from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.auth import get_current_user
from app.routes import news, bookmarks

@pytest.fixture
def library(monkeypatch):
    db = Mock()
    for method in ('table','select','eq','in_','ilike','order','range','limit','upsert','delete'):
        getattr(db, method).return_value = db
    db.execute.return_value = SimpleNamespace(data=[])
    app.dependency_overrides[get_current_user] = lambda: {'user_id':'owner','access_token':'owner-token'}
    factory = Mock(return_value=db)
    monkeypatch.setattr(news, 'create_supabase_client', factory)
    monkeypatch.setattr(bookmarks, 'create_supabase_client', factory)
    yield TestClient(app), db, factory
    app.dependency_overrides.clear()


def test_search_is_bound_escaped_and_bounded(library):
    client, db, factory = library
    db.execute.return_value = SimpleNamespace(data=[{'id':str(i)} for i in range(3)])
    r=client.get('/api/v1/news/discover',params={'q':'100%_news','limit':2})
    assert r.status_code==200 and len(r.json()['news'])==2 and r.json()['next_offset']==2
    db.ilike.assert_called_once_with('title', '%100\\%\\_news%')
    db.range.assert_called_once_with(0,2)
    factory.assert_called_with('owner-token')
    assert client.get('/api/v1/news/discover?limit=1000').status_code==422
    assert client.get('/api/v1/news/discover?offset=-1').status_code==422


def test_empty_search_and_missing_detail(library):
    client, db, _ = library
    assert client.get('/api/v1/news/discover').json()=={'news':[],'next_offset':None}
    assert client.get('/api/v1/news/'+str(uuid4())).status_code==404
    db.execute.side_effect=RuntimeError('private credential')
    response=client.get('/api/v1/news/discover')
    assert response.status_code==503 and 'credential' not in response.text


def test_personalized_discovery_is_limited_to_saved_categories(library):
    client, db, _ = library
    business = str(uuid4())
    db.execute.side_effect = [
        SimpleNamespace(data=[{'category_id': business}]),
        SimpleNamespace(data=[]),
    ]
    response = client.get('/api/v1/news/discover', params={'selected_only': 'true'})
    assert response.status_code == 200
    db.in_.assert_called_once_with('category_id', [business])
    assert ('user_id', 'owner') in [call.args for call in db.eq.call_args_list]


def test_personalized_discovery_rejects_unselected_category_without_news_query(library):
    client, db, _ = library
    db.execute.return_value = SimpleNamespace(data=[{'category_id': str(uuid4())}])
    response = client.get('/api/v1/news/discover', params={
        'selected_only': 'true', 'category_id': str(uuid4()),
    })
    assert response.json() == {'news': [], 'next_offset': None}
    db.in_.assert_not_called()


def test_bookmarks_always_use_authenticated_owner_and_fail_closed(library):
    client, db, factory = library
    article=str(uuid4())
    assert client.put('/api/v1/bookmarks/'+article,json={'user_id':'other'}).json()=={'saved':True}
    assert db.upsert.call_args.args[0]=={'user_id':'owner','article_id':article}
    client.delete('/api/v1/bookmarks/'+article)
    assert ('user_id','owner') in [call.args for call in db.eq.call_args_list]
    factory.assert_called_with('owner-token')
    db.execute.side_effect=RuntimeError('missing table and secret')
    response=client.get('/api/v1/bookmarks')
    assert response.status_code==503 and 'secret' not in response.text


def test_library_endpoints_require_auth():
    with TestClient(app) as client:
        for path in ('/api/v1/news/discover','/api/v1/news/'+str(uuid4()),'/api/v1/bookmarks'):
            assert client.get(path).status_code==401
