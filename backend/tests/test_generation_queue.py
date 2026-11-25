from types import SimpleNamespace
from unittest.mock import Mock

from app.services import generation_queue
from app.services.briefing.jobs import GenerationLimited


def test_manual_trial_request_forces_fresh_audio_with_idempotency_key(monkeypatch):
    job = {
        'id': 'job-id', 'user_id': 'owner', 'briefing_date': '2026-11-23',
        'request_key': 'category-change-request', 'length': 'standard',
        'lease_token': 'lease-token',
    }
    database = Mock()
    database.rpc.return_value.execute.side_effect = [
        SimpleNamespace(data=job),
        SimpleNamespace(data=True),
        SimpleNamespace(data=True),
    ]
    generate = Mock(return_value=({'id': 'briefing-id'}, True))
    monkeypatch.setattr(generation_queue, 'admin_supabase', database)
    monkeypatch.setattr(generation_queue, 'collect_user_news', lambda _user: [{'stories': [{'title': 'Fresh'}]}])
    monkeypatch.setattr(generation_queue, 'get_trial', lambda _user: {'entitlement_kind': 'trial'})
    monkeypatch.setattr(generation_queue, 'generate_and_save', generate)

    assert generation_queue.process_one_request() is True
    assert generate.call_args.kwargs['regeneration_id'] == 'category-change-request'
    assert database.rpc.call_args.args[0] == 'finish_briefing_request'


def test_daily_limit_is_reported_as_a_specific_request_failure(monkeypatch):
    job = {
        'id': 'job-id', 'user_id': 'owner', 'briefing_date': '2026-11-23',
        'request_key': 'category-change-request', 'length': 'standard',
        'lease_token': 'lease-token',
    }
    database = Mock()
    database.rpc.return_value.execute.side_effect = [
        SimpleNamespace(data=job),
        SimpleNamespace(data=True),
        SimpleNamespace(data=True),
    ]
    monkeypatch.setattr(generation_queue, 'admin_supabase', database)
    monkeypatch.setattr(generation_queue, 'collect_user_news', lambda _user: [{'stories': [{'title': 'Fresh'}]}])
    monkeypatch.setattr(generation_queue, 'get_trial', lambda _user: {'entitlement_kind': 'trial'})
    monkeypatch.setattr(generation_queue, 'generate_and_save', Mock(side_effect=GenerationLimited()))

    assert generation_queue.process_one_request() is True
    name, params = database.rpc.call_args.args
    assert name == 'fail_briefing_request'
    assert params['p_error_code'] == 'generation_limit_reached'
