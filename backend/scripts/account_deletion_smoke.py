"""Opt-in disposable staging Auth/Storage deletion check. No providers or background jobs.

Pauses after requesting deletion so a reviewer can advance only the printed test
user's available_at through the connected SQL tool (or wait fifteen minutes).
No credentials/session tokens are printed or persisted.
"""
import logging
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4

from dotenv import dotenv_values
from run_staging import child_environment, STAGING_URL
from staging_smoke import require


def run():
    backend = Path(__file__).resolve().parents[1]
    values = dotenv_values(backend / '.env.staging', interpolate=False)
    environment = child_environment(values, 'backend')
    os.environ.clear()
    os.environ.update(environment)
    os.environ['ACCOUNT_DELETION_ENABLED'] = 'true'  # This isolated TestClient only.
    sys.path.insert(0, str(backend))
    logging.getLogger('httpx').setLevel(logging.WARNING)
    from supabase import create_client
    from fastapi.testclient import TestClient
    from app.main import app
    from app.lib.supabase import admin_supabase as admin
    from app.services.account_deletion import process_one_deletion

    accounts = []
    paths = []
    deleted = set()
    try:
        for _ in range(2):
            email = f'deletion-smoke-{uuid4().hex}@example.invalid'
            password = secrets.token_urlsafe(32)
            user = admin.auth.admin.create_user({'email': email, 'password': password, 'email_confirm': True}).user
            require(user is not None, 'Fixture creation failed')
            accounts.append({'id': user.id})
            client = create_client(STAGING_URL, values['SUPABASE_PUBLISHABLE_KEY'])
            session = client.auth.sign_in_with_password({'email': email, 'password': password}).session
            require(session is not None, 'Fixture sign in failed')
            accounts[-1].update(client=client, token=session.access_token)
            path = f'{user.id}/deletion-smoke/{uuid4().hex}.mp3'
            paths.append(path)
            admin.storage.from_('briefings').upload(path, b'ID3-disposable-fixture', {'content-type': 'audio/mpeg'})
        first, other = accounts
        # Refuse to claim unrelated queued deletions, even on staging.
        require(not admin.table('account_deletion_jobs').select('user_id').execute().data, 'Staging deletion queue must be empty')
        headers = {'Authorization': 'Bearer ' + first['token']}
        with TestClient(app) as api:
            require(api.get('/api/v1/users/me/deletion', headers=headers).json() == {'enabled': True, 'status': None}, 'Initial status failed')
            response = api.request('DELETE', '/api/v1/users/me', headers=headers, json={'confirmation': 'DELETE'})
            require(response.status_code == 202 and response.json()['status'] == 'requested', 'Request not accepted')
            require(api.get('/api/v1/users/me/preferences', headers=headers).status_code in (401, 403), 'API still allows deleted account')
            require(not first['client'].table('profiles').select('id').execute().data, 'Old JWT still reads profile')
            require(admin.rpc('claim_account_deletion', {}).execute().data is None, 'Waiting period missing')
            print(f'Prepared disposable deletion user: {first["id"]}', flush=True)
            input('Advance only this test job to due (or wait 15 minutes), then press Enter: ')
            require(process_one_deletion(), 'No due test deletion was processed')
            require(not admin.table('account_deletion_jobs').select('user_id').eq('user_id', first['id']).execute().data, 'Cleanup did not finish')
            require(admin.rpc('account_is_active', {'p_user_id': first['id']}).execute().data is False, 'Deleted user remains active')
            remaining = admin.auth.admin.list_users()
            require(all(user.id != first['id'] for user in remaining), 'Deleted Auth user remains')
            deleted.add(first['id'])
            require(not admin.storage.from_('briefings').list(first['id'] + '/deletion-smoke'), 'Deleted audio remains')
            require(admin.storage.from_('briefings').download(paths[1]) == b'ID3-disposable-fixture', 'Other user audio changed')
            require(admin.auth.admin.get_user_by_id(other['id']).user.id == other['id'], 'Other Auth user changed')
            print('PASS: real authenticated deletion request, old-token denial, Storage cleanup, Auth removal and other-user isolation', flush=True)
    finally:
        for path in paths:
            try:
                admin.storage.from_('briefings').remove([path])
            except Exception:
                print('Fixture audio cleanup needs inspection', flush=True)
        for account in accounts:
            if account['id'] not in deleted:
                try:
                    admin.auth.admin.delete_user(account['id'])
                except Exception:
                    print(f'Fixture Auth cleanup needs inspection: {account["id"]}', flush=True)


if __name__ == '__main__':
    if sys.argv[1:] != ['--disposable-staging']:
        raise SystemExit('Explicit --disposable-staging is required; read this script before running.')
    try:
        run()
    except Exception as error:
        # Provider errors can contain tokens/URLs; keep output to exception type.
        print(f'Staging deletion verification failed: {type(error).__name__}', file=sys.stderr)
        raise SystemExit(1) from None
