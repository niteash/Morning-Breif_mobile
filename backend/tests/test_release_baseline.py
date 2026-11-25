from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies.auth import get_current_user
from app.routes import briefings, news_ingestion
from app.services.ai import gemini
from app.services.briefing.dates import briefing_date
from app.services.tts.duration import audio_duration_seconds


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_health_without_scheduler(client):
    response = client.get("/health", headers={"X-Request-ID": "health-check-1"})
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"] == "health-check-1"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/").json()["scheduler"] == "disabled"
    assert client.get("/").json()["news_ingestion"] == "disabled"
    assert client.get("/").json()["push_delivery"] == "disabled"


def test_readiness_checks_database_without_exposing_failure(client, monkeypatch):
    from app.routes import health

    database = Mock()
    database.table.return_value = database
    database.select.return_value = database
    database.limit.return_value = database
    database.execute.return_value = SimpleNamespace(data=[])
    monkeypatch.setattr(health, "admin_supabase", database)
    assert client.get("/health/ready").json()["status"] == "ready"

    database.execute.side_effect = RuntimeError("secret database endpoint")
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert "secret" not in response.text


@pytest.mark.parametrize("path", ["/api/v1/news/ingest", "/api/v1/news/ingest-all"])
def test_ingestion_requires_authentication(client, path):
    assert client.post(path, json={}).status_code == 401


def test_non_operator_cannot_ingest(client):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "ordinary-user"}
    assert client.post("/api/v1/news/ingest-all").status_code == 403


def test_anonymous_session_cannot_read_user_briefings(client, monkeypatch):
    from app.dependencies import auth
    monkeypatch.setattr(auth.admin_supabase.auth, "get_claims", lambda token: {
        "claims": {"sub": "11111111-1111-4111-8111-111111111111", "is_anonymous": True}})
    response = client.get("/api/v1/briefings/today/saved", headers={"Authorization": "Bearer test"})
    assert response.status_code == 401


def test_manual_generation_persists_duration_even_if_signing_fails(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "owner", "access_token": "test"}
    artifact = {"script": "Burmese script", "audio_url": "owner/date/file.mp3", "duration_seconds": 42}
    async def select(**kwargs):
        return [{"stories": [{"title": "News"}]}]
    db = Mock()
    db.table.return_value = db
    db.upsert.return_value = db
    db.execute.return_value = SimpleNamespace(data=[{"id": "briefing", **artifact}])
    monkeypatch.setattr(briefings, "create_supabase_client", lambda token: db)
    monkeypatch.setattr(briefings, "get_briefing_date", lambda client, user: "2026-11-08")
    monkeypatch.setattr(briefings, "select_recent_stories", select)
    monkeypatch.setattr(briefings, "generate_and_save", lambda *args: ({"id": "briefing", **artifact}, True))
    monkeypatch.setattr(briefings, "create_briefing_signed_url", Mock(side_effect=RuntimeError("unavailable")))
    response = client.post("/api/v1/briefings/generate", json={})
    assert response.status_code == 200
    assert response.json()["briefing"]["audio_url"] is None
    assert response.json()["briefing"]["duration_seconds"] == 42
    db.upsert.assert_not_called()  # Persistence belongs to the fenced service RPC.


def test_generate_refreshes_reviewed_news_once_before_audio(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "owner", "access_token": "test"}
    empty = [{"category": {"id": "category", "slug": "technology"}, "stories": []}]
    fresh = [{"category": {"id": "category", "slug": "technology"},
              "stories": [{"id": "story", "title": "Fresh news"}]}]
    selections = iter((empty, fresh))
    async def select(**_kwargs): return next(selections)
    async def ingest(): return {"successful_feeds": 1, "failed_feeds": 0, "totals": {"inserted": 1}}
    monkeypatch.setattr(briefings, "ON_DEMAND_NEWS_REFRESH_ENABLED", True)
    monkeypatch.setattr(briefings, "select_recent_stories", select)
    monkeypatch.setattr(briefings, "run_ingestion_batch", ingest)
    monkeypatch.setattr(briefings, "require_generation_access", Mock())
    monkeypatch.setattr(briefings, "generation_disabled", lambda: False)
    monkeypatch.setattr(briefings, "get_briefing_date", lambda *_: "2026-11-21")
    monkeypatch.setattr(briefings, "create_supabase_client", lambda *_: Mock())
    generated = Mock(return_value=({"id": "briefing", "audio_url": None, "generated_at": "now"}, True))
    monkeypatch.setattr(briefings, "generate_and_save", generated)
    response = client.post("/api/v1/briefings/generate", json={})
    assert response.status_code == 200
    assert response.json()["categories"] == fresh
    generated.assert_called_once()


