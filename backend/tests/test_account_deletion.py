import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import app
from app.dependencies import auth
from app.services import account_deletion as deletion
from app.services import storage
from app.routes import account_deletion as routes

USER = str(uuid4())
JOB = {'user_id': USER, 'lease_token': str(uuid4())}


def test_delete_requires_authentication_and_exact_confirmation(monkeypatch):
    monkeypatch.setenv('ACCOUNT_DELETION_ENABLED', 'true')
    request = Mock(return_value={'status': 'requested'})
    monkeypatch.setattr(routes, 'request_deletion', request)
    with TestClient(app) as client:
        assert client.delete('/api/v1/users/me').status_code == 401
        app.dependency_overrides[auth.get_verified_user] = lambda: {'user_id': USER, 'access_token': 'private-token'}
        try:
            for body in [{}, {'confirmation': 'delete'}, {'confirmation': 'DELETE', 'user_id': str(uuid4())}]:
                assert client.request('DELETE', '/api/v1/users/me', json=body).status_code == 422
            request.assert_not_called()
            result = client.request('DELETE', '/api/v1/users/me', json={'confirmation': 'DELETE'})
            assert result.status_code == 202 and result.json()['status'] == 'requested'
            request.assert_called_once_with(USER, 'private-token')
            monkeypatch.setenv('ACCOUNT_DELETION_ENABLED', 'false')
            assert client.request('DELETE', '/api/v1/users/me', json={'confirmation': 'DELETE'}).status_code == 503
        finally:
            app.dependency_overrides.clear()


def test_account_marker_blocks_api_even_with_valid_auth(monkeypatch):
    monkeypatch.setattr(auth, 'account_is_active', lambda _: False)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(auth.get_current_user({'user_id': USER}))
    assert failure.value.status_code == 403
    monkeypatch.setattr(auth, 'account_is_active', Mock(side_effect=RuntimeError('private')))
    with pytest.raises(HTTPException) as failure:
        asyncio.run(auth.get_current_user({'user_id': USER}))
    assert failure.value.status_code == 503 and 'private' not in failure.value.detail


def test_session_revoke_failure_does_not_lose_accepted_request(monkeypatch, caplog):
    db = Mock()
    db.rpc.return_value.execute.return_value = SimpleNamespace(data={**JOB, 'requested_at': 'now'})
    db.auth.admin.sign_out.side_effect = RuntimeError('private-token')
    monkeypatch.setattr(deletion, 'admin_supabase', db)
    assert deletion.request_deletion(USER, 'private-token')['status'] == 'requested'
    assert 'private-token' not in caplog.text


def worker_database(paths, fail_auth=False):
    db = Mock()
    inventory = iter(paths)
    events = []
    def rpc(name, params):
        if name == 'claim_account_deletion':
            value = JOB
        elif name == 'deletion_object_paths':
            value = next(inventory)
        else:
            events.append(('finish', params['p_success']))
            value = True
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=value))
    db.rpc.side_effect = rpc
    db.storage.from_.return_value.remove.side_effect = lambda paths: events.append(('remove', paths))
    def delete(_):
        events.append(('auth-delete', USER))
        if fail_auth:
            raise RuntimeError('private-response')
    db.auth.admin.delete_user.side_effect = delete
    return db, events


def test_worker_removes_audio_before_auth_and_sweeps_again(monkeypatch):
    paths = [f'{USER}/2026-11-09/{n}.mp3' for n in range(125)]
    db, events = worker_database([paths[:100], paths[100:], [], []])
    monkeypatch.setattr(deletion, 'admin_supabase', db)
    assert deletion.process_one_deletion()
    assert [event[0] for event in events] == ['remove', 'remove', 'auth-delete', 'finish']
    assert events[-1] == ('finish', True)


@pytest.mark.parametrize('bad_path', ['other-user/file.mp3', f'{USER}/../other/file.mp3', f'{USER}//file.mp3'])
def test_worker_rejects_unsafe_inventory(monkeypatch, bad_path):
    db, events = worker_database([[bad_path]])
    monkeypatch.setattr(deletion, 'admin_supabase', db)
    deletion.process_one_deletion()
    db.storage.from_.assert_not_called()
    db.auth.admin.delete_user.assert_not_called()
    assert events == [('finish', False)]


def test_auth_failure_retains_deletion_for_retry(monkeypatch, caplog):
    db, events = worker_database([[]], fail_auth=True)
    monkeypatch.setattr(deletion, 'admin_supabase', db)
    deletion.process_one_deletion()
    assert events[-1] == ('finish', False)
    assert 'private-response' not in caplog.text


def test_upload_refuses_deleted_account_and_removes_a_racing_upload(monkeypatch, tmp_path):
    audio = tmp_path/'test.mp3'
    audio.write_bytes(b'fixture')
    db = Mock()
    monkeypatch.setattr(storage, 'admin_supabase', db)
    monkeypatch.setattr(storage, 'account_is_active', lambda _: False)
    with pytest.raises(RuntimeError):
        storage.upload_briefing_audio(str(audio), f'{USER}/today/file.mp3')
    db.storage.from_.assert_not_called()
    monkeypatch.setattr(storage, 'account_is_active', Mock(side_effect=[True, False]))
    with pytest.raises(RuntimeError):
        storage.upload_briefing_audio(str(audio), f'{USER}/today/file.mp3')
    db.storage.from_.return_value.remove.assert_called_once_with([f'{USER}/today/file.mp3'])


def test_status_retains_pending_request_when_new_requests_are_disabled(monkeypatch):
    monkeypatch.setenv('ACCOUNT_DELETION_ENABLED', 'false')
    db = Mock()
    query = db.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = SimpleNamespace(data=[{'state': 'pending'}])
    monkeypatch.setattr(routes, 'admin_supabase', db)
    result = asyncio.run(routes.deletion_status({'user_id': USER}))
    assert result == {'enabled': False, 'status': 'requested'}
    db.table.return_value.select.return_value.eq.assert_called_once_with('user_id', USER)
    query.execute.side_effect = RuntimeError('private-credential')
    with pytest.raises(HTTPException) as failure:
        asyncio.run(routes.deletion_status({'user_id': USER}))
    assert failure.value.status_code == 503 and 'private' not in failure.value.detail


def test_worker_recovers_when_auth_was_already_deleted(monkeypatch):
    from supabase_auth.errors import AuthApiError
    db, events = worker_database([[], []])
    db.auth.admin.update_user_by_id.side_effect = AuthApiError('User not found', 404, 'user_not_found')
    db.auth.admin.delete_user.side_effect = AuthApiError('User not found', 404, 'user_not_found')
    monkeypatch.setattr(deletion, 'admin_supabase', db)
    assert deletion.process_one_deletion()
    assert events == [('finish', True)]


def test_worker_tick_is_bounded_and_stops_on_empty_or_failed_claim(monkeypatch):
    process = Mock(return_value=True)
    monkeypatch.setattr(deletion, 'process_one_deletion', process)
    asyncio.run(deletion.process_account_deletions())
    assert process.call_count == 4
    for outcome in [False, RuntimeError('offline')]:
        process = Mock(side_effect=outcome) if isinstance(outcome, Exception) else Mock(return_value=outcome)
        monkeypatch.setattr(deletion, 'process_one_deletion', process)
        asyncio.run(deletion.process_account_deletions())
        assert process.call_count == 1
