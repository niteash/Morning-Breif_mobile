"""Explicit opt-in hosted staging checks; never collected by offline pytest.

Creates a private bucket if absent and two disposable email/password accounts.
Exercises real Auth/PostgREST/Storage through the FastAPI ASGI test client, with no
SMS, provider generation, FCM or scheduler. Deletes test objects/users in finally.
"""
import contextlib
from datetime import datetime
import io
import logging
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

from dotenv import dotenv_values
import requests

STAGING_URL = 'https://wwtntxknfjagdjdgiaxu.supabase.co'
BACKEND = Path(__file__).resolve().parents[1]


class SmokeFailure(RuntimeError):
    """A safe diagnostic written by this test runner, never a provider response."""


def validate_environment(values):
    if values.get('SUPABASE_URL') != STAGING_URL:
        raise ValueError('This runner only supports the authorized staging project')
    for key in ('GEMINI_API_KEY', 'AZURE_SPEECH_KEY', 'FIREBASE_SERVICE_ACCOUNT_PATH', 'INGESTION_OPERATOR_IDS'):
        if key not in values or values[key] != '':
            raise ValueError('Provider and operator configuration must be explicitly blank')
    for key in ('ACCOUNT_DELETION_ENABLED', 'ACCOUNT_DELETION_WORKER_ENABLED'):
        if values.get(key, 'false') != 'false':
            raise ValueError('Account deletion must be disabled in this launcher')
    if values.get('PUSH_DELIVERY_ENABLED', 'false') != 'false':
        raise ValueError('Push delivery must be disabled')
    if values.get('NEWS_INGESTION_ENABLED', 'false') != 'false':
        raise ValueError('Periodic ingestion must be disabled')
    if values.get('SCHEDULER_ENABLED') != 'false':
        raise ValueError('Scheduler must be disabled')
    if values.get('AUTOMATIC_BRIEFING_PREFERENCES_ENABLED', 'false') != 'false':
        raise ValueError('Automatic briefing preferences must remain disabled')
    if not values.get('SUPABASE_PUBLISHABLE_KEY') or not values.get('SUPABASE_SERVICE_ROLE_KEY'):
        raise ValueError('Staging API credentials are required')


def require(condition, label):
    if not condition:
        raise SmokeFailure(label)


