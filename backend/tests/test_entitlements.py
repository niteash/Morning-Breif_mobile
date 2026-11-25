from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest

from app.routes.entitlements import run
from app.services import entitlements


class DatabaseError(Exception):
    def __init__(self, code):
        super().__init__('redacted database failure')
        self.code = code


@pytest.mark.parametrize('code,category', [
    ('PGRST202', 'migration_missing'), ('PGRST205', 'migration_missing'),
    ('42P01', 'migration_missing'), ('42883', 'migration_missing'),
    ('42501', 'permission_denied'), ('08006', 'database_unavailable'),
])
def test_missing_objects_permissions_and_database_failures_are_classified_safely(monkeypatch, caplog, code, category):
    fake = SimpleNamespace(rpc=lambda *_args, **_kwargs: SimpleNamespace(
        execute=lambda: (_ for _ in ()).throw(DatabaseError(code))))
    monkeypatch.setattr(entitlements, 'admin_supabase', fake)
    with pytest.raises(entitlements.EntitlementUnavailable) as raised:
        entitlements._read('get_account_trial', 'private-user-id')
    assert raised.value.category == category
    assert 'Entitlement RPC failed diagnostics=' in caplog.text
    assert code in caplog.text
    assert 'private-user-id' not in caplog.text
    assert 'redacted database failure' not in caplog.text


def test_malformed_database_code_is_sanitized_and_log_format_is_valid(monkeypatch, caplog):
    secret_like_code = 'private credential value'
    fake = SimpleNamespace(rpc=lambda *_args, **_kwargs: SimpleNamespace(
        execute=lambda: (_ for _ in ()).throw(DatabaseError(secret_like_code))))
    monkeypatch.setattr(entitlements, 'admin_supabase', fake)
    with pytest.raises(entitlements.EntitlementUnavailable) as raised:
        entitlements._read('get_account_trial', 'private-user-id')
    assert raised.value.category == 'database_unavailable'
    assert "'db_code': 'none'" in caplog.text
    assert secret_like_code not in caplog.text
    assert 'private-user-id' not in caplog.text
    assert 'Logging error' not in caplog.text


def test_route_returns_migration_specific_503_without_leaking_database_details():
    def missing(_user_id):
        raise entitlements.EntitlementUnavailable('Trial database migration is not installed', 'migration_missing')
    with pytest.raises(Exception) as raised:
        import asyncio
        asyncio.run(run(missing, {'user_id': 'private-user-id'}))
    assert getattr(raised.value, 'status_code', None) == 503
    assert 'migration is not installed' in raised.value.detail
    assert 'private-user-id' not in raised.value.detail


def test_success_response_requires_valid_server_status_and_never_infers_trial_access(monkeypatch):
    payload = {'status': 'claim_required', 'started_at': None, 'expires_at': None,
               'server_now': '2026-11-14T00:00:00Z', 'grant_scope': None}
    monkeypatch.setattr(entitlements, '_read', lambda *_: dict(payload))
    monkeypatch.setattr(entitlements, 'staging_claim_enabled', lambda: False)
    result = entitlements.get_trial('user')
    assert result['status'] == 'claim_unavailable'
    assert result['can_generate'] is False
    assert result['claim_mode'] == 'device_required'


def test_active_trial_response_requires_server_expiry_and_scope(monkeypatch):
    payload = {'status': 'trial_active', 'started_at': '2026-01-01T00:00:00Z',
               'expires_at': '2026-04-01T00:00:00Z', 'server_now': '2026-02-01T00:00:00Z',
               'grant_scope': 'staging_account'}
    monkeypatch.setattr(entitlements, 'admin_supabase', SimpleNamespace(rpc=lambda *_a, **_k:
        SimpleNamespace(execute=lambda: SimpleNamespace(data=payload))))
    monkeypatch.setattr(entitlements, 'is_staging', lambda: True)
    result = entitlements.get_trial('user')
    assert result['status'] == 'trial_active'
    assert result['can_generate'] is True
    assert result['expires_at'] == payload['expires_at']


