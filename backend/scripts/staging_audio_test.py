"""Read-only staging rehearsal by default; real execution requires exact approval arguments.
Never imports FastAPI main or starts a scheduler. Never claims a trial.
"""
import argparse
import asyncio
from contextlib import redirect_stdout, redirect_stderr
from datetime import date
import io
import json
import base64
import logging
import os
import re
from pathlib import Path
import sys
from uuid import UUID
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
PROJECT = 'wwtntxknfjagdjdgiaxu'
STAGING_URL = f'https://{PROJECT}.supabase.co'
USER = 'e726b864-c879-4b8f-9ac1-c5cb73ae8a58'
STATE = {'stage': 'configuration', 'generation_invoked': False}

PROVIDER_KEYS = ('GEMINI_API_KEY', 'AZURE_SPEECH_KEY', 'AZURE_SPEECH_REGION', 'AZURE_SPEECH_VOICE')
DISABLED = ('SCHEDULER_ENABLED', 'NEWS_INGESTION_ENABLED', 'PUSH_DELIVERY_ENABLED',
            'AUTOMATIC_BRIEFING_PREFERENCES_ENABLED', 'TRIAL_STAGING_ACCOUNT_ENABLED',
            'ACCOUNT_DELETION_ENABLED', 'ACCOUNT_DELETION_WORKER_ENABLED')


def provider_readiness(provider):
    """Report names/categories only; never echo malformed credential values."""
    missing = [key for key in PROVIDER_KEYS[:3] if not (provider.get(key) or '').strip()]
    errors = []
    if set(provider) - set(PROVIDER_KEYS):
        errors.append('unexpected_provider_file_keys')
    if any(value and value != value.strip() for key in PROVIDER_KEYS if (value := provider.get(key))):
        errors.append('surrounding_whitespace')
    region = provider.get('AZURE_SPEECH_REGION')
    if region and not re.fullmatch(r'[a-z0-9-]+', region):
        errors.append('invalid_region_format')
    if (provider.get('AZURE_SPEECH_VOICE') or 'my-MM-NilarNeural') not in {'my-MM-NilarNeural', 'my-MM-ThihaNeural'}:
        errors.append('unsupported_burmese_voice')
    return missing, errors


