"""Launch local staging without loading or overwriting production .env files."""
import argparse
import ipaddress
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
from dotenv import dotenv_values

STAGING_URL = 'https://wwtntxknfjagdjdgiaxu.supabase.co'
ROOT = Path(__file__).resolve().parents[2]
SYSTEM_ENV = ('PATH', 'HOME', 'USER', 'TMPDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL',
              'SHELL', 'TERM', 'CI', 'ANDROID_HOME', 'ANDROID_SDK_ROOT', 'JAVA_HOME', 'EXPO_OFFLINE')
PROVIDER_KEYS = ('GEMINI_API_KEY', 'AZURE_SPEECH_KEY', 'AZURE_SPEECH_REGION', 'AZURE_SPEECH_VOICE')
PUSH_KEYS = ('FIREBASE_SERVICE_ACCOUNT_PATH',)
BACKEND_KEYS = ('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_SERVICE_ROLE_KEY',
                'FIREBASE_SERVICE_ACCOUNT_PATH', 'INGESTION_OPERATOR_IDS', 'SCHEDULER_ENABLED',
                'AUTOMATIC_BRIEFING_PREFERENCES_ENABLED',
                'RSS_IMPORT_ACCESS_TOKEN', 'RSS_IMPORT_RLS_POLICY_VERIFIED')


def validate(values):
    if values.get('SUPABASE_URL') != STAGING_URL:
        raise ValueError('Only the authorized staging project is supported.')
    if not values.get('SUPABASE_PUBLISHABLE_KEY') or not values.get('SUPABASE_SERVICE_ROLE_KEY'):
        raise ValueError('Run the approved staging preparation first.')
    if not values['SUPABASE_PUBLISHABLE_KEY'].startswith('sb_publishable_'):
        raise ValueError('Use the staging publishable key, never a secret key.')
    for key in ('FIREBASE_SERVICE_ACCOUNT_PATH', 'INGESTION_OPERATOR_IDS'):
        if values.get(key) != '':
            raise ValueError('This launcher requires blank provider/operator credentials.')
    for key in ('ACCOUNT_DELETION_ENABLED', 'ACCOUNT_DELETION_WORKER_ENABLED'):
        if values.get(key, 'false') != 'false':
            raise ValueError('Account deletion must be disabled in this launcher')
    if values.get('PUSH_DELIVERY_ENABLED', 'false') != 'false':
        raise ValueError('Push delivery must be disabled')
    if values.get('NEWS_INGESTION_ENABLED', 'false') != 'false':
        raise ValueError('This launcher requires periodic ingestion to be disabled.')
    if values.get('SCHEDULER_ENABLED') != 'false':
        raise ValueError('This launcher requires the scheduler to be disabled.')
    if values.get('AUTOMATIC_BRIEFING_PREFERENCES_ENABLED', 'false') != 'false':
        raise ValueError('Automatic briefing preferences must remain disabled in this launcher.')


def validate_api_url(value):
    url = urlparse(value)
    if url.scheme != 'http' or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise ValueError('Use the local staging API base URL, such as http://10.0.2.2:8000.')
    if url.hostname != 'localhost':
        try:
            address = ipaddress.ip_address(url.hostname)
        except ValueError:
            raise ValueError('Use localhost or a private LAN/emulator IP address.') from None
        if not address.is_private or address.is_unspecified or address.is_multicast:
            raise ValueError('Use a private LAN/emulator IP address.')
    if not url.port:
        raise ValueError('Include the local API port, normally 8000.')
    return value.rstrip('/')


