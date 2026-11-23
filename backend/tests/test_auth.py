import base64
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from supabase_auth.errors import AuthApiError

from app.dependencies import auth
from app.main import app

USER_ID = "11111111-1111-4111-8111-111111111111"


def verified_user(user_id=USER_ID, anonymous=False):
    return {"claims": {"sub": user_id, "is_anonymous": anonymous}}


def token_with_expiry(expiry: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": expiry}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature-for-test-only"


def test_missing_authorization_is_classified_without_calling_auth(monkeypatch, caplog):
    get_claims = Mock(side_effect=AssertionError("missing header must stop before Supabase"))
    monkeypatch.setattr(auth.admin_supabase.auth, "get_claims", get_claims)
    with TestClient(app) as client:
        response = client.get("/api/v1/news?limit=3", headers={"X-Request-ID": "auth-missing-1"})
    assert response.status_code == 401
    assert "request_id=auth-missing-1" in caplog.text
    assert "route=/api/v1/news" in caplog.text
    assert "category=missing_authorization" in caplog.text
    get_claims.assert_not_called()


@pytest.mark.parametrize("expiry,state", [(int(time.time()) - 30, "expired"), (int(time.time()) + 3600, "valid")])
def test_supabase_invalid_token_stays_401_and_logs_only_expiry_state(monkeypatch, caplog, expiry, state):
    token = token_with_expiry(expiry)
    monkeypatch.setattr(auth.admin_supabase.auth, "get_claims", Mock(side_effect=AuthApiError("private server message", 401, None)))
    with TestClient(app) as client:
        response = client.get("/api/v1/news?limit=3", headers={
            "Authorization": f"Bearer {token}", "X-Request-ID": "auth-reject-2",
        })
    assert response.status_code == 401
    assert f"category=token_rejected" in caplog.text
    assert f"token_expiry={state}" in caplog.text
    assert "auth-reject-2" in caplog.text
    assert token not in caplog.text
    assert "private server message" not in caplog.text


@pytest.mark.parametrize("failure", [
    httpx.ConnectError("private connection detail"),
    AuthApiError("private provider detail", 503, None),
])
def test_auth_provider_failures_are_503_not_false_401(monkeypatch, caplog, failure):
    monkeypatch.setattr(auth.admin_supabase.auth, "get_claims", Mock(side_effect=failure))
    token = token_with_expiry(int(time.time()) + 3600)
    with TestClient(app) as client:
        response = client.get("/api/v1/news?limit=3", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Authentication service is temporarily unavailable"
    assert "category=auth_provider_unavailable" in caplog.text
    assert "private connection detail" not in caplog.text
    assert "private provider detail" not in caplog.text
    assert token not in caplog.text


def test_valid_supabase_user_continues_to_account_and_route(monkeypatch):
    from app.routes import users
    monkeypatch.setattr(users, "AUTOMATIC_BRIEFING_PREFERENCES_ENABLED", False)
    monkeypatch.setattr(auth.admin_supabase.auth, "get_claims", lambda _token: verified_user())
    monkeypatch.setattr(auth, "account_is_active", lambda _user_id: True)

    db = Mock()
    db.table.return_value = db
    db.select.return_value = db
    db.eq.return_value = db
    db.limit.return_value = db
    db.execute.return_value = SimpleNamespace(data=[{
        "id": USER_ID, "name": None, "timezone": "Asia/Yangon",
        "delivery_hour": 7, "delivery_minute": 0, "subscription_status": "free",
    }])
    monkeypatch.setattr("app.routes.users.create_supabase_client", lambda _token: db)
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me/preferences", headers={
            "Authorization": f"Bearer {token_with_expiry(int(time.time()) + 3600)}",
            "X-Request-ID": "auth-valid-3",
        })
    assert response.status_code == 200
    assert response.json()["profile"]["automatic_delivery_preferences_available"] is False
    assert response.json()["profile"]["daily_reminder_enabled"] is False
    assert "daily_reminder_enabled" not in db.select.call_args.args[0]