def test_generation_without_fresh_selected_news_returns_recoverable_code(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "owner", "access_token": "test"}
    async def select(**_kwargs): return [{"category": {"id": "business"}, "stories": []}]
    async def ingest(): return {"totals": {"inserted": 0}}
    monkeypatch.setattr(briefings, "select_recent_stories", select)
    monkeypatch.setattr(briefings, "ON_DEMAND_NEWS_REFRESH_ENABLED", True)
    monkeypatch.setattr(briefings, "run_ingestion_batch", ingest)
    monkeypatch.setattr(briefings, "require_generation_access", Mock())
    monkeypatch.setattr(briefings, "generation_disabled", lambda: False)
    monkeypatch.setattr(briefings, "get_briefing_date", lambda *_: "2026-11-21")
    monkeypatch.setattr(briefings, "create_supabase_client", lambda *_: Mock())
    response = client.post("/api/v1/briefings/generate", json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "no_recent_news"



def test_operator_cannot_request_arbitrary_url(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "operator"}
    monkeypatch.setenv("INGESTION_OPERATOR_IDS", "operator")
    ingest = Mock(side_effect=AssertionError("Must not fetch"))
    monkeypatch.setattr(news_ingestion, "ingest_feed", ingest)
    response = client.post("/api/v1/news/ingest", json={
        "feed_url": "http://127.0.0.1/private", "source": "Injected",
        "category_id": "00000000-0000-0000-0000-000000000001",
    })
    assert response.status_code == 422
    ingest.assert_not_called()


def test_invalid_timezone_rejected_before_database(client):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user"}
    assert client.put("/api/v1/users/me/preferences", json={"timezone": "bad/zone"}).status_code == 422


def test_preference_patch_preserves_omitted_automatic_delivery_flags(client, monkeypatch):
    from app.routes import users
    monkeypatch.setattr(users, "AUTOMATIC_BRIEFING_PREFERENCES_ENABLED", True)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user", "access_token": "test"}
    db = Mock()
    db.table.return_value = db
    db.select.return_value = db
    db.eq.return_value = db
    db.limit.return_value = db
    db.update.return_value = db
    db.execute.side_effect = [
        SimpleNamespace(data=[{"id": "user"}]),
        SimpleNamespace(data=[{"id": "user", "daily_reminder_enabled": True}]),
    ]
    monkeypatch.setattr("app.routes.users.create_supabase_client", lambda _token: db)
    response = client.put("/api/v1/users/me/preferences", json={"daily_reminder_enabled": True})
    assert response.status_code == 200
    db.update.assert_called_once_with({"daily_reminder_enabled": True})


def test_automatic_delivery_preference_write_fails_closed_until_schema_enabled(client):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user", "access_token": "test"}
    response = client.put("/api/v1/users/me/preferences", json={"auto_play_when_open": True})
    assert response.status_code == 503


def test_invalid_delivery_schedule_is_rejected_before_database(client):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user"}
    assert client.put("/api/v1/users/me/preferences", json={"delivery_schedule": "weekends"}).status_code == 422


def test_local_dates_at_utc_boundary():
    instant = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)
    assert briefing_date("Asia/Yangon", instant) == "2026-11-08"
    assert briefing_date("America/New_York", instant) == "2026-11-07"
    assert briefing_date("invalid", instant) == "2026-11-08"
    with pytest.raises(ValueError):
        briefing_date("UTC", datetime(2026, 11, 7))


@pytest.mark.parametrize("categories", [[], [{"category": {"name_en": "World"}, "stories": [{"title": " "}]}]])
def test_empty_stories_never_call_llm(monkeypatch, categories):
    generate = Mock(side_effect=AssertionError("Must not call provider"))
    monkeypatch.setattr(gemini, "_generate_with_model", generate)
    with pytest.raises(ValueError, match="no usable"):
        gemini.generate_briefing_script(categories)
    generate.assert_not_called()