def test_verified_purchase_overrides_expired_trial(monkeypatch):
    payload = {'status': 'trial_ended', 'started_at': '2026-01-01T00:00:00Z',
               'expires_at': '2026-04-01T00:00:00Z', 'server_now': '2026-11-01T00:00:00Z',
               'grant_scope': 'android_device'}
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    monkeypatch.setattr(entitlements, '_read', lambda *_: dict(payload))
    monkeypatch.setenv('REVENUECAT_API_KEY', 'server-secret')
    monkeypatch.setenv('REVENUECAT_ENTITLEMENT_ID', 'premium')
    response = SimpleNamespace(status_code=200, json=lambda: {'subscriber': {'entitlements': {
        'premium': {'expires_date': expires, 'grace_period_expires_date': None, 'refunded_at': None}
    }}})
    monkeypatch.setattr(entitlements.requests, 'get', lambda *args, **kwargs: response)
    result = entitlements.get_trial('user-id')
    assert result['status'] == 'subscription_active'
    assert result['can_generate'] is True
    assert result['entitlement_kind'] == 'purchase'


def test_billing_outage_fails_closed_without_active_trial(monkeypatch):
    payload = {'status': 'trial_ended', 'started_at': '2026-01-01T00:00:00Z',
               'expires_at': '2026-04-01T00:00:00Z', 'server_now': '2026-11-01T00:00:00Z',
               'grant_scope': 'android_device'}
    monkeypatch.setattr(entitlements, '_read', lambda *_: dict(payload))
    monkeypatch.setenv('REVENUECAT_API_KEY', 'server-secret')
    monkeypatch.setattr(entitlements.requests, 'get', lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(entitlements.EntitlementUnavailable) as raised:
        entitlements.require_generation_access('user-id')
    assert raised.value.category == 'billing_unavailable'


@pytest.mark.parametrize('payload', [
    None, [], {}, {'status': 'unknown', 'server_now': '2026-11-14T00:00:00Z'},
    {'status': 'trial_active', 'server_now': '2026-11-14T00:00:00Z'},
    {'status': 'claim_required', 'server_now': 'not-a-date'},
    {'status': 'claim_required', 'server_now': '2026-11-14T00:00:00'},
    {'status': 'claim_required', 'server_now': '2026-11-14T00:00:00Z', 'grant_scope': 'android_device'},
    {'status': 'trial_active', 'server_now': '2026-04-01T00:00:00Z', 'started_at': '2026-01-01T00:00:00Z',
     'expires_at': '2026-04-01T00:00:00Z', 'grant_scope': 'android_device'},
])
def test_malformed_or_inconsistent_entitlement_fails_closed(monkeypatch, payload):
    monkeypatch.setattr(entitlements, 'admin_supabase', SimpleNamespace(rpc=lambda *_a, **_k:
        SimpleNamespace(execute=lambda: SimpleNamespace(data=payload))))
    with pytest.raises(entitlements.EntitlementUnavailable) as raised:
        entitlements.require_generation_access('user')
    assert raised.value.category == 'invalid_response'


def test_unclaimed_account_returns_200_without_granting_and_generation_is_denied(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies.auth import get_current_user

    calls = []
    def rpc(name, _args):
        calls.append(name)
        assert name == 'get_account_trial'  # A read/disabled claim must never run the grant RPC.
        return SimpleNamespace(execute=lambda: SimpleNamespace(data={
            'status': 'claim_required', 'server_now': '2026-11-14T18:00:00Z',
            'started_at': None, 'expires_at': None, 'grant_scope': None,
        }))
    monkeypatch.setattr(entitlements, 'admin_supabase', SimpleNamespace(rpc=rpc))
    monkeypatch.setattr(entitlements, 'staging_claim_enabled', lambda: False)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: {'user_id': 'offline-user'})
    with TestClient(app) as client:
        response = client.get('/api/v1/entitlements/me')
        assert response.status_code == 200
        assert response.json() == {
            'status': 'claim_unavailable', 'server_now': '2026-11-14T18:00:00Z',
            'started_at': None, 'expires_at': None, 'grant_scope': None,
            'can_generate': False, 'claim_mode': 'device_required', 'reason': 'device_verification_unavailable',
        }
        assert client.post('/api/v1/entitlements/claim').json()['can_generate'] is False
    with pytest.raises(entitlements.TrialAccessDenied):
        entitlements.require_generation_access('offline-user')
    assert calls == ['get_account_trial'] * 3
