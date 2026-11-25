"""Private, operator-only operational visibility and maintenance controls."""
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.operator import require_operator
from app.lib.supabase import admin_supabase
from app.services.retention import run_retention

router = APIRouter(prefix='/api/v1/operations', tags=['operations'], dependencies=[Depends(require_operator)])


COUNT_COLUMNS = {
    'briefing_requests': 'id', 'notification_deliveries': 'id',
    'account_deletion_jobs': 'user_id', 'billing_events': 'event_id',
}


def _count(table: str, state: str | None = None, *, unprocessed: bool = False) -> int:
    query = admin_supabase.table(table).select(COUNT_COLUMNS[table], count='exact').limit(1)
    if state:
        query = query.eq('state', state)
    if unprocessed:
        query = query.is_('processed_at', 'null')
    response = query.execute()
    return int(response.count or 0)


@router.get('/status')
def operations_status():
    try:
        return {
            'generation': {state: _count('briefing_requests', state) for state in ('queued', 'selecting', 'checking_sources', 'writing', 'synthesizing', 'finalizing', 'failed')},
            'notifications': {state: _count('notification_deliveries', state) for state in ('pending', 'sending', 'dead')},
            'account_deletions': {state: _count('account_deletion_jobs', state) for state in ('pending', 'processing', 'failed')},
            'billing': {'unprocessed_events': _count('billing_events', unprocessed=True)},
        }
    except Exception:
        raise HTTPException(503, 'Operational status is temporarily unavailable') from None


@router.post('/retention/run')
def run_retention_now():
    try:
        return {'deleted': run_retention()}
    except Exception:
        raise HTTPException(503, 'Retention could not be completed') from None


@router.post('/recovery/retry')
def retry_failed_operations():
    """Requeue bounded, retryable failures without accepting client-supplied IDs."""
    try:
        result = admin_supabase.rpc('retry_failed_operations', {}).execute().data
        if not isinstance(result, dict):
            raise RuntimeError('Invalid recovery response')
        return {'requeued': result}
    except Exception:
        raise HTTPException(503, 'Failed operations could not be requeued') from None
