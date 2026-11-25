from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.services.briefing import jobs
from app.services.entitlements import TrialAccessDenied, EntitlementUnavailable
from app.services.scheduler import is_delivery_due
from datetime import datetime, timezone

CATEGORIES = [{"stories": [{"title": "News"}]}]


@pytest.fixture(autouse=True)
def staging_trial(monkeypatch):
    # These tests isolate generation coordination after a successful trial gate.
    monkeypatch.setenv("BRIEFING_SOURCES_ENABLED", "false")
    monkeypatch.setattr(jobs, 'require_generation_access', lambda user_id: None)
    monkeypatch.setattr(jobs, 'generation_disabled', lambda: False)

@pytest.mark.parametrize('outcome,error', [
    ('busy', jobs.GenerationBusy), ('limited', jobs.GenerationLimited),
    ('unexpected', jobs.GenerationUnavailable),
])
def test_rejected_claim_never_calls_paid_services(monkeypatch, outcome, error):
    db = Mock()
    db.rpc.return_value.execute.return_value = SimpleNamespace(data={'outcome': outcome})
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    generate = Mock()
    monkeypatch.setattr(jobs, 'generate_combined_audio', generate)
    with pytest.raises(error): jobs.generate_and_save('owner', '2026-11-08', CATEGORIES)
    generate.assert_not_called()


def test_missing_rpc_fails_before_paid_work(monkeypatch):
    db = Mock()
    db.rpc.side_effect = RuntimeError('missing migration')
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    generate = Mock()
    monkeypatch.setattr(jobs, 'generate_combined_audio', generate)
    with pytest.raises(jobs.GenerationUnavailable): jobs.generate_and_save('owner', '2026-11-08', CATEGORIES)
    generate.assert_not_called()


def test_ready_claim_returns_existing_without_generation(monkeypatch):
    saved = {'id': 'existing', 'status': 'ready'}
    db = Mock()
    db.rpc.return_value.execute.return_value = SimpleNamespace(data={'outcome':'ready','briefing':saved})
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    generate = Mock()
    monkeypatch.setattr(jobs, 'generate_combined_audio', generate)
    assert jobs.generate_and_save('owner', '2026-11-08', CATEGORIES) == (saved, False)
    generate.assert_not_called()


@pytest.mark.parametrize('failure', ['provider', 'lease', 'none'])
def test_claim_token_follows_completion_and_failure(monkeypatch, failure):
    db = Mock()
    saved = {'id':'saved','status':'ready'}
    db.rpc.return_value.execute.side_effect = [
        SimpleNamespace(data={'outcome':'claimed','token':'owned-token'}),
        SimpleNamespace(data=None if failure == 'lease' else saved),
        SimpleNamespace(data=True),
    ]
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    generator = Mock(return_value={'script':'news','audio_url':'owner/date/file.mp3','duration_seconds':42})
    if failure == 'provider': generator.side_effect = RuntimeError('provider failed')
    monkeypatch.setattr(jobs, 'generate_combined_audio', generator)
    if failure != 'none':
        with pytest.raises((RuntimeError, jobs.LostGenerationLease)):
            jobs.generate_and_save('owner','2026-11-08',CATEGORIES)
        assert db.rpc.call_args.args[0] == 'fail_briefing_v2'
    else:
        assert jobs.generate_and_save('owner','2026-11-08',CATEGORIES) == (saved, True)
        assert db.rpc.call_args.args[0] == 'finish_briefing_v2'
    assert db.rpc.call_args.args[1]['p_token'] == 'owned-token'


@pytest.mark.parametrize('hour,minute,expected', [(0,0,True),(0,30,True),(1,30,True),(2,1,True),(23,0,False)])
def test_scheduler_catches_delayed_ticks(hour, minute, expected):
    # 06:30 Yangon is 00:00 UTC.
    profile = {'id':'user','timezone':'Asia/Yangon','delivery_hour':6,'delivery_minute':30}
    now = datetime(2026,11,8,hour,minute,tzinfo=timezone.utc)
    assert is_delivery_due(profile,now) is expected


def test_preparation_starts_thirty_minutes_before_delivery():
    profile = {'id':'user','timezone':'Asia/Yangon','delivery_hour':6,'delivery_minute':30}
    assert is_delivery_due(profile, datetime(2026,11,7,23,30,tzinfo=timezone.utc))
    assert not is_delivery_due(profile, datetime(2026,11,7,23,29,tzinfo=timezone.utc))


def test_midnight_delivery_prepares_the_correct_local_briefing_date():
    from app.services.scheduler import delivery_due_at
    profile = {'id': 'user', 'timezone': 'Asia/Yangon', 'delivery_hour': 0,
               'delivery_minute': 15, 'delivery_schedule': 'daily'}
    now = datetime(2026, 11, 15, 17, 15, tzinfo=timezone.utc)  # 23:45 Yangon
    due = delivery_due_at(profile, now)
    assert due is not None
    assert due.date().isoformat() == '2026-11-16'


def test_weekday_schedule_skips_weekends_but_allows_weekday_preparation():
    profile = {'id': 'user', 'timezone': 'America/New_York', 'delivery_hour': 7,
               'delivery_minute': 0, 'delivery_schedule': 'weekdays'}
    # Monday 06:30 EST starts preparation 30 minutes before 07:00.
    monday = datetime(2026, 11, 16, 11, 30, tzinfo=timezone.utc)
    assert is_delivery_due(profile, monday)
    saturday = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    assert not is_delivery_due(profile, saturday)


