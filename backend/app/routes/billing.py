"""Signed RevenueCat webhook. Payloads are used only to trigger canonical refresh."""
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.lib.supabase import admin_supabase
from app.services.entitlements import refresh_purchase_entitlement

router = APIRouter(prefix='/api/v1/billing', tags=['billing'])
logger = logging.getLogger(__name__)


def _process_event(event_id: str, user_id: str) -> None:
    error_code = None
    try:
        refresh_purchase_entitlement(user_id)
    except Exception as error:
        error_code = type(error).__name__[:80]
        logger.warning('Billing refresh failed: error_type=%s', type(error).__name__)
    try:
        admin_supabase.table('billing_events').update({
            'processed_at': datetime.now(timezone.utc).isoformat(), 'error_code': error_code,
        }).eq('event_id', event_id).execute()
    except Exception as error:
        logger.warning('Billing event completion unavailable: error_type=%s', type(error).__name__)


@router.post('/revenuecat', status_code=status.HTTP_202_ACCEPTED)
async def revenuecat_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
):
    secret = os.getenv('REVENUECAT_WEBHOOK_AUTH', '').strip()
    if not secret:
        raise HTTPException(status_code=503, detail='Billing webhook is not configured')
    expected = f'Bearer {secret}'
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail='Invalid webhook authorization')
    content_length = request.headers.get('content-length')
    if content_length:
        try:
            if int(content_length) > 64_000:
                raise HTTPException(status_code=413, detail='Webhook payload is too large')
        except ValueError:
            raise HTTPException(status_code=400, detail='Invalid content length') from None
    try:
        body = await request.body()
        if len(body) > 64_000:
            raise HTTPException(status_code=413, detail='Webhook payload is too large')
        payload = json.loads(body)
        event = payload.get('event') if isinstance(payload, dict) else None
        event_id = event.get('id') if isinstance(event, dict) else None
        event_type = event.get('type') if isinstance(event, dict) else None
        raw_user_id = event.get('app_user_id') if isinstance(event, dict) else None
        if not raw_user_id and isinstance(event, dict) and isinstance(event.get('transferred_to'), list):
            raw_user_id = next((value for value in event['transferred_to'] if isinstance(value, str)), None)
        environment = str(event.get('environment') or 'unknown').lower() if isinstance(event, dict) else 'unknown'
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 160:
            raise ValueError('event id')
        if not isinstance(event_type, str) or not 1 <= len(event_type) <= 80:
            raise ValueError('event type')
        try:
            user_id = str(UUID(raw_user_id)) if isinstance(raw_user_id, str) else None
        except ValueError:
            user_id = None  # Anonymous/legacy RevenueCat IDs cannot map to an account.
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail='Invalid webhook payload') from None
    environment = environment if environment in {'production', 'sandbox'} else 'unknown'
    try:
        existing = (admin_supabase.table('billing_events').select('event_id,app_user_id,processed_at,error_code')
                    .eq('event_id', event_id).limit(1).execute().data or [])
        if existing:
            retry_user = existing[0].get('app_user_id')
            if retry_user and (not existing[0].get('processed_at') or existing[0].get('error_code')):
                background_tasks.add_task(_process_event, event_id, retry_user)
            return {'accepted': True, 'duplicate': True}
        admin_supabase.table('billing_events').insert({
            'event_id': event_id, 'event_type': event_type,
            'app_user_id': user_id, 'environment': environment,
        }).execute()
    except Exception as error:
        logger.warning('Billing webhook persistence failed: error_type=%s', type(error).__name__)
        raise HTTPException(status_code=503, detail='Billing event could not be persisted') from None
    if user_id:
        background_tasks.add_task(_process_event, event_id, user_id)
    return {'accepted': True, 'duplicate': False}
