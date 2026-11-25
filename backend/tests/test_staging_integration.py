import asyncio
import importlib.util
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.main import app
from app.routes import news_ingestion
from app.services.news import batch, categories, run_ingestion
from app.services.news.sources import NEWS_SOURCES
from app.services.ai import gemini


@pytest.fixture
def category_ids():
    return {feed['category']: uuid4() for feed in NEWS_SOURCES}


@pytest.fixture
def operator_client(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {'user_id': 'operator'}
    monkeypatch.setenv('INGESTION_OPERATOR_IDS', 'operator')
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_category_ids_come_from_current_database(monkeypatch, category_ids):
    query = Mock()
    query.table.return_value = query
    query.select.return_value = query
    query.in_.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[
        {'slug': slug, 'id': str(id)} for slug, id in category_ids.items()
    ])
    monkeypatch.setattr(categories, 'admin_supabase', query)
    assert categories.resolve_category_ids() == category_ids
    query.eq.assert_called_once_with('active', True)
    query.execute.return_value = SimpleNamespace(data=[])
    with pytest.raises(RuntimeError, match='missing or inactive'):
        categories.resolve_category_ids()


def test_configured_feed_uses_staging_id(operator_client, monkeypatch, category_ids):
    feed = NEWS_SOURCES[0]
    monkeypatch.setattr(news_ingestion, 'resolve_category_ids', lambda: category_ids)
    ingest = Mock(return_value={'inserted': 1})
    monkeypatch.setattr(news_ingestion, 'ingest_feed', ingest)
    body = {'feed_url': feed['url'], 'source': feed['name'],
            'category_id': str(category_ids[feed['category']])}
    assert operator_client.post('/api/v1/news/ingest', json=body).status_code == 200
    assert ingest.call_args.kwargs['category_id'] == category_ids[feed['category']]
    ingest.reset_mock()
    body['category_id'] = str(uuid4())
    assert operator_client.post('/api/v1/news/ingest', json=body).status_code == 422
    ingest.assert_not_called()


def test_missing_categories_stop_batch_before_fetch(operator_client, monkeypatch):
    monkeypatch.setattr(batch, 'resolve_category_ids', Mock(side_effect=RuntimeError('private failure')))
    ingest = Mock()
    monkeypatch.setattr(batch, 'ingest_feed', ingest)
    response = operator_client.post('/api/v1/news/ingest-all')
    assert response.status_code == 503
    assert 'private failure' not in response.text
    ingest.assert_not_called()


def test_bulk_feed_failure_does_not_expose_provider_detail(monkeypatch, category_ids, caplog):
    monkeypatch.setattr(batch, 'ingest_feed', Mock(side_effect=RuntimeError('secret-token-value')))
    async def run():
        return await batch.ingest_one(NEWS_SOURCES[0], asyncio.Semaphore(1), category_ids)
    result = asyncio.run(run())
    assert result['success'] is False
    assert 'secret-token-value' not in str(result)
    assert 'secret-token-value' not in caplog.text


def test_legacy_ingestion_resolves_ids_once(monkeypatch, category_ids):
    resolver = Mock(return_value=category_ids)
    ingest = Mock(return_value={'inserted': 0})
    monkeypatch.setattr(run_ingestion, 'resolve_category_ids', resolver)
    monkeypatch.setattr(run_ingestion, 'ingest_feed', ingest)
    assert len(run_ingestion.run_all_ingestion()) == 8
    resolver.assert_called_once()
    assert {c.kwargs['category_id'] for c in ingest.call_args_list} == set(category_ids.values())


def test_missing_ai_credential_never_constructs_provider_client(monkeypatch):
    gemini._get_client.cache_clear()
    monkeypatch.setattr(gemini, 'GEMINI_API_KEY', None)
    factory = Mock()
    monkeypatch.setattr(gemini.genai, 'Client', factory)
    with pytest.raises(RuntimeError, match='not configured'):
        gemini._get_client()
    factory.assert_not_called()


def load_staging_setup():
    path = Path(__file__).resolve().parents[1] / 'scripts/prepare_staging.py'
    spec = importlib.util.spec_from_file_location('prepare_staging', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ai_provider_failure_does_not_log_response_body(monkeypatch, capsys):
    monkeypatch.setattr(gemini, '_generate_with_model', Mock(side_effect=RuntimeError('secret-provider-response')))
    with pytest.raises(RuntimeError, match='primary and fallback'):
        gemini.generate_briefing_script([{'category': {'name_en': 'World'}, 'stories': [{'title': 'Test article'}]}])
    assert 'secret-provider-response' not in capsys.readouterr().out


def test_staging_setup_excludes_provider_credentials_and_preserves_existing_file(tmp_path, monkeypatch):
    setup = load_staging_setup()
    monkeypatch.setenv('GEMINI_API_KEY', 'production-gemini-secret')
    monkeypatch.setenv('AZURE_SPEECH_KEY', 'production-azure-secret')
    values = setup.build_environment([
        {'type': 'publishable', 'api_key': 'test-public'},
        {'type': 'secret', 'api_key': 'test-private'},
    ])
    destination = tmp_path / '.env.staging'
    setup.write_environment(destination, values)
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    saved = dotenv_values(destination)
    assert saved['GEMINI_API_KEY'] == saved['AZURE_SPEECH_KEY'] == ''
    assert saved['SCHEDULER_ENABLED'] == 'false'
    assert saved['AUTOMATIC_BRIEFING_PREFERENCES_ENABLED'] == 'false'
    assert 'production-' not in destination.read_text()
    with pytest.raises(FileExistsError):
        setup.write_environment(destination, {})
    assert dotenv_values(destination) == saved


def test_staging_setup_refuses_ambiguous_or_disabled_keys():
    setup = load_staging_setup()
    with pytest.raises(RuntimeError):
        setup.build_environment([{'type': 'secret', 'api_key': 'disabled', 'disabled': True}])


def test_hosted_runner_refuses_production_and_enabled_providers():
    path = Path(__file__).resolve().parents[1] / 'scripts/staging_smoke.py'
    spec = importlib.util.spec_from_file_location('staging_smoke', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = load_staging_setup().build_environment([
        {'type': 'publishable', 'api_key': 'test-public'},
        {'type': 'secret', 'api_key': 'test-private'},
    ])
    module.validate_environment(values)
    with pytest.raises(ValueError, match='authorized staging'):
        module.validate_environment({**values, 'SUPABASE_URL': 'https://production.supabase.co'})
    for key, value in [('GEMINI_API_KEY', 'provider-key'), ('AZURE_SPEECH_KEY', 'provider-key'),
                       ('FIREBASE_SERVICE_ACCOUNT_PATH', '/credentials.json'), ('SCHEDULER_ENABLED', 'true'), ('AUTOMATIC_BRIEFING_PREFERENCES_ENABLED', 'true'), ('NEWS_INGESTION_ENABLED', 'true'), ('PUSH_DELIVERY_ENABLED', 'true')]:
        with pytest.raises(ValueError):
            module.validate_environment({**values, key: value})