def test_timezone_dst_offset_is_respected_for_preparation_window():
    profile = {'id': 'user', 'timezone': 'America/New_York', 'delivery_hour': 7,
               'delivery_minute': 0, 'delivery_schedule': 'daily'}
    winter_early = datetime(2026, 1, 15, 11, 30, tzinfo=timezone.utc)  # 06:30 EST
    summer_early = datetime(2026, 7, 15, 10, 30, tzinfo=timezone.utc)  # 06:30 EDT
    assert is_delivery_due(profile, winter_early)
    assert is_delivery_due(profile, summer_early)
    assert not is_delivery_due(profile, winter_early.replace(hour=10))


@pytest.mark.parametrize('error', [TrialAccessDenied('denied'), EntitlementUnavailable()])
def test_entitlement_failure_prevents_claim_and_provider_work(monkeypatch, error):
    db, provider = Mock(), Mock()
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    monkeypatch.setattr(jobs, 'generate_combined_audio', provider)
    monkeypatch.setattr(jobs, 'require_generation_access', Mock(side_effect=error))
    with pytest.raises(type(error)):
        jobs.generate_and_save('owner', '2026-11-15', CATEGORIES)
    db.rpc.assert_not_called()
    provider.assert_not_called()


@pytest.mark.parametrize('schema_ready', [False, None, {}, 'true'])
def test_sources_schema_must_be_ready_before_claim_or_paid_work(monkeypatch, schema_ready):
    monkeypatch.setenv('BRIEFING_SOURCES_ENABLED', 'true')
    db, provider = Mock(), Mock()
    db.rpc.return_value.execute.return_value = SimpleNamespace(data=schema_ready)
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    monkeypatch.setattr(jobs, 'generate_combined_audio', provider)
    with pytest.raises(jobs.GenerationUnavailable):
        jobs.generate_and_save('owner', '2026-11-15', CATEGORIES)
    assert db.rpc.call_count == 1
    assert db.rpc.call_args.args[0] == 'briefing_sources_ready'
    provider.assert_not_called()


def test_sources_finish_uses_same_lease_and_exact_metadata(monkeypatch):
    monkeypatch.setenv('BRIEFING_SOURCES_ENABLED', 'true')
    metadata = {'title': 'နေ့သစ်', 'sections': [], 'script': 'မြန်မာ'}
    saved = {'id': 'saved', 'status': 'ready', 'source_metadata': metadata}
    db = Mock()
    db.rpc.return_value.execute.side_effect = [
        SimpleNamespace(data=True),
        SimpleNamespace(data={'outcome': 'claimed', 'token': 'lease'}),
        SimpleNamespace(data=saved),
    ]
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    monkeypatch.setattr(jobs, 'generate_combined_audio', Mock(return_value={
        'script': 'မြန်မာ', 'audio_url': 'owner/date/test.mp3',
        'duration_seconds': 30, 'source_metadata': metadata,
    }))
    assert jobs.generate_and_save('owner', '2026-11-15', CATEGORIES) == (saved, True)
    name, params = db.rpc.call_args.args
    assert name == 'finish_briefing_with_sources'
    assert params['p_token'] == 'lease'
    assert params['p_metadata'] == metadata
    assert params['p_script'] == metadata['script']


def test_disabled_generation_does_not_claim_or_call_providers(monkeypatch):
    monkeypatch.setattr(jobs, 'generation_disabled', lambda: True)
    db, provider = Mock(), Mock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    monkeypatch.setattr(jobs, 'generate_combined_audio', provider)
    with pytest.raises(jobs.GenerationDisabled):
        jobs.generate_and_save('owner', '2026-11-15', CATEGORIES)
    db.rpc.assert_not_called()
    provider.assert_not_called()


def test_disabled_generation_can_reuse_owned_ready_audio(monkeypatch):
    monkeypatch.setattr(jobs, 'generation_disabled', lambda: True)
    db, provider = Mock(), Mock()
    saved = {'id': 'saved', 'status': 'ready', 'user_id': 'owner'}
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [saved]
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    monkeypatch.setattr(jobs, 'generate_combined_audio', provider)
    assert jobs.generate_and_save('owner', '2026-11-15', CATEGORIES) == (saved, False)
    db.rpc.assert_not_called()
    provider.assert_not_called()


@pytest.mark.parametrize('state,code', [('failed', 'generation_cooldown'), ('generating', 'generation_in_progress')])
def test_busy_status_distinguishes_cooldown_from_processing(monkeypatch, state, code):
    from datetime import timedelta
    db = Mock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {'state': state, 'lease_until': (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()}]
    monkeypatch.setattr(jobs, 'admin_supabase', db)
    detail = jobs.busy_detail('owner', '2026-11-15')
    assert detail['code'] == code
    assert 0 < detail['retry_after_seconds'] <= 60
    db.rpc.assert_not_called()


def test_missing_provider_configuration_fails_closed(monkeypatch):
    # Test the real helper despite the coordination fixture's provider mock.
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('isolated_jobs', jobs.__file__)
    module = module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setenv('BRIEFING_GENERATION_ENABLED', 'true')
    monkeypatch.delenv('AZURE_SPEECH_KEY', raising=False)
    assert module.generation_disabled()