def test_profile_update_is_scoped_to_authenticated_owner(monkeypatch):
    from app.routes import users
    monkeypatch.setattr(auth.admin_supabase.auth, "get_claims", lambda _token: verified_user())
    monkeypatch.setattr(auth, "account_is_active", lambda _user_id: True)
    db = Mock()
    db.table.return_value = db
    db.update.return_value = db
    db.eq.return_value = db
    db.execute.return_value = SimpleNamespace(data=[{
        "id": "11111111-1111-4111-8111-111111111111", "name": "Nikki",
        "phone_number": "+959123456789", "avatar_path": None,
    }])
    monkeypatch.setattr(users, "create_supabase_client", lambda _token: db)
    with TestClient(app) as client:
        response = client.put("/api/v1/users/me/profile", json={
            "name": "  Nikki  ", "phone_number": "+959123456789",
        }, headers={"Authorization": f"Bearer {token_with_expiry(int(time.time()) + 3600)}"})
    assert response.status_code == 200
    assert db.update.call_args.args[0] == {"name": "Nikki", "phone_number": "+959123456789"}
    db.eq.assert_called_with("id", "11111111-1111-4111-8111-111111111111")


def test_profile_rejects_another_users_avatar_path(monkeypatch):
    monkeypatch.setattr(auth.admin_supabase.auth, "get_claims", lambda _token: verified_user())
    monkeypatch.setattr(auth, "account_is_active", lambda _user_id: True)
    with TestClient(app) as client:
        response = client.put("/api/v1/users/me/profile", json={
            "avatar_path": "22222222-2222-4222-8222-222222222222/1795250917598-22222222-2222-4222-8222-222222222222.jpg",
        }, headers={"Authorization": f"Bearer {token_with_expiry(int(time.time()) + 3600)}"})
    assert response.status_code == 422


def test_transient_read_error_recovers_without_accepting_unverified_token(monkeypatch, caplog):
    import asyncio
    user = verified_user()
    remote = Mock(side_effect=[httpx.ReadError('secret network details'), user])
    monkeypatch.setattr(auth.admin_supabase.auth, 'get_claims', remote)
    result = asyncio.run(auth._verify_shared('private-token', 'retry-test', '/api/v1/news', 'valid'))
    assert result is user and remote.call_count == 2
    assert 'transport_category=network_read_failure' in caplog.text
    assert 'private-token' not in caplog.text and 'secret network details' not in caplog.text


def test_persistent_read_error_is_bounded_and_returns_503(monkeypatch, caplog):
    remote = Mock(side_effect=httpx.ReadError('private transport details'))
    monkeypatch.setattr(auth.admin_supabase.auth, 'get_claims', remote)
    with TestClient(app) as client:
        response = client.get('/api/v1/news', headers={'Authorization': 'Bearer private-token'})
    assert response.status_code == 503 and remote.call_count == 2
    assert 'network_read_failure' in caplog.text and 'private-token' not in caplog.text


def test_concurrent_requests_share_auth_and_account_checks(monkeypatch):
    import asyncio
    import threading
    from starlette.requests import Request
    started, release = threading.Event(), threading.Event()
    def verify(token):
        started.set()
        assert release.wait(2)
        return verified_user()
    remote = Mock(side_effect=verify)
    active = Mock(return_value=True)
    monkeypatch.setattr(auth.admin_supabase.auth, 'get_claims', remote)
    monkeypatch.setattr(auth, 'account_is_active', active)
    async def scenario():
        async def request():
            req = Request({'type': 'http', 'path': '/api/v1/news', 'headers': []})
            verified = await auth.get_verified_user(req, 'Bearer shared-token')
            return await auth.get_current_user(verified)
        tasks = [asyncio.create_task(request()) for _ in range(8)]
        assert await asyncio.to_thread(started.wait, 2)
        release.set()
        results = await asyncio.gather(*tasks)
        assert len(results) == 8 and remote.call_count == 1 and active.call_count == 1
        # A later request reuses both short-lived successful checks.
        remote.side_effect = AuthApiError('revoked', 401, None)
        assert (await request())['user_id'] == USER_ID
        assert remote.call_count == 1 and active.call_count == 1

        # Once the cache is unavailable/expired, Auth is authoritative again.
        auth._verification_cache.get(asyncio.get_running_loop(), {}).clear()
        with pytest.raises(auth.HTTPException) as rejected:
            await request()
        assert rejected.value.status_code == 401 and remote.call_count == 2
    asyncio.run(scenario())