def run():
    values = dotenv_values(BACKEND / '.env.staging')
    validate_environment(values)
    os.environ.update({key: value for key, value in values.items() if value is not None})
    # Prevent any library from falling back to the existing production .env file.
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['NEWS_INGESTION_ENABLED'] = 'false'
    os.environ['AUTOMATIC_BRIEFING_PREFERENCES_ENABLED'] = 'false'
    os.environ['PUSH_DELIVERY_ENABLED'] = 'false'
    os.environ['ACCOUNT_DELETION_ENABLED'] = 'false'
    os.environ['ACCOUNT_DELETION_WORKER_ENABLED'] = 'false'
    sys.path.insert(0, str(BACKEND))
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    from fastapi.testclient import TestClient
    from supabase import create_client
    from app.main import app
    from app.services.news.categories import resolve_category_ids

    admin = create_client(STAGING_URL, values['SUPABASE_SERVICE_ROLE_KEY'])
    public_key = values['SUPABASE_PUBLISHABLE_KEY']
    accounts = []
    objects = []
    passed = []
    try:
        buckets = admin.storage.list_buckets()
        if not any(bucket.id == 'briefings' for bucket in buckets):
            admin.storage.create_bucket('briefings', options={
                'public': False, 'file_size_limit': 20 * 1024 * 1024,
                'allowed_mime_types': ['audio/mpeg'],
            })
        bucket = admin.storage.get_bucket('briefings')
        require(bucket.public is False, 'Audio bucket must be private')
        passed.append('private bucket configuration')

        category_ids = resolve_category_ids()
        require(len(category_ids) == 5, 'Expected five configured categories')
        for _ in range(2):
            email = f'staging-smoke-{uuid4().hex}@example.invalid'
            password = secrets.token_urlsafe(32)
            user = admin.auth.admin.create_user({
                'email': email, 'password': password, 'email_confirm': True,
            }).user
            require(user is not None, 'Disposable Auth user creation failed')
            account = {'id': user.id, 'token': None}
            accounts.append(account)
            client = create_client(STAGING_URL, public_key)
            session = client.auth.sign_in_with_password({'email': email, 'password': password}).session
            require(session is not None, 'Disposable Auth sign-in failed')
            account.update(token=session.access_token, client=client)
        first, second = accounts
        headers = [{'Authorization': 'Bearer ' + account['token']} for account in accounts]
        # Legacy handlers still print profile details; suppress these in this test runner.
        with contextlib.redirect_stdout(io.StringIO()), TestClient(app) as api:
            require(api.get('/health').status_code == 200, 'Health check failed')
            require(api.get('/').json()['scheduler'] == 'disabled', 'Scheduler unexpectedly active')
            require(api.get('/api/v1/users/me/preferences').status_code == 401, 'Unauthenticated request accepted')
            require(api.get('/api/v1/users/me/preferences', headers={'Authorization': 'Bearer invalid'}).status_code == 401,
                    'Invalid token accepted')
            response = api.get('/api/v1/categories')
            require(response.status_code == 200 and len(response.json()['categories']) == 5, 'Category API failed')
            for index, header in enumerate(headers):
                response = api.put('/api/v1/users/me/preferences', headers=header, json={
                    'timezone': 'Asia/Yangon', 'delivery_hour': 7 + index, 'delivery_minute': 0,
                })
                require(response.status_code == 200, 'Authenticated preferences write failed')
                response = api.get('/api/v1/users/me/preferences', headers=header)
                require(response.status_code == 200 and response.json()['profile']['id'] == accounts[index]['id'],
                        'Profile ownership check failed')
                response = api.put('/api/v1/users/me/categories', headers=header,
                                   json={'category_ids': [str(category_ids['technology'])]})
                require(response.status_code == 200, 'Category RPC through API failed')
            response = api.put('/api/v1/users/me/categories', headers=headers[0], json={'category_ids': [str(uuid4())]})
            require(response.status_code == 422, 'Invalid category not rejected')
            saved = first['client'].table('user_categories').select('category_id').execute().data
            require(len(saved) == 1 and saved[0]['category_id'] == str(category_ids['technology']),
                    'Failed category replacement lost preferences')
            require(second['client'].table('profiles').select('id').eq('id', first['id']).execute().data == [],
                    'Cross-user profile visible through PostgREST')
            require(api.get('/api/v1/news', headers=headers[0]).status_code == 200, 'News API failed')
            require(api.post('/api/v1/news/ingest-all', headers=headers[0]).status_code == 403,
                    'Non-operator ingestion accepted')
            passed.append('real Auth sessions, API preferences/categories, isolation and operator denial')

            day = datetime.now(ZoneInfo('Asia/Yangon')).date().isoformat()
            path = f"{first['id']}/{day}/staging-smoke-{uuid4().hex}.mp3"
            # Encoded-frame fixture tests storage access, not Burmese TTS quality.
            audio = (bytes.fromhex('fffb9064') + bytes(413)) * 100
            objects.append(path)
            admin.storage.from_('briefings').upload(path, audio, {'content-type': 'audio/mpeg', 'upsert': 'false'})
            claim = admin.rpc('claim_briefing_v2', {'p_user_id': first['id'], 'p_date': day}).execute().data
            require(claim['outcome'] == 'claimed', 'Service claim failed')
            saved = admin.rpc('finish_briefing_v2', {
                'p_user_id': first['id'], 'p_date': day, 'p_token': claim['token'],
                'p_script': 'Staging storage fixture; not a news briefing.', 'p_audio_path': path, 'p_duration': 3,
            }).execute().data
            require(saved['status'] == 'ready', 'Service completion failed')
            response = api.get('/api/v1/briefings/today/saved', headers=headers[0])
            require(response.status_code == 200, 'Saved briefing API failed')
            signed_url = response.json()['briefing']['audio_url']
            require(signed_url and urlparse(signed_url).netloc == urlparse(STAGING_URL).netloc, 'Invalid signed URL origin')
            downloaded = requests.get(signed_url, timeout=25, allow_redirects=False)
            require(downloaded.status_code == 200 and downloaded.content == audio, 'Signed download failed')
            other = api.get('/api/v1/briefings/today/saved', headers=headers[1])
            require(other.status_code == 200 and other.json()['briefing'] is None, 'Other user received saved briefing')
            public = requests.get(f'{STAGING_URL}/storage/v1/object/public/briefings/{path}', timeout=25, allow_redirects=False)
            require(public.status_code in (400, 401, 403, 404), 'Private audio exposed on public URL')
            cross_user = requests.get(f'{STAGING_URL}/storage/v1/object/authenticated/briefings/{path}',
                                      headers={'apikey': public_key, **headers[1]}, timeout=25, allow_redirects=False)
            require(cross_user.status_code in (400, 401, 403, 404), 'Direct cross-user audio access accepted')
            passed.append('service upload/completion, saved API signing, signed download and private access denial')
    finally:
        cleanup_errors = []
        if objects:
            try:
                admin.storage.from_('briefings').remove(objects)
            except Exception:
                cleanup_errors.append('test audio removal')
        for account in accounts:
            if account['token']:
                try:
                    admin.auth.admin.sign_out(account['token'])
                except Exception:
                    cleanup_errors.append('session revocation')
            try:
                admin.auth.admin.delete_user(account['id'])
            except Exception:
                cleanup_errors.append('test account deletion')
        if cleanup_errors:
            raise SmokeFailure('Cleanup incomplete: ' + ', '.join(cleanup_errors))
    return passed


if __name__ == '__main__':
    try:
        for check in run():
            print('PASS:', check)
        print('Disposable accounts, sessions and audio cleaned up. Private bucket retained.')
    except Exception as error:
        # Exception messages can embed signed URLs or provider responses.
        print('Staging smoke failed:', type(error).__name__)
        if isinstance(error, SmokeFailure):
            print('Check:', str(error))
        raise SystemExit(1)
