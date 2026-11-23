"""Durable worker for on-demand briefing requests."""
import asyncio
import logging

from app.lib.supabase import admin_supabase
from app.services.briefing.jobs import (
    GenerationBusy,
    GenerationDisabled,
    GenerationLimited,
    generate_and_save,
)
from app.services.entitlements import EntitlementUnavailable, TrialAccessDenied, get_trial
from app.services.scheduler import collect_user_news

logger = logging.getLogger(__name__)
LENGTH_MINUTES = {'quick': 3, 'standard': 7, 'detailed': 13}


def _update(job: dict, state: str, progress: int, message: str) -> None:
    accepted = admin_supabase.rpc('update_briefing_request', {
        'p_id': job['id'], 'p_lease_token': job['lease_token'],
        'p_state': state, 'p_progress': progress, 'p_message': message,
    }).execute().data
    if accepted is not True:
        raise RuntimeError('Generation request lease was lost')


def process_one_request() -> bool:
    job = admin_supabase.rpc('claim_briefing_request', {}).execute().data
    if not job:
        return False
    try:
        categories = collect_user_news(job['user_id'])
        if not categories:
            raise ValueError('no_recent_news')
        _update(job, 'checking_sources', 25, 'Checking sources')
        length = job.get('length') if job.get('length') in LENGTH_MINUTES else 'standard'
        entitlement = get_trial(job['user_id'])
        if length != 'standard' and entitlement.get('entitlement_kind') != 'purchase':
            raise TrialAccessDenied('Premium length required')
        saved, _ = generate_and_save(
            job['user_id'], job['briefing_date'], categories,
            # Every explicit request must be able to replace audio created for an
            # older category selection. The request key keeps retries idempotent;
            # the database attempt fence still limits daily provider spend.
            regeneration_id=job['request_key'],
            target_minutes=LENGTH_MINUTES[length],
            progress=lambda state, percent, message: _update(job, state, percent, message),
        )
        accepted = admin_supabase.rpc('finish_briefing_request', {
            'p_id': job['id'], 'p_lease_token': job['lease_token'],
            'p_briefing_id': saved['id'],
        }).execute().data
        if accepted is not True:
            raise RuntimeError('Generation request completion was rejected')
    except (TrialAccessDenied, EntitlementUnavailable) as error:
        _fail(job, 'entitlement_unavailable', 'Your plan does not currently allow generation')
        logger.info('Queued generation denied: category=%s', type(error).__name__)
    except GenerationLimited:
        _fail(job, 'generation_limit_reached', 'Today’s manual generation limit has been reached')
    except GenerationBusy:
        _fail(job, 'generation_in_progress', 'A briefing is already being prepared')
    except GenerationDisabled:
        _fail(job, 'generation_disabled', 'Audio generation is not configured on this backend')
    except ValueError:
        _fail(job, 'no_recent_news', 'No current stories are available in your selected categories')
    except Exception as error:
        _fail(job, 'generation_failed', 'Generation failed temporarily. Please try again.')
        logger.error('Queued generation failed: error_type=%s', type(error).__name__)
    return True


def _fail(job: dict, code: str, message: str) -> None:
    try:
        admin_supabase.rpc('fail_briefing_request', {
            'p_id': job['id'], 'p_lease_token': job['lease_token'],
            'p_error_code': code, 'p_message': message,
        }).execute()
    except Exception:
        logger.warning('Could not mark queued generation failed; lease will expire')


async def process_generation_requests() -> None:
    # One paid provider job per tick prevents unexpected burst spend. Multiple API
    # processes remain safe because database claims use SKIP LOCKED and leases.
    await asyncio.to_thread(process_one_request)
