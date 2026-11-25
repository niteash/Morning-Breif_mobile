from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
import importlib.util

import pytest
from app.services.ai import gemini
from app.services.tts import azure
from app.services.briefing import pipeline
from app.services.briefing.rehearsal import mock_rehearsal, validate_selection, batch_digest

USER = 'e726b864-c879-4b8f-9ac1-c5cb73ae8a58'
CATEGORY = '9f82967b-bc06-4751-86ae-7444570db73f'
NOW = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)


def selection():
    return [{'category': {'id': CATEGORY, 'slug': 'myanmar', 'name_my': 'မြန်မာသတင်း'},
             'stories': [{'id': '11111111-1111-4111-8111-111111111111', 'category_id': CATEGORY,
                          'title': 'Fixture headline', 'description': 'Fixture excerpt',
                          'source': 'Fixture publisher', 'url': 'https://example.org/story',
                          'published_at': NOW.isoformat()}]}]


def runner():
    path = Path(__file__).parents[1] / 'scripts/staging_audio_test.py'
    spec = importlib.util.spec_from_file_location('audio_test_runner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mocked_coordinator_to_audio_to_saved_record():
    categories = selection()
    assert validate_selection(categories, NOW) == {'myanmar': 1}
    result = mock_rehearsal(USER, '2026-11-15', categories)
    assert result['status'] == 'ready'
    assert result['duration_seconds'] == 3
    assert result['paid_calls'] == result['external_writes'] == 0
    assert result['owner_path_valid']


@pytest.mark.parametrize('change', ['expired', 'future', 'duplicate', 'category', 'url', 'source'])
def test_invalid_news_rejected(change):
    data = selection()
    story = data[0]['stories'][0]
    if change == 'expired': story['published_at'] = (NOW - timedelta(hours=25)).isoformat()
    if change == 'future': story['published_at'] = (NOW + timedelta(seconds=1)).isoformat()
    if change == 'duplicate': data[0]['stories'].append(dict(story))
    if change == 'category': story['category_id'] = USER
    if change == 'url': story['url'] = 'file:///tmp/story'
    if change == 'source': story['source'] = ''
    with pytest.raises(ValueError): validate_selection(data, NOW)


def test_changed_news_changes_approval_digest():
    first = selection()
    digest = batch_digest(first)
    first[0]['stories'][0]['description'] = 'Changed excerpt'
    assert batch_digest(first) != digest


@pytest.mark.parametrize('field', ['approve_project', 'approve_user', 'approve_date', 'approve_batch'])
def test_exact_approval_required(field):
    mod = runner()
    args = SimpleNamespace(approve_project=mod.PROJECT, approve_user=USER,
                           approve_date='2026-11-15', approve_batch='reviewed-digest')
    setattr(args, field, 'different')
    with pytest.raises(ValueError): mod.validate_approval(args, 'reviewed-digest', '2026-11-15', {'can_generate': True})


def test_missing_trial_cannot_be_overridden_by_operator_flags():
    mod = runner()
    args = SimpleNamespace(approve_project=mod.PROJECT, approve_user=USER,
                           approve_date='2026-11-15', approve_batch='reviewed')
    with pytest.raises(ValueError): mod.validate_approval(args, 'reviewed', '2026-11-15', {'can_generate': False})


def test_attempt_reservation_is_exclusive_and_survives_failure(tmp_path):
    mod = runner()
    marker = mod.reserve_attempt(tmp_path, '2026-11-15')
    assert marker.exists()
    with pytest.raises(FileExistsError): mod.reserve_attempt(tmp_path, '2026-11-15')


@pytest.mark.parametrize('script', ['', 'English only', 'မ' * 12001, None])
def test_script_validation_rejects_before_tts(script):
    with pytest.raises(RuntimeError): pipeline.validate_script(script)


def test_invalid_owner_never_calls_provider(monkeypatch):
    provider = Mock()
    monkeypatch.setattr(pipeline, 'generate_briefing_script', provider)
    with pytest.raises(ValueError): pipeline.generate_combined_audio('../other', '2026-11-15', selection())
    provider.assert_not_called()


def test_single_attempt_disables_model_fallback(monkeypatch):
    monkeypatch.setenv('BRIEFING_SINGLE_ATTEMPT', 'true')
    call = Mock(side_effect=RuntimeError('secret provider body'))
    monkeypatch.setattr(gemini, '_generate_with_model', call)
    with pytest.raises(RuntimeError, match='operator review') as error:
        gemini.generate_briefing_script(selection())
    assert 'secret' not in str(error.value)
    assert call.call_count == 1


def test_sdk_retry_limit_and_generation_budget(monkeypatch):
    gemini._get_client.cache_clear()
    client = Mock()
    client.models.generate_content.return_value.text = 'မြန်မာသတင်း'
    client.models.generate_content.return_value.candidates = [SimpleNamespace(finish_reason='STOP')]
    constructor = Mock(return_value=client)
    monkeypatch.setattr(gemini.genai, 'Client', constructor)
    try:
        assert gemini._generate_with_model(gemini.PRIMARY_MODEL, 'prompt') == 'မြန်မာသတင်း'
        assert constructor.call_args.kwargs['http_options'].retry_options.attempts == 1
        config = client.models.generate_content.call_args.kwargs['config']
        assert config.max_output_tokens == 8192
        assert config.thinking_config.thinking_budget == 0
    finally: gemini._get_client.cache_clear()


def test_grounded_schema_locks_category_and_story_narration_counts():
    second_category = '22222222-2222-4222-8222-222222222222'
    categories = selection() + [{
        'category': {'id': second_category, 'name_my': 'ကမ္ဘာ'},
        'stories': [{'id': '33333333-3333-4333-8333-333333333333', 'title': 'World story'}],
    }]
    schema = gemini.grounded_response_schema(categories)
    introductions = schema['properties']['category_introductions']
    stories = schema['properties']['story_narrations']
    assert introductions['minItems'] == introductions['maxItems'] == 2
    assert stories['minItems'] == stories['maxItems'] == 2
    assert stories['items'] == {'type': 'string'}


def test_structured_generation_passes_json_schema_to_sdk(monkeypatch):
    client = Mock()
    client.models.generate_content.return_value = SimpleNamespace(
        text='{"title":"နေ့သစ်","sections":[]}',
        candidates=[SimpleNamespace(finish_reason=gemini.types.FinishReason.STOP)],
    )
    monkeypatch.setattr(gemini, '_get_client', lambda: client)
    schema = {'type': 'object', 'properties': {'title': {'type': 'string'}}, 'required': ['title']}
    gemini._generate_with_model(gemini.PRIMARY_MODEL, 'prompt', structured=True,
                                response_json_schema=schema)
    config = client.models.generate_content.call_args.kwargs['config']
    assert config.response_mime_type == 'application/json'
    assert config.response_json_schema == schema


def test_azure_failure_does_not_echo_response_body_or_retry(monkeypatch, tmp_path):
    monkeypatch.setattr(azure, 'AZURE_SPEECH_KEY', 'secret-fixture')
    monkeypatch.setattr(azure, 'AZURE_SPEECH_REGION', 'southeastasia')
    monkeypatch.setattr(azure, 'AZURE_SPEECH_VOICE', 'my-MM-NilarNeural')
    call = Mock(return_value=SimpleNamespace(status_code=403, text='secret-fixture'))
    monkeypatch.setattr(azure.requests, 'post', call)
    with pytest.raises(RuntimeError, match='HTTP 403') as error:
        azure.generate_speech('မြန်မာသတင်း', str(tmp_path / 'test.mp3'))
    assert 'secret-fixture' not in str(error.value)
    assert call.call_count == 1
    assert call.call_args.kwargs['allow_redirects'] is False
    assert call.call_args.kwargs['headers']['X-Microsoft-OutputFormat'] == 'audio-24khz-48kbitrate-mono-mp3'
    assert not (tmp_path / 'test.mp3').exists()


def test_bilingual_ssml_uses_one_burmese_female_voice_and_safe_natural_pacing(monkeypatch):
    monkeypatch.setattr(azure, 'AZURE_SPEECH_VOICE', 'my-MM-NilarNeural')
    ssml = azure.build_ssml('မြန်မာ AI နည်းပညာ & သတင်း။\n\nOpenAI Update')
    assert ssml.count('<voice ') == 1
    assert '<voice name="my-MM-NilarNeural"><prosody rate="-2%" pitch="+1%">' in ssml
    assert ssml.count('<prosody ') == 1
    assert 'volume=' not in ssml
    assert 'အေ အိုင်' in ssml and 'အိုးပင်း အေ အိုင်' in ssml
    assert 'en-US-' not in ssml
    assert '&amp;' in ssml
    assert '<break time="420ms"/>' in azure.build_ssml('မြန်မာသတင်း။\n\nနောက်တစ်ပုဒ်။')


def test_unmapped_english_acronyms_are_spoken_as_myanmar_letter_names():
    ssml = azure.build_ssml('BBC နှင့် NASA သတင်း')
    assert 'ဘီ ဘီ စီ' in ssml
    assert 'အန် အေ အက်စ် အေ' in ssml
    assert 'BBC' not in ssml and 'NASA' not in ssml

def test_azure_usd_currency_is_spoken_in_burmese():
    ssml = azure.build_ssml(
        'ကုမ္ပဏီ၏ ဝင်ငွေမှာ $1,250 ဖြစ်သည်။'
    )

    assert 'အမေရိကန်ဒေါ်လာ' in ssml
    assert 'တစ်ထောင်နှစ်ရာငါးဆယ်' in ssml
    assert '$1,250' not in ssml


def test_bilingual_narration_prompt_is_written_for_spoken_delivery():
    prompt = gemini.build_prompt(selection())
    assert 'Write for speech, not print' in prompt
    assert 'single Myanmar female voice' in prompt
    assert 'Burmese phonetic spelling' in prompt
    assert 'human newsreader should pause' in prompt


def test_runner_dry_run_uses_selection_without_live_generation(monkeypatch):
    from app.lib import supabase as database
    from app.services.briefing import dates, jobs
    from app.services import entitlements
    from app.services.news import selector
    mod = runner()
    values = {'SUPABASE_URL': mod.STAGING_URL, 'SUPABASE_PUBLISHABLE_KEY': 'fixture',
              'SUPABASE_SERVICE_ROLE_KEY': 'fixture', 'RSS_IMPORT_ACCESS_TOKEN': (
                      'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.'
                      'eyJleHAiOjQxMDI0NDQ4MDB9.'
                      'test-signature'
                  )}
    monkeypatch.setattr(mod, 'dotenv_values', lambda path, **kw: values if path.name == '.env.staging' else {})
    client = Mock()
    client.auth.get_user.return_value.user = SimpleNamespace(id=USER, is_anonymous=False)
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    monkeypatch.setattr(database, 'create_supabase_client', lambda token: client)
    monkeypatch.setattr(database, 'admin_supabase', client)
    monkeypatch.setattr(dates, 'get_briefing_date', lambda *args: '2026-11-15')
    monkeypatch.setattr(entitlements, 'get_trial', lambda user: {'can_generate': False, 'status': 'claim_unavailable'})
    data = selection()
    data[0]['stories'][0]['published_at'] = datetime.now(timezone.utc).isoformat()
    async def selected(*args, **kwargs): return data
    monkeypatch.setattr(selector, 'select_recent_stories', selected)
    # The mock rehearsal intentionally calls the real coordinator under isolated ports;
    # verify that live client RPCs and Storage are never touched.
    args = SimpleNamespace(execute=False)
    import os
    import logging
    from unittest.mock import patch
    previous_logging = logging.root.manager.disable
    with patch.dict(os.environ):
        try:
            result = mod.run(args)
        finally:
            logging.disable(previous_logging)
    assert result['counts'] == {'myanmar': 1}
    assert result['can_generate'] is False
    assert result['rehearsal']['paid_calls'] == 0
    assert not mod.STATE['generation_invoked']
    client.rpc.assert_not_called()
    client.storage.from_.assert_not_called()


@pytest.mark.parametrize('reason', ['MAX_TOKENS', 'SAFETY', 'OTHER'])
def test_incomplete_or_blocked_narration_rejected(monkeypatch, reason):
    client = Mock()
    client.models.generate_content.return_value = SimpleNamespace(
        text='မြန်မာသတင်း', candidates=[SimpleNamespace(finish_reason=reason)])
    monkeypatch.setattr(gemini, '_get_client', lambda: client)
    with pytest.raises(RuntimeError, match='blocked or incomplete'):
        gemini._generate_with_model(gemini.PRIMARY_MODEL, 'fixture')
    assert client.models.generate_content.call_count == 1

@pytest.mark.parametrize(
    ('amount', 'expected'),
    [
        ('$0', 'အမေရိကန်ဒေါ်လာ သုည'),
        ('$10', 'အမေရိကန်ဒေါ်လာ ဆယ်'),
        ('$100', 'အမေရိကန်ဒေါ်လာ တစ်ရာ'),
        ('$1,000', 'အမေရိကန်ဒေါ်လာ တစ်ထောင်'),
        ('$9,999', 'အမေရိကန်ဒေါ်လာ ကိုးထောင်ကိုးရာကိုးဆယ်ကိုး'),
        ('$12,500', 'အမေရိကန်ဒေါ်လာ တစ်သောင်းနှစ်ထောင်ငါးရာ'),
        ('$12.50', 'အမေရိကန်ဒေါ်လာ ဆယ်နှစ် ဒသမ ငါး သုည'),
        ('$1,25', '$1,25'),
    ],
)
def test_azure_usd_currency_edge_cases(amount, expected):
    ssml = azure.build_ssml(f'တန်ဖိုး {amount} ဖြစ်သည်။')
    assert expected in ssml


@pytest.mark.parametrize('patch,expected', [
    ({'AZURE_SPEECH_REGION': 'https://wrong.example'}, 'invalid_region_format'),
    ({'AZURE_SPEECH_VOICE': 'en-US-Voice'}, 'unsupported_burmese_voice'),
    ({'GEMINI_API_KEY': ' secret '}, 'surrounding_whitespace'),
    ({'SUPABASE_URL': 'unexpected'}, 'unexpected_provider_file_keys'),
])
def test_provider_readiness_reports_categories_without_values(patch, expected):
    values = {'GEMINI_API_KEY': 'fixture-key', 'AZURE_SPEECH_KEY': 'fixture-speech',
              'AZURE_SPEECH_REGION': 'southeastasia'}
    values.update(patch)
    missing, errors = runner().provider_readiness(values)
    assert expected in errors
    assert 'fixture-key' not in str((missing, errors))


@pytest.mark.parametrize(
    ('amount', 'expected'),
    [
        (
            '၁၅,၀၀၀ ကျပ်',
            'တစ်သောင်းငါးထောင် ကျပ်',
        ),
        (
            '၅၀၀ ကျပ်',
            'ငါးရာ ကျပ်',
        ),
        (
            '25,000 MMK',
            'နှစ်သောင်းငါးထောင် ကျပ်',
        ),
    ],
)
def test_azure_mmk_currency_pronunciation(amount, expected):
    ssml = azure.build_ssml(
        f'ကုန်ကျစရိတ်မှာ {amount} ဖြစ်သည်။'
    )
    assert expected in ssml

@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('50%', 'ငါးဆယ် ရာခိုင်နှုန်း'),
        ('၁၅%', 'တစ်ဆယ့်ငါး ရာခိုင်နှုန်း'),
        ('100%', 'တစ်ရာ ရာခိုင်နှုန်း'),
        ('2.5%', 'နှစ် ဒသမ ငါး ရာခိုင်နှုန်း'),
    ],
)
def test_azure_percentage_pronunciation(value, expected):
    ssml = azure.build_ssml(
        f'တိုးတက်မှုနှုန်းမှာ {value} ဖြစ်သည်။'
    )
    assert expected in ssml

