from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.auth import get_current_user
from app.routes import briefings

@pytest.fixture
def history(monkeypatch):
    db=Mock()
    for method in ('table','select','eq','order','range','limit'):
        getattr(db,method).return_value=db
    db.execute.return_value=SimpleNamespace(data=[])
    owner=str(uuid4())
    app.dependency_overrides[get_current_user]=lambda: {'user_id':owner,'access_token':'test-only'}
    factory=Mock(return_value=db)
    signer=Mock(return_value='https://storage.invalid/signed')
    monkeypatch.setattr(briefings,'create_supabase_client',factory)
    monkeypatch.setattr(briefings,'create_briefing_signed_url',signer)
    yield TestClient(app),db,owner,signer,factory
    app.dependency_overrides.clear()


def test_owner_scoped_pagination(history):
    client,db,owner,signer,factory=history
    db.execute.return_value=SimpleNamespace(data=[{'id':str(i)} for i in range(3)])
    response=client.get('/api/v1/briefings/history?limit=2')
    assert response.status_code==200
    assert response.json()['next_offset']==2 and len(response.json()['briefings'])==2
    db.eq.assert_called_with('user_id',owner)
    factory.assert_called_with('test-only')
    assert 'audio_url' not in db.select.call_args.args[0]
    signer.assert_not_called()
    assert client.get('/api/v1/briefings/history?limit=51').status_code==422


def test_missing_foreign_or_unsafe_audio_never_signed(history):
    client,db,owner,signer,_=history
    path='/api/v1/briefings/history/'+str(uuid4())
    assert client.get(path).status_code==404
    for record in ({'user_id':'other','audio_url':'other/a.mp3','status':'ready'},
                   {'user_id':owner,'audio_url':'other/a.mp3','status':'ready'},
                   {'user_id':owner,'audio_url':owner+'/../a.mp3','status':'ready'},
                   {'user_id':owner,'audio_url':owner+'/%2e%2e/a.mp3','status':'ready'}):
        db.execute.return_value=SimpleNamespace(data=[record])
        assert client.get(path).status_code in (404,503)
    signer.assert_not_called()


def test_authorized_url_renewal_and_storage_failure(history):
    client,db,owner,signer,_=history
    path='/api/v1/briefings/history/'+str(uuid4())
    db.execute.return_value=SimpleNamespace(data=[{'user_id':owner,'audio_url':owner+'/day/a.mp3','status':'ready'}])
    assert client.get(path).json()['briefing']['audio_url']=='https://storage.invalid/signed'
    signer.assert_called_with(owner+'/day/a.mp3',expires_in=3600)
    signer.side_effect=RuntimeError('secret')
    response=client.get(path)
    assert response.status_code==503 and 'secret' not in response.text


def test_history_requires_auth():
    with TestClient(app) as client:
        assert client.get('/api/v1/briefings/history').status_code==401
        assert client.get('/api/v1/briefings/history/'+str(uuid4())).status_code==401
