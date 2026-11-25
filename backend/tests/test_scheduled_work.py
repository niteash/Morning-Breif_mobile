import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import httpx
import pytest
from postgrest import SyncPostgrestClient

from app.services import scheduler
from app.services.news import batch


@pytest.fixture(autouse=True)
def ingestion_database_lease(monkeypatch):
    monkeypatch.setattr(batch, '_claim_ingestion_lease', lambda: 'test-lease')
    monkeypatch.setattr(batch, '_release_ingestion_lease', lambda _token: None)


class FixedTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 9, 7, tzinfo=timezone.utc).astimezone(tz)


def profile(number):
    return {'id': str(UUID(int=number)), 'timezone': 'UTC', 'delivery_hour': 7, 'delivery_minute': 0,
            'delivery_schedule': 'daily', 'automatic_briefing_enabled': True}


def test_cursor_scan_reaches_beyond_row_limit_with_deletions_and_bounded_workers(monkeypatch):
    rows = [profile(n) for n in range(1, 1151)]
    expected = {item['id'] for item in rows}
    requests = []
    def handle(request):
        params = request.url.params
        assert params['order'] == 'id.asc'
        assert params['select'] == 'id,timezone,delivery_hour,delivery_minute,delivery_schedule,automatic_briefing_enabled'
        assert params['automatic_briefing_enabled'].lower() == 'eq.true'
        requests.append(request)
        cursor = params.get('id', '').removeprefix('gt.')
        # Deleting an already-scanned row must not shift/skip the next page.
        if len(requests) == 2:
            rows.pop(0)
        selected = [row for row in rows if row['id'] > cursor]
        # Emulate a server limit below the requested page size.
        return httpx.Response(200, json=selected[:min(37, int(params['limit']))])
    client = httpx.Client(transport=httpx.MockTransport(handle))
    postgrest = SyncPostgrestClient('https://offline.invalid/rest/v1', http_client=client)
    monkeypatch.setattr(scheduler, 'admin_supabase', SimpleNamespace(table=postgrest.from_))
    monkeypatch.setattr(scheduler, 'datetime', FixedTime)
    seen = []
    active = maximum = 0
    async def deliver(item):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        seen.append(item['id'])
        active -= 1
    monkeypatch.setattr(scheduler, 'generate_scheduled_briefing', deliver)
    try:
        result = asyncio.run(scheduler.check_due_users())
    finally:
        client.close()
    assert result['scan_complete'] is True
    assert result['profiles_scanned'] == result['attempted'] == 1150
    assert len(seen) == len(set(seen)) == 1150
    assert set(seen) == expected
    assert maximum <= scheduler.DELIVERY_CONCURRENCY
    assert len(requests) > 2


def test_scan_failure_drains_queued_users_and_next_tick_recovers(monkeypatch, caplog):
    monkeypatch.setattr(scheduler, 'datetime', FixedTime)
    pages = Mock(side_effect=[[profile(1), profile(2)], RuntimeError('private-database-detail')])
    monkeypatch.setattr(scheduler, 'fetch_profile_page', pages)
    delivered = AsyncMock()
    monkeypatch.setattr(scheduler, 'generate_scheduled_briefing', delivered)
    result = asyncio.run(scheduler.check_due_users())
    assert not result['scan_complete']
    assert delivered.await_count == 2
    assert 'private-database-detail' not in caplog.text
    pages.side_effect = [[profile(1), profile(2), profile(3)], []]
    result = asyncio.run(scheduler.check_due_users())
    assert result['scan_complete'] and result['attempted'] == 3


def test_nonadvancing_cursor_stops_and_queued_expiry_is_rechecked(monkeypatch):
    monkeypatch.setattr(scheduler, 'fetch_profile_page', Mock(return_value=[profile(1)]))
    # First scan considers the user due; delivery recheck detects expiration.
    monkeypatch.setattr(scheduler, 'is_delivery_due', Mock(side_effect=[True, False]))
    delivered = AsyncMock()
    monkeypatch.setattr(scheduler, 'generate_scheduled_briefing', delivered)
    result = asyncio.run(scheduler.check_due_users())
    assert not result['scan_complete'] and result['expired'] == 1
    delivered.assert_not_awaited()


def test_one_delivery_exception_does_not_stop_other_users(monkeypatch):
    monkeypatch.setattr(scheduler, 'datetime', FixedTime)
    monkeypatch.setattr(scheduler, 'fetch_profile_page', Mock(side_effect=[[profile(1), profile(2)], []]))
    delivered = AsyncMock(side_effect=[RuntimeError('failed'), None])
    monkeypatch.setattr(scheduler, 'generate_scheduled_briefing', delivered)
    result = asyncio.run(scheduler.check_due_users())
    assert result['scan_complete'] and result['task_errors'] == 1
    assert delivered.await_count == 2


def test_expired_entitlement_skips_news_selection_and_provider_work(monkeypatch):
    from app.services.entitlements import TrialAccessDenied
    profile_data = profile(1)
    monkeypatch.setattr(scheduler, 'delivery_due_at', lambda _profile, _now: datetime(2026, 11, 16, 7, tzinfo=timezone.utc))
    monkeypatch.setattr(scheduler, 'get_existing_briefing', Mock(return_value=None))
    monkeypatch.setattr(scheduler, 'require_generation_access', Mock(side_effect=TrialAccessDenied()))
    select_news = Mock(side_effect=AssertionError('unauthorized account must not select stories'))
    monkeypatch.setattr(scheduler, 'collect_user_news', select_news)
    scheduler._in_progress.clear()
    asyncio.run(scheduler.generate_scheduled_briefing(profile_data))
    select_news.assert_not_called()


