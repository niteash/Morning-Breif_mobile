import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('run_staging', Path(__file__).resolve().parents[1] / 'scripts/run_staging.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def values():
    return dict(SUPABASE_URL=launcher.STAGING_URL, SUPABASE_PUBLISHABLE_KEY='sb_publishable_test',
                SUPABASE_SERVICE_ROLE_KEY='sb_secret_test', GEMINI_API_KEY='', AZURE_SPEECH_KEY='',
                FIREBASE_SERVICE_ACCOUNT_PATH='', INGESTION_OPERATOR_IDS='', SCHEDULER_ENABLED='false',
                AUTOMATIC_BRIEFING_PREFERENCES_ENABLED='false')


def test_mobile_receives_only_public_staging_credentials(values):
    env = launcher.child_environment(values, 'mobile', 'http://10.0.2.2:8000/', {
        'PATH': '/usr/bin', 'SUPABASE_ACCESS_TOKEN_STAGING': 'management-secret',
        'EXPO_PUBLIC_GEMINI_KEY': 'accidental-public-secret', 'AZURE_SPEECH_KEY': 'production-secret',
        'EXPO_PUBLIC_SUPABASE_URL': 'https://source.supabase.co',
    })
    assert env['EXPO_PUBLIC_SUPABASE_URL'] == launcher.STAGING_URL
    assert env['EXPO_PUBLIC_API_URL'] == 'http://10.0.2.2:8000'
    assert env['EXPO_NO_DOTENV'] == '1'
    assert env['EXPO_PUBLIC_PUSH_ENABLED'] == 'false'
    assert not any('secret' in value for value in env.values())
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in env


def test_backend_cannot_fall_back_to_inherited_production_keys(values):
    env = launcher.child_environment(values, 'backend', inherited={'GEMINI_API_KEY': 'production-secret', 'NEWS_INGESTION_ENABLED': 'true', 'PUSH_DELIVERY_ENABLED': 'true', 'ACCOUNT_DELETION_ENABLED': 'true', 'ACCOUNT_DELETION_WORKER_ENABLED': 'true'})
    assert env['SUPABASE_URL'] == launcher.STAGING_URL
    assert env['GEMINI_API_KEY'] == ''
    assert env['PYTHON_DOTENV_DISABLED'] == '1'
    assert env['SCHEDULER_ENABLED'] == 'false'
    assert env['AUTOMATIC_BRIEFING_PREFERENCES_ENABLED'] == 'false'
    assert env['NEWS_INGESTION_ENABLED'] == 'false'
    assert env['PUSH_DELIVERY_ENABLED'] == 'false'
    assert env['ACCOUNT_DELETION_ENABLED'] == 'false'
    assert env['ACCOUNT_DELETION_WORKER_ENABLED'] == 'false'


def test_explicit_generation_mode_uses_only_isolated_provider_file(values):
    provider = {'GEMINI_API_KEY': 'gemini-test', 'AZURE_SPEECH_KEY': 'azure-test',
                'AZURE_SPEECH_REGION': 'southeastasia', 'AZURE_SPEECH_VOICE': 'my-MM-NilarNeural'}
    env = launcher.child_environment(values, 'backend', provider_values=provider,
                                     enable_generation=True,
                                     inherited={'GEMINI_API_KEY': 'wrong-inherited-key'})
    assert env['GEMINI_API_KEY'] == 'gemini-test'
    assert env['BRIEFING_GENERATION_ENABLED'] == 'true'
    assert env['ON_DEMAND_NEWS_REFRESH_ENABLED'] == 'true'
    assert env['SCHEDULER_ENABLED'] == env['PUSH_DELIVERY_ENABLED'] == 'false'


def test_automation_is_explicit_and_requires_generation(values):
    with pytest.raises(ValueError):
        launcher.child_environment(values, 'backend', enable_automation=True)
    provider = {'GEMINI_API_KEY': 'gemini-test', 'AZURE_SPEECH_KEY': 'azure-test',
                'AZURE_SPEECH_REGION': 'southeastasia', 'AZURE_SPEECH_VOICE': 'my-MM-NilarNeural'}
    env = launcher.child_environment(values, 'backend', provider_values=provider,
                                     enable_generation=True, enable_automation=True)
    assert env['SCHEDULER_ENABLED'] == 'true'
    assert env['AUTOMATIC_BRIEFING_PREFERENCES_ENABLED'] == 'true'
    assert env['NEWS_INGESTION_ENABLED'] == 'true'
    assert env['PUSH_DELIVERY_ENABLED'] == 'false'


def test_push_requires_isolated_existing_service_account(values, tmp_path):
    provider = {'GEMINI_API_KEY': 'gemini-test', 'AZURE_SPEECH_KEY': 'azure-test',
                'AZURE_SPEECH_REGION': 'southeastasia', 'AZURE_SPEECH_VOICE': 'my-MM-NilarNeural'}
    credential = tmp_path / 'firebase.json'
    credential.write_text('{}')
    env = launcher.child_environment(values, 'backend', provider_values=provider,
        push_values={'FIREBASE_SERVICE_ACCOUNT_PATH': str(credential)}, enable_generation=True,
        enable_automation=True, enable_push=True)
    assert env['PUSH_DELIVERY_ENABLED'] == 'true'
    assert env['FIREBASE_SERVICE_ACCOUNT_PATH'] == str(credential)


def test_mobile_public_feature_flags_are_explicit(values):
    env = launcher.child_environment(values, 'mobile', 'http://10.0.2.2:8000',
                                     enable_push=True, enable_ads=True)
    assert env['EXPO_PUBLIC_PUSH_ENABLED'] == 'true'
    assert env['EXPO_PUBLIC_ADS_ENABLED'] == 'true'


@pytest.mark.parametrize('key,value', [
    ('SUPABASE_URL', 'https://source.supabase.co'), ('INGESTION_OPERATOR_IDS', 'unexpected-operator'),
    ('ACCOUNT_DELETION_ENABLED', 'true'), ('ACCOUNT_DELETION_WORKER_ENABLED', 'true'), ('SCHEDULER_ENABLED', 'true'), ('AUTOMATIC_BRIEFING_PREFERENCES_ENABLED', 'true'), ('NEWS_INGESTION_ENABLED', 'true'), ('PUSH_DELIVERY_ENABLED', 'true'), ('FIREBASE_SERVICE_ACCOUNT_PATH', '/secret.json'),
    ('SUPABASE_PUBLISHABLE_KEY', 'sb_secret_wrong-key'),
])
def test_launcher_refuses_source_or_enabled_providers(values, key, value):
    values[key] = value
    with pytest.raises(ValueError):
        launcher.child_environment(values, 'backend')


@pytest.mark.parametrize('url', [
    'https://production.example:443', 'http://8.8.8.8:8000', 'http://user:password@localhost:8000',
    'http://localhost:8000/private', 'http://localhost:8000?key=private', 'http://0.0.0.0:8000',
])
def test_mobile_refuses_nonlocal_or_credential_bearing_api_url(values, url):
    with pytest.raises(ValueError):
        launcher.child_environment(values, 'mobile', url)


@pytest.mark.parametrize('mode', ['backend', 'mobile'])
def test_stored_provider_secrets_are_preserved_but_not_forwarded(values, mode, capsys):
    for key in launcher.PROVIDER_KEYS:
        values[key] = 'private-fixture-' + key
    before = dict(values)
    env = launcher.child_environment(values, mode, 'http://10.0.2.2:8000',
        inherited={key: 'inherited-private-fixture' for key in launcher.PROVIDER_KEYS})
    assert values == before
    assert all(not env.get(key) for key in launcher.PROVIDER_KEYS)
    assert not any('private-fixture' in value for value in env.values())
    assert capsys.readouterr().out == ''


def test_unknown_launch_mode_fails_closed(values):
    with pytest.raises(ValueError):
        launcher.child_environment(values, 'ai')