def child_environment(values, mode, api_url=None, inherited=None, *, provider_values=None,
                      push_values=None, enable_generation=False, enable_automation=False,
                      enable_push=False, enable_ads=False):
    if mode not in ('backend', 'mobile'):
        raise ValueError('Unsupported staging launch mode')
    validate(values)
    if enable_automation and not enable_generation:
        raise ValueError('Automatic generation requires isolated generation providers')
    if mode == 'backend' and enable_push and not enable_automation:
        raise ValueError('Push delivery requires automatic delivery mode')
    inherited = os.environ if inherited is None else inherited
    # Never pass inherited management/provider secrets to Expo or the API.
    env = {key: inherited[key] for key in SYSTEM_ENV if key in inherited}
    env['PYTHON_DOTENV_DISABLED'] = '1'
    if mode == 'backend':
        env.update({key: values.get(key) or '' for key in BACKEND_KEYS})
        # Protected file may retain AI credentials. Normal staging never receives
        # them, and dotenv fallback is disabled. Only the bounded audio-test runner
        # may load its separately approved provider configuration.
        if enable_generation:
            provider_values = provider_values or {}
            missing = [key for key in PROVIDER_KEYS[:3] if not (provider_values.get(key) or '').strip()]
            if missing or set(provider_values) - set(PROVIDER_KEYS):
                raise ValueError('Complete isolated provider configuration is required')
            env.update({key: (provider_values.get(key) or '').strip() for key in PROVIDER_KEYS})
            env['BRIEFING_GENERATION_ENABLED'] = 'true'
            env['GENERATION_WORKER_ENABLED'] = 'true'
            env['ON_DEMAND_NEWS_REFRESH_ENABLED'] = 'true'
        else:
            env.update({key: '' for key in PROVIDER_KEYS})
            env['BRIEFING_GENERATION_ENABLED'] = 'false'
            env['GENERATION_WORKER_ENABLED'] = 'false'
            env['ON_DEMAND_NEWS_REFRESH_ENABLED'] = 'false'
        if enable_push:
            push_values = push_values or {}
            path_value = (push_values.get('FIREBASE_SERVICE_ACCOUNT_PATH') or '').strip()
            credential_path = Path(path_value)
            if set(push_values) - set(PUSH_KEYS) or not credential_path.is_absolute() or not credential_path.is_file():
                raise ValueError('A valid isolated Firebase service account path is required')
            env['FIREBASE_SERVICE_ACCOUNT_PATH'] = path_value
        env['NEWS_INGESTION_ENABLED'] = 'true' if enable_automation else 'false'
        env['SCHEDULER_ENABLED'] = 'true' if enable_automation else 'false'
        env['AUTOMATIC_BRIEFING_PREFERENCES_ENABLED'] = 'true' if enable_automation else 'false'
        env['PUSH_DELIVERY_ENABLED'] = 'true' if enable_push else 'false'
        env['ACCOUNT_DELETION_ENABLED'] = 'false'
        env['ACCOUNT_DELETION_WORKER_ENABLED'] = 'false'
        env['BRIEFING_SOURCES_ENABLED'] = 'true'
        env['APP_ENV'] = 'staging'
        env['TRIAL_STAGING_ACCOUNT_ENABLED'] = values.get('TRIAL_STAGING_ACCOUNT_ENABLED', 'false')
    else:
        env.update({
            'EXPO_NO_DOTENV': '1',
            'EXPO_PUBLIC_SUPABASE_URL': STAGING_URL,
            'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY': values['SUPABASE_PUBLISHABLE_KEY'],
            'EXPO_PUBLIC_API_URL': validate_api_url(api_url),
            'EXPO_PUBLIC_PUSH_ENABLED': 'true' if enable_push else 'false',
            'EXPO_PUBLIC_ADS_ENABLED': 'true' if enable_ads else 'false',
            'EXPO_PUBLIC_AUTO_PLAY_ENABLED': 'false',
        })
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    backend = sub.add_parser('backend')
    backend.add_argument('--host', choices=['127.0.0.1', '0.0.0.0'], default='127.0.0.1')
    backend.add_argument('--port', type=int, default=8000)
    backend.add_argument('--enable-generation', action='store_true')
    backend.add_argument('--enable-automation', action='store_true')
    backend.add_argument('--enable-push', action='store_true')
    mobile = sub.add_parser('mobile')
    mobile.add_argument('--api-url', default='http://10.0.2.2:8000')
    mobile.add_argument('--port', type=int, default=8081)
    mobile.add_argument('--enable-push', action='store_true')
    mobile.add_argument('--enable-ads', action='store_true')
    args = parser.parse_args()
    try:
        values = dotenv_values(ROOT / 'backend/.env.staging', interpolate=False)
        provider_values = (dotenv_values(ROOT / 'backend/.env.audio-test', interpolate=False)
                           if args.mode == 'backend' and args.enable_generation else None)
        push_values = (dotenv_values(ROOT / 'backend/.env.push-test', interpolate=False)
                       if args.mode == 'backend' and args.enable_push else None)
        env = child_environment(values, args.mode, getattr(args, 'api_url', None),
                                provider_values=provider_values,
                                push_values=push_values,
                                enable_generation=args.mode == 'backend' and args.enable_generation,
                                enable_automation=args.mode == 'backend' and args.enable_automation,
                                enable_push=args.enable_push,
                                enable_ads=args.mode == 'mobile' and args.enable_ads)
        if args.mode == 'backend':
            command = [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', args.host, '--port', str(args.port)]
            directory = ROOT / 'backend'
        else:
            command = ['node', str(ROOT / 'node_modules/expo/bin/cli'), 'start', '--clear', '--port', str(args.port)]
            directory = ROOT
        print(f'Starting {args.mode} with staging Supabase; generation={getattr(args, "enable_generation", False)}, automation={getattr(args, "enable_automation", False)}, push={args.enable_push}.', flush=True)
        return subprocess.call(command, cwd=directory, env=env)
    except (ValueError, OSError):
        print('Staging launch failed. Check .env.staging, the local API URL, Node 22 and installed dependencies.', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