def test_batch_counts_partial_writes_and_isolates_feed_failures(monkeypatch):
    feeds = [{'name': str(n), 'url': f'https://feed.invalid/{n}', 'category': 'technology'} for n in range(3)]
    monkeypatch.setattr(batch, 'NEWS_SOURCES', feeds)
    monkeypatch.setattr(batch, 'resolve_category_ids', lambda: {'technology': 'category-id'})
    def ingest(**kwargs):
        if kwargs['source'] == '2':
            raise RuntimeError('private-provider-response')
        failed = int(kwargs['source'] == '1')
        return {'total': 5, 'inserted': 3, 'fresh_inserted': 3, 'skipped': 2,
                'skipped_insert_failure': failed}
    monkeypatch.setattr(batch, 'ingest_feed', ingest)
    result = asyncio.run(batch.run_ingestion_batch())
    assert result['successful_feeds'] == 1 and result['failed_feeds'] == 2
    assert result['totals']['articles_seen'] == 10
    assert result['totals']['inserted'] == 6
    assert result['totals']['skipped_insert_failure'] == 1
    assert 'private-provider-response' not in str(result)


def test_batch_overlap_is_rejected_and_failure_releases_guard(monkeypatch):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        monkeypatch.setattr(batch, 'resolve_category_ids', lambda: {})
        async def ingest(*args):
            started.set()
            await release.wait()
            return {'success': True, 'result': {}}
        monkeypatch.setattr(batch, 'ingest_one', ingest)
        running = asyncio.create_task(batch.run_ingestion_batch())
        await started.wait()
        with pytest.raises(batch.IngestionBusy):
            await batch.run_ingestion_batch()
        release.set()
        await running
        monkeypatch.setattr(batch, 'resolve_category_ids', Mock(side_effect=RuntimeError('unavailable')))
        with pytest.raises(RuntimeError):
            await batch.run_ingestion_batch()
        monkeypatch.setattr(batch, 'resolve_category_ids', lambda: {})
        assert (await batch.run_ingestion_batch())['failed_feeds'] == 0
    asyncio.run(scenario())


@pytest.mark.parametrize('deliveries,ingestion,expected', [
    (False, False, set()), (True, False, {'morning_brief_delivery_checker'}),
    (False, True, {'morning_brief_news_ingestion'}),
    (True, True, {'morning_brief_delivery_checker', 'morning_brief_news_ingestion'}),
])
def test_periodic_jobs_are_independent_and_opt_in(monkeypatch, deliveries, ingestion, expected):
    engine = Mock(running=False)
    monkeypatch.setattr(scheduler, 'scheduler', engine)
    scheduler.start_scheduler(deliveries_enabled=deliveries, ingestion_enabled=ingestion)
    assert {call.kwargs['id'] for call in engine.add_job.call_args_list} == expected
    assert engine.start.call_count == bool(expected)
    for call in engine.add_job.call_args_list:
        assert call.kwargs['max_instances'] == 1 and call.kwargs['coalesce'] is True


@pytest.mark.parametrize('interval', [0, 4, 1441])
def test_invalid_ingestion_interval_starts_no_jobs(monkeypatch, interval):
    engine = Mock(running=False)
    monkeypatch.setattr(scheduler, 'scheduler', engine)
    with pytest.raises(ValueError):
        scheduler.start_scheduler(ingestion_enabled=True, ingestion_interval_minutes=interval)
    engine.start.assert_not_called()
    engine.add_job.assert_not_called()


def test_real_scheduler_runs_ingestion_without_generating_briefings(monkeypatch):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    async def scenario():
        completed = asyncio.Event()
        async def ingest():
            completed.set()
        engine = AsyncIOScheduler(timezone='UTC')
        monkeypatch.setattr(scheduler, 'scheduler', engine)
        monkeypatch.setattr(scheduler, 'run_ingestion_batch', ingest)
        deliveries = AsyncMock()
        monkeypatch.setattr(scheduler, 'check_due_users', deliveries)
        try:
            scheduler.start_scheduler(ingestion_enabled=True)
            await asyncio.wait_for(completed.wait(), timeout=2)
            assert [job.id for job in engine.get_jobs()] == ['morning_brief_news_ingestion']
            deliveries.assert_not_awaited()
        finally:
            scheduler.stop_scheduler()
            await asyncio.sleep(0)
    asyncio.run(scenario())


def test_feed_concurrency_is_bounded(monkeypatch):
    import threading
    active = maximum = 0
    guard = threading.Lock()
    barrier = threading.Barrier(batch.MAX_CONCURRENT_FEEDS, timeout=2)
    feeds = [{'name': str(n), 'url': f'https://feed.invalid/{n}', 'category': 'technology'}
             for n in range(batch.MAX_CONCURRENT_FEEDS * 2)]
    monkeypatch.setattr(batch, 'NEWS_SOURCES', feeds)
    monkeypatch.setattr(batch, 'resolve_category_ids', lambda: {'technology': 'id'})
    def ingest(**kwargs):
        nonlocal active, maximum
        with guard:
            active += 1
            maximum = max(maximum, active)
        barrier.wait()
        with guard:
            active -= 1
        return {'total': 1, 'inserted': 1}
    monkeypatch.setattr(batch, 'ingest_feed', ingest)
    result = asyncio.run(batch.run_ingestion_batch())
    assert result['failed_feeds'] == 0
    assert maximum == batch.MAX_CONCURRENT_FEEDS
    assert result['totals']['inserted'] == len(feeds)
