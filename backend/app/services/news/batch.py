"""Shared, bounded ingestion for the operator API and periodic worker."""
import asyncio
import logging
import os
import socket

from app.lib.supabase import admin_supabase, isolated_admin_supabase_client
from app.services.news.categories import resolve_category_ids
from app.services.news.ingest import ingest_feed
from app.services.news.sources import MAX_HEADLINE_AGE_HOURS, NEWS_SOURCES

logger = logging.getLogger(__name__)
MAX_CONCURRENT_FEEDS = 4
_batch_running = False
INGESTION_LEASE_NAME = 'rss_ingestion'
INGESTION_LEASE_SECONDS = 1800


class IngestionBusy(RuntimeError):
    pass


def _claim_ingestion_lease() -> str:
    owner = f"{socket.gethostname()[:48]}:{os.getpid()}"
    token = admin_supabase.rpc('claim_worker_lease', {
        'p_name': INGESTION_LEASE_NAME,
        'p_seconds': INGESTION_LEASE_SECONDS,
        'p_owner_hint': owner,
    }).execute().data
    if not token:
        raise IngestionBusy('An ingestion batch is already running')
    if not isinstance(token, str):
        raise RuntimeError('Invalid ingestion lease response')
    return token


def _release_ingestion_lease(token: str) -> None:
    try:
        admin_supabase.rpc('release_worker_lease', {
            'p_name': INGESTION_LEASE_NAME, 'p_token': token,
        }).execute()
    except Exception as error:
        # The lease expires on the database clock; a release outage cannot leave
        # ingestion permanently locked.
        logger.warning('RSS ingestion lease release deferred: error_type=%s', type(error).__name__)


def _ingest_feed_with_isolated_client(feed, category_ids):
    with isolated_admin_supabase_client() as database:
        return ingest_feed(
            feed_url=feed['url'],
            category_id=category_ids[feed['category']],
            source=feed['name'],
            database=database,
        )


async def ingest_one(feed, semaphore, category_ids):
    async with semaphore:
        base = {'source': feed['name'], 'category': feed['category'], 'feed_url': feed['url']}
        try:
            stats = await asyncio.to_thread(_ingest_feed_with_isolated_client, feed, category_ids)
            # A feed fetch can succeed even if its database writes fail.
            success = stats.get('skipped_insert_failure', 0) == 0
            return {**base, 'success': success, 'result': stats,
                    **({} if success else {'error': 'Some articles could not be stored. Please retry later.'})}
        except Exception as error:
            logger.warning('RSS feed failed: source=%s error_type=%s', feed['name'], type(error).__name__)
            return {**base, 'success': False, 'error': 'Feed ingestion failed. Please retry later.'}


async def run_ingestion_batch():
    global _batch_running
    if _batch_running:
        raise IngestionBusy('An ingestion batch is already running in this worker')
    _batch_running = True
    lease_token = None
    try:
        lease_token = await asyncio.to_thread(_claim_ingestion_lease)
        category_ids = await asyncio.to_thread(resolve_category_ids)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)
        results = await asyncio.gather(*(ingest_one(feed, semaphore, category_ids) for feed in NEWS_SOURCES))
        totals = {key: 0 for key in ('articles_seen', 'inserted', 'fresh_inserted', 'fallback_inserted',
                                    'skipped', 'skipped_insert_failure')}
        for result in results:
            # Include successful writes in partially failed feeds.
            stats = result.get('result', {})
            for key in totals:
                totals[key] += stats.get('total' if key == 'articles_seen' else key, 0)
        successful = sum(result['success'] for result in results)
        summary = {'message': 'RSS ingestion run completed', 'total_feeds': len(results),
                   'successful_feeds': successful, 'failed_feeds': len(results) - successful,
                   'max_article_age_hours': MAX_HEADLINE_AGE_HOURS, 'totals': totals, 'results': results}
        logger.info('RSS batch complete: successful=%s failed=%s articles_seen=%s inserted=%s write_failures=%s',
                    successful, summary['failed_feeds'], totals['articles_seen'], totals['inserted'],
                    totals['skipped_insert_failure'])
        return summary
    finally:
        if lease_token:
            await asyncio.to_thread(_release_ingestion_lease, lease_token)
        _batch_running = False