def access_token_is_expired(token, now=None):
    """Unverified expiry preflight only; Auth remains the authority on the session."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return True
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
        expiry = payload.get('exp')
        return not isinstance(expiry, (int, float)) or expiry <= (now or __import__('time').time())
    except (ValueError, TypeError, json.JSONDecodeError):
        return True


def validate_approval(args, digest, day, entitlement):
    if (args.approve_project != PROJECT or args.approve_user != USER
            or args.approve_date != day or args.approve_batch != digest):
        raise ValueError('Exact project/account/date/batch approval required')
    if entitlement.get('can_generate') is not True:
        raise ValueError('An existing active staging entitlement is required')


def reserve_attempt(directory, day):
    date.fromisoformat(day)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    marker = directory / f'{USER}-{day}.attempt'
    # Retain after failures/timeouts. Never delete to retry without renewed approval.
    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write('One approved attempt reserved. Inspect database before any further action.\n')
    return marker


def run(args):
    STATE.update(stage='configuration', generation_invoked=False)
    values = dotenv_values(ROOT / 'backend/.env.staging', interpolate=False)
    if values.get('SUPABASE_URL') != STAGING_URL:
        raise ValueError('Wrong staging target')
    for key in ('SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_SERVICE_ROLE_KEY'):
        if not values.get(key):
            raise ValueError('Missing staging database configuration')
    token = values.get('AUDIO_TEST_ACCESS_TOKEN') or values.get('RSS_IMPORT_ACCESS_TOKEN')
    if not token:
        raise ValueError('Missing staging account session')
    if access_token_is_expired(token):
        raise ValueError('Staging account session expired; refresh through staging_operator_login.py')
    # Provider secrets live in a separate ignored file. The ordinary staging launcher
    # keeps its blank-provider protection. Never read backend/.env.
    provider = dotenv_values(ROOT / 'backend/.env.audio-test', interpolate=False)
    missing, configuration_errors = provider_readiness(provider)
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['APP_ENV'] = 'staging'
    os.environ['BRIEFING_SINGLE_ATTEMPT'] = 'true'
    for key in DISABLED:
        os.environ[key] = 'false'
    for key in ('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_SERVICE_ROLE_KEY'):
        os.environ[key] = values[key]
    for key in PROVIDER_KEYS:
        os.environ[key] = provider.get(key) or ('my-MM-NilarNeural' if key == 'AZURE_SPEECH_VOICE' else '')
    os.environ['FIREBASE_SERVICE_ACCOUNT_PATH'] = ''
    # These SDKs can log request URLs and payloads; operator output is allowlisted below.
    logging.disable(logging.CRITICAL)
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.lib.supabase import create_supabase_client, admin_supabase
    from app.services.briefing.dates import get_briefing_date
    from app.services.entitlements import get_trial
    from app.services.news.selector import select_recent_stories
    from app.services.briefing.rehearsal import validate_selection, batch_digest, mock_rehearsal
    from app.services.briefing.jobs import generate_and_save
    client = create_supabase_client(token)
    STATE['stage'] = 'staging_session_validation'
    identity = client.auth.get_user(token)
    if str(identity.user.id) != USER or identity.user.is_anonymous:
        raise ValueError('Session does not belong to the approved staging account')
    UUID(USER)
    STATE['stage'] = 'read_only_profile_entitlement_and_news'
    day = get_briefing_date(client, USER)
    entitlement = get_trial(USER)
    categories = asyncio.run(select_recent_stories(USER, token, stories_per_category=5, hours=24))
    counts = validate_selection(categories)
    digest = batch_digest(categories)
    existing = client.table('briefings').select('id,status').eq('user_id', USER).eq('briefing_date', day).execute().data
    attempts = admin_supabase.table('briefing_generation_jobs').select('state,attempts').eq('user_id', USER).eq('briefing_date', day).execute().data
    STATE['stage'] = 'offline_mock_rehearsal'
    result = {'project': PROJECT, 'date': day, 'batch_sha256': digest, 'counts': counts,
              'can_generate': entitlement['can_generate'], 'entitlement_status': entitlement['status'],
              'entitlement_reason': entitlement.get('reason'),
              'existing_briefing': bool(existing), 'existing_job': bool(attempts),
              'provider_file_exists': (ROOT / 'backend/.env.audio-test').is_file(),
              'missing_configuration': missing, 'configuration_errors': configuration_errors,
              'rehearsal': mock_rehearsal(USER, day, categories)}
    if not args.execute:
        return result
    STATE['stage'] = 'approval_and_existing_job_checks'
    validate_approval(args, digest, day, entitlement)
    if result['missing_configuration'] or configuration_errors or existing or attempts:
        raise ValueError('Missing provider configuration or an existing briefing/job; operator review required')
    import re
    if not re.fullmatch(r'[a-z0-9-]+', os.environ['AZURE_SPEECH_REGION']) or os.environ['AZURE_SPEECH_VOICE'] not in {'my-MM-NilarNeural', 'my-MM-ThihaNeural'}:
        raise ValueError('Invalid speech configuration')
    if get_briefing_date(client, USER) != day:
        raise ValueError('Local briefing date changed; repeat dry run')
    STATE['stage'] = 'reserve_local_attempt'
    reserve_attempt(ROOT / '.audio-test', day)
    # Exactly one coordinator invocation; no retry or regeneration ID.
    STATE.update(stage='single_generation_attempt', generation_invoked=True)
    saved, created = generate_and_save(USER, day, categories)
    result.update(mode='real', newly_created=created, saved_status=saved.get('status'),
                  duration_seconds=saved.get('duration_seconds'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    for key in ('project', 'user', 'date', 'batch'):
        parser.add_argument(f'--approve-{key}')
    args = parser.parse_args()
    try:
        # Suppress legacy selector printouts (articles, IDs, raw errors).
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = run(args)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as error:
        # No exception body/traceback, tokens, provider responses or signed URLs.
        import re
        code = getattr(error, 'code', None)
        code = code if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_]{1,48}', code) else 'unavailable'
        message = str(error)
        safe_error = ('expired_staging_session' if 'session expired' in message.lower()
                      else 'invalid_staging_session' if type(error).__name__ == 'AuthApiError'
                      else type(error).__name__)
        print(json.dumps({'status': 'stopped', 'error_category': safe_error,
            'service_code': code,
            **STATE, 'committed_rows': 'unknown; inspect staging' if STATE['generation_invoked'] else 0,
            'next_action': 'Do not retry execute; inspect entitlement, configuration and attempt marker. Run dry-run diagnostics.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
