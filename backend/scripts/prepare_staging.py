"""Create a private, Supabase-only staging environment after operator approval.

Run from the app root: .venv/bin/python backend/scripts/prepare_staging.py
Never imports app.config or copies production provider credentials.
"""
import os
from pathlib import Path

import requests
from dotenv import dotenv_values

STAGING_PROJECT_REF = 'wwtntxknfjagdjdgiaxu'
BACKEND = Path(__file__).resolve().parents[1]


def build_environment(keys: list[dict]) -> dict[str, str]:
    def key_of_type(kind):
        candidates = [key for key in keys if key.get('type') == kind
                      and not key.get('disabled') and key.get('api_key')]
        if len(candidates) != 1:
            raise RuntimeError(f'Expected one enabled staging {kind} key')
        return candidates[0]['api_key']

    return {
        'SUPABASE_URL': f'https://{STAGING_PROJECT_REF}.supabase.co',
        'SUPABASE_PUBLISHABLE_KEY': key_of_type('publishable'),
        'SUPABASE_SERVICE_ROLE_KEY': key_of_type('secret'),
        'GEMINI_API_KEY': '',
        'AZURE_SPEECH_KEY': '',
        'AZURE_SPEECH_REGION': '',
        'AZURE_SPEECH_VOICE': 'my-MM-NilarNeural',
        'FIREBASE_SERVICE_ACCOUNT_PATH': '',
        'INGESTION_OPERATOR_IDS': '',
        'SCHEDULER_ENABLED': 'false',
        'AUTOMATIC_BRIEFING_PREFERENCES_ENABLED': 'false',
        'ACCOUNT_DELETION_ENABLED': 'false',
        'ACCOUNT_DELETION_WORKER_ENABLED': 'false',
        'PUSH_DELIVERY_ENABLED': 'false',
        'NEWS_INGESTION_ENABLED': 'false',
    }


def write_environment(destination: Path, values: dict[str, str]) -> None:
    if any(any(char in value for char in ("'", '\n', '\r')) for value in values.values()):
        raise ValueError('Unsupported environment value')
    # Exclusive creation preserves existing settings; owner-only permissions protect keys.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write('# Private staging environment. Never commit this file.\n')
        for name, value in values.items():
            # Single-quoted dotenv values preserve Unicode and prevent interpolation.
            output.write(f"{name}='{value}'\n")


def main() -> None:
    destination = BACKEND / '.env.staging'
    if destination.exists():
        raise RuntimeError('backend/.env.staging already exists; preserved')
    token = dotenv_values(BACKEND / '.env').get('SUPABASE_ACCESS_TOKEN_STAGING')
    if not token:
        raise RuntimeError('SUPABASE_ACCESS_TOKEN_STAGING is missing')
    response = requests.get(
        f'https://api.supabase.com/v1/projects/{STAGING_PROJECT_REF}/api-keys',
        headers={'Authorization': f'Bearer {token}'}, params={'reveal': 'true'}, timeout=25,
    )
    if response.status_code != 200:
        raise RuntimeError(f'Staging API key lookup returned HTTP {response.status_code}')
    write_environment(destination, build_environment(response.json()))
    print('Created private backend/.env.staging; AI, speech, push and scheduler disabled.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print provider responses, environment contents or credentials.
        raise SystemExit(f'Staging setup failed ({type(error).__name__}). No credentials printed.')