def test_missing_provider_file_reports_exact_required_names():
    missing, errors = runner().provider_readiness({})
    assert missing == ['GEMINI_API_KEY', 'AZURE_SPEECH_KEY', 'AZURE_SPEECH_REGION']
    assert errors == []


def test_supported_provider_configuration_needs_no_explicit_voice():
    assert runner().provider_readiness({'GEMINI_API_KEY': 'fixture',
        'AZURE_SPEECH_KEY': 'fixture', 'AZURE_SPEECH_REGION': 'southeastasia'}) == ([], [])


@pytest.mark.parametrize('token', ['', 'malformed', 'e30.e30.e30'])
def test_expiry_preflight_rejects_missing_malformed_or_unverifiable_tokens(token):
    assert runner().access_token_is_expired(token, now=100)


def test_expiry_preflight_detects_expiry_without_revealing_claims():
    import base64, json
    payload = base64.urlsafe_b64encode(json.dumps({'exp': 99, 'sub': 'private'}).encode()).decode().rstrip('=')
    assert runner().access_token_is_expired('header.' + payload + '.signature', now=100)


def test_grounded_rehearsal_never_calls_real_providers(monkeypatch):
    monkeypatch.setenv('BRIEFING_SOURCES_ENABLED', 'true')
    result = mock_rehearsal(USER, '2026-11-15', selection())
    assert result['status'] == 'ready'
    assert result['paid_calls'] == result['external_writes'] == 0
    assert result['owner_path_valid']


@pytest.mark.parametrize(
    'value',
    [
        '12.50%',
        '12,500%',
        '25,000 MMK',
    ],
)
def test_azure_preserves_unsupported_financial_formats(value):
    ssml = azure.build_ssml(f'တန်ဖိုး {value} ဖြစ်သည်။')

    if value == '12.50%':
        # Supported percentage decimals should be spoken.
        assert 'တစ်ဆယ့်နှစ် ဒသမ ငါး သုည ရာခိုင်နှုန်း' in ssml
    elif value == '25,000 MMK':
        # Supported MMK amounts should be converted.
        assert 'နှစ်သောင်းငါးထောင် ကျပ်' in ssml
    else:
        assert value in ssml
