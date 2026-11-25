"""Bounded durable notification worker. Database leases survive process restarts."""
import asyncio
import logging
from datetime import datetime, timezone

from app.lib.supabase import admin_supabase
from app.services.push_notifications import initialize_firebase, send_briefing_notification, send_breaking_news_notification

logger = logging.getLogger(__name__)
WORKERS = 4
CLAIMS_PER_WORKER = 5


def deliver_one() -> bool:
    job = admin_supabase.rpc('claim_notification_delivery', {}).execute().data
    if not job:
        return False
    remaining = int((datetime.fromisoformat(job['expires_at']) - datetime.now(timezone.utc)).total_seconds())
    outcome = send_briefing_notification(
        job['fcm_token'], job['briefing_id'], job['briefing_date'], job['id'], remaining
    ) if remaining > 0 else 'retry'
    accepted = admin_supabase.rpc('finish_notification_delivery', {
        'p_id': job['id'], 'p_lease_token': job['lease_token'], 'p_outcome': outcome,
    }).execute().data
    if not accepted:
        logger.warning('Notification result rejected: expired or superseded lease')
    return True


async def deliver_pending_notifications() -> None:
    # Missing Firebase configuration must not consume database retry attempts.
    if not await asyncio.to_thread(initialize_firebase):
        logger.warning('Notification worker paused: Firebase is unavailable')
        return

    async def work():
        for _ in range(CLAIMS_PER_WORKER):
            try:
                if not await asyncio.to_thread(deliver_one):
                    break
            except Exception as error:
                # A failed acknowledgement leaves the lease to expire for retry.
                logger.warning('Notification worker failed: error_type=%s', type(error).__name__)
                break
    await asyncio.gather(*(work() for _ in range(WORKERS)))


async def deliver_breaking_notifications() -> None:
    if not await asyncio.to_thread(initialize_firebase):
        return
    async def breaking_work():
        for _ in range(CLAIMS_PER_WORKER):
            try:
                job = await asyncio.to_thread(
                    lambda: admin_supabase.rpc('claim_breaking_news_delivery', {}).execute().data)
                if not job:
                    break
                remaining = int((datetime.fromisoformat(job['expires_at']) - datetime.now(timezone.utc)).total_seconds())
                outcome = await asyncio.to_thread(
                    send_breaking_news_notification, job['fcm_token'], job['news_id'],
                    job['headline'], job['publisher'], job['id'], remaining,
                ) if remaining > 0 else 'retry'
                accepted = await asyncio.to_thread(
                    lambda: admin_supabase.rpc('finish_breaking_news_delivery', {
                        'p_id': job['id'], 'p_lease_token': job['lease_token'],
                        'p_outcome': outcome,
                    }).execute().data)
                if outcome == 'invalid':
                    await asyncio.to_thread(lambda: admin_supabase.table('device_tokens').update(
                        {'is_active': False}).eq('id', job['device_id']).execute())
                if accepted is not True:
                    logger.warning('Breaking-news result rejected: expired or superseded lease')
            except Exception as error:
                logger.warning('Breaking-news worker failed: error_type=%s', type(error).__name__)
                break
    await asyncio.gather(*(breaking_work() for _ in range(2)))


async def deliver_all_notifications() -> None:
    await asyncio.gather(deliver_pending_notifications(), deliver_breaking_notifications())