def test_invalid_mp3_rejected(tmp_path):
    path = tmp_path / "invalid.mp3"
    path.write_bytes(b"not audio")
    with pytest.raises(Exception):
        audio_duration_seconds(str(path))


def test_saved_briefing_is_scoped_to_user_and_local_date(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "owner", "access_token": "test"}
    db = Mock()
    db.table.return_value = db
    db.select.return_value = db
    db.eq.return_value = db
    db.limit.return_value = db
    db.execute.return_value = SimpleNamespace(data=[])
    monkeypatch.setattr(briefings, "create_supabase_client", lambda token: db)
    monkeypatch.setattr(briefings, "get_briefing_date", lambda client, user: "2026-11-08")
    assert client.get("/api/v1/briefings/today/saved").json() == {"briefing": None}
    db.eq.assert_any_call("user_id", "owner")
    db.eq.assert_any_call("briefing_date", "2026-11-08")


@pytest.mark.parametrize("module", ["test_relevance", "test_ranker", "test_clustering", "test_news_pipeline"])
def test_legacy_news_regressions(module):
    import importlib
    importlib.import_module(module).main()


def test_category_rpc_failure_never_deletes_existing_preferences(client, monkeypatch):
    from app.routes import users
    app.dependency_overrides[get_current_user] = lambda: {'user_id':'owner','access_token':'test'}
    db = Mock()
    db.rpc.side_effect = RuntimeError('missing migration')
    monkeypatch.setattr(users, 'create_supabase_client', lambda token: db)
    response=client.put('/api/v1/users/me/categories', json={'category_ids':['10000000-0000-0000-0000-000000000001']})
    assert response.status_code==503
    db.table.assert_not_called()


@pytest.mark.parametrize('error,status', [
    (briefings.GenerationBusy(),409), (briefings.GenerationLimited(),429),
    (briefings.GenerationUnavailable(),503), (briefings.LostGenerationLease(),503),
])
def test_generation_coordination_errors_are_actionable(client, monkeypatch, error, status):
    app.dependency_overrides[get_current_user] = lambda: {'user_id':'owner','access_token':'test'}
    monkeypatch.setattr(briefings,'get_briefing_date',lambda *args:'2026-11-08')
    monkeypatch.setattr(briefings,'create_supabase_client',lambda *args: Mock())
    async def select(**kwargs): return [{'stories':[{'title':'News'}]}]
    monkeypatch.setattr(briefings,'select_recent_stories',select)
    monkeypatch.setattr(briefings,'generate_and_save',Mock(side_effect=error))
    assert client.post('/api/v1/briefings/generate',json={}).status_code==status


def test_generation_limit_has_structured_safe_detail(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {'user_id':'owner','access_token':'test'}
    monkeypatch.setattr(briefings,'get_briefing_date',lambda *args:'2026-11-08')
    monkeypatch.setattr(briefings,'create_supabase_client',lambda *args: Mock())
    async def select(**kwargs): return [{'stories':[{'title':'News'}]}]
    monkeypatch.setattr(briefings,'select_recent_stories',select)
    monkeypatch.setattr(briefings,'generate_and_save',Mock(side_effect=briefings.GenerationLimited()))

    response = client.post('/api/v1/briefings/generate',json={})

    assert response.status_code == 429
    assert response.json()['detail']['code'] == 'generation_limit_reached'
    assert 'audio' in response.json()['detail']['message']


def test_generation_pipeline_error_reports_safe_stage(client, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {'user_id':'owner','access_token':'test'}
    monkeypatch.setattr(briefings,'get_briefing_date',lambda *args:'2026-11-08')
    monkeypatch.setattr(briefings,'create_supabase_client',lambda *args: Mock())
    async def select(**kwargs): return [{'stories':[{'title':'News'}]}]
    monkeypatch.setattr(briefings,'select_recent_stories',select)
    error = briefings.PipelineStageError('speech_synthesis', RuntimeError('provider secret'))
    monkeypatch.setattr(briefings,'generate_and_save',Mock(side_effect=error))

    response = client.post('/api/v1/briefings/generate',json={})

    assert response.status_code == 503
    assert response.json()['detail']['stage'] == 'speech_synthesis'
    assert 'provider secret' not in response.text