def test_concurrent_failed_requests_share_one_bounded_retry(monkeypatch):
    import asyncio
    remote = Mock(side_effect=httpx.ReadError('failure'))
    monkeypatch.setattr(auth.admin_supabase.auth, 'get_claims', remote)
    async def scenario():
        results = await asyncio.gather(*[
            auth._verify_shared('same-token', 'request', '/api/v1/news', 'valid') for _ in range(10)
        ], return_exceptions=True)
        assert all(isinstance(result, httpx.ReadError) for result in results)
        assert remote.call_count == 2
    asyncio.run(scenario())


def test_invalid_tokens_and_pool_exhaustion_are_not_retried(monkeypatch):
    import asyncio
    for error in (AuthApiError('invalid', 401, None), httpx.PoolTimeout('busy')):
        remote = Mock(side_effect=error)
        monkeypatch.setattr(auth.admin_supabase.auth, 'get_claims', remote)
        with pytest.raises(type(error)):
            asyncio.run(auth._verify_shared('token', 'request', '/news', 'expired'))
        assert remote.call_count == 1


def test_one_cancelled_waiter_does_not_cancel_other_verification(monkeypatch):
    import asyncio
    import threading
    started, release = threading.Event(), threading.Event()
    result = verified_user()
    def verify(_token):
        started.set()
        assert release.wait(2)
        return result
    monkeypatch.setattr(auth.admin_supabase.auth, 'get_claims', verify)
    async def scenario():
        first = asyncio.create_task(auth._verify_shared('token', 'one', '/news', 'valid'))
        second = asyncio.create_task(auth._verify_shared('token', 'two', '/news', 'valid'))
        assert await asyncio.to_thread(started.wait, 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert await second is result
    asyncio.run(scenario())


def test_different_tokens_never_share_verified_identity(monkeypatch):
    import asyncio
    remote = Mock(side_effect=lambda token: verified_user(USER_ID if token == 'account-a-token' else '22222222-2222-4222-8222-222222222222'))
    monkeypatch.setattr(auth.admin_supabase.auth, 'get_claims', remote)
    async def scenario():
        results = await asyncio.gather(
            auth._verify_shared('account-a-token', 'a', '/news', 'valid'),
            auth._verify_shared('account-b-token', 'b', '/news', 'valid'))
        assert [response['claims']['sub'] for response in results] == [USER_ID, '22222222-2222-4222-8222-222222222222']
        assert remote.call_count == 2
    asyncio.run(scenario())


def test_verification_capacity_rejects_new_tokens_without_extra_provider_calls(monkeypatch):
    import asyncio
    import threading
    started, release = threading.Event(), threading.Event()
    monkeypatch.setattr(auth, 'MAX_INFLIGHT_VERIFICATIONS', 1)
    def verify(_token):
        started.set()
        assert release.wait(2)
        return verified_user()
    remote = Mock(side_effect=verify)
    monkeypatch.setattr(auth.admin_supabase.auth, 'get_claims', remote)
    async def scenario():
        first = asyncio.create_task(auth._verify_shared('token-a', 'a', '/news', 'valid'))
        assert await asyncio.to_thread(started.wait, 2)
        try:
            with pytest.raises(httpx.PoolTimeout):
                await auth._verify_shared('token-b', 'b', '/news', 'valid')
            assert remote.call_count == 1
        finally:
            release.set()
            await first
    asyncio.run(scenario())
