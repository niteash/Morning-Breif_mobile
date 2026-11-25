import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from firebase_admin import messaging

from app.services import notification_delivery as worker
from app.services import push_notifications as push

JOB = {'id': 'delivery-id', 'lease_token': 'lease', 'fcm_token': 'private-device-token', 'briefing_id': 'briefing-id', 'briefing_date': '2026-11-09',
       'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}


@pytest.mark.parametrize('result', ['sent', 'retry', 'invalid'])
def test_delivery_acknowledges_exact_lease_and_outcome(monkeypatch, result):
    db = Mock()
    db.rpc.return_value.execute.side_effect = [SimpleNamespace(data=JOB), SimpleNamespace(data=True)]
    monkeypatch.setattr(worker, 'admin_supabase', db)
    send = Mock(return_value=result)
    monkeypatch.setattr(worker, 'send_briefing_notification', send)
    assert worker.deliver_one() is True
    assert send.call_args.args[:4] == (JOB['fcm_token'], JOB['briefing_id'], JOB['briefing_date'], JOB['id'])
    assert 0 < send.call_args.args[4] <= 3600
    assert db.rpc.call_args.args == ('finish_notification_delivery', {
        'p_id': JOB['id'], 'p_lease_token': JOB['lease_token'], 'p_outcome': result,
    })


def test_missing_configuration_never_claims_or_consumes_attempts(monkeypatch):
    monkeypatch.setattr(worker, 'initialize_firebase', lambda: False)
    claim = Mock(side_effect=AssertionError('must not claim'))
    monkeypatch.setattr(worker, 'deliver_one', claim)
    asyncio.run(worker.deliver_pending_notifications())
    claim.assert_not_called()


def test_failed_acknowledgement_leaves_lease_for_database_recovery(monkeypatch, caplog):
    monkeypatch.setattr(worker, 'initialize_firebase', lambda: True)
    db = Mock()
    def rpc(name, params):
        if name == 'claim_notification_delivery':
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=JOB))
        return SimpleNamespace(execute=Mock(side_effect=RuntimeError('secret-provider-body')))
    db.rpc.side_effect = rpc
    monkeypatch.setattr(worker, 'admin_supabase', db)
    monkeypatch.setattr(worker, 'send_briefing_notification', Mock(return_value='sent'))
    asyncio.run(worker.deliver_pending_notifications())
    assert db.rpc.call_count == worker.WORKERS * 2
    assert 'secret-provider-body' not in caplog.text


def test_worker_bounds_claims_per_tick(monkeypatch):
    monkeypatch.setattr(worker, 'initialize_firebase', lambda: True)
    deliver = Mock(return_value=True)
    monkeypatch.setattr(worker, 'deliver_one', deliver)
    asyncio.run(worker.deliver_pending_notifications())
    assert deliver.call_count == worker.WORKERS * worker.CLAIMS_PER_WORKER


@pytest.mark.parametrize('error,expected', [
    (None, 'sent'), (messaging.UnregisteredError('private-token'), 'invalid'),
    (messaging.SenderIdMismatchError('private-project'), 'retry'),
    (RuntimeError('private-response'), 'retry'),
])
def test_firebase_outcomes_and_stable_notification_identity(monkeypatch, caplog, error, expected):
    monkeypatch.setattr(push, 'initialize_firebase', lambda: True)
    send = Mock(side_effect=error)
    monkeypatch.setattr(push.messaging, 'send', send)
    assert push.send_briefing_notification('private-token', 'briefing-id', '2026-11-09', 'delivery-id', 3600) == expected
    message = send.call_args.args[0]
    assert message.data['notification_id'] == 'delivery-id'
    assert message.data['briefing_id'] == 'briefing-id'
    assert 'နေ့သစ်' in message.notification.title
    assert 'မိနစ်အနည်းငယ်' in message.notification.body
    assert message.android.notification.tag == 'delivery-id'
    assert message.android.collapse_key == 'delivery-id'
    assert message.android.ttl == 3600
    assert 'private-' not in caplog.text


def test_push_scheduler_is_independent(monkeypatch):
    from app.services import scheduler
    engine = Mock(running=False)
    monkeypatch.setattr(scheduler, 'scheduler', engine)
    scheduler.start_scheduler(push_enabled=True)
    assert [call.kwargs['id'] for call in engine.add_job.call_args_list] == ['morning_brief_push_delivery']


def test_expired_delivery_is_not_sent_to_firebase(monkeypatch):
    db = Mock()
    expired = {**JOB, 'expires_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
    db.rpc.return_value.execute.side_effect = [SimpleNamespace(data=expired), SimpleNamespace(data=True)]
    monkeypatch.setattr(worker, 'admin_supabase', db)
    send = Mock()
    monkeypatch.setattr(worker, 'send_briefing_notification', send)
    worker.deliver_one()
    send.assert_not_called()
    assert db.rpc.call_args.args[1]['p_outcome'] == 'retry'
