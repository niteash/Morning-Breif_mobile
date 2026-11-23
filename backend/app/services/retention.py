"""Bounded database retention. User content/audio is intentionally not deleted here."""
import logging
import os

from app.lib.supabase import admin_supabase

logger = logging.getLogger(__name__)


def run_retention() -> dict:
    values = {
        'p_request_days': int(os.getenv('GENERATION_REQUEST_RETENTION_DAYS', '30')),
        'p_notification_days': int(os.getenv('NOTIFICATION_RETENTION_DAYS', '30')),
        'p_billing_days': int(os.getenv('BILLING_EVENT_RETENTION_DAYS', '90')),
        'p_deletion_days': int(os.getenv('DELETION_JOB_RETENTION_DAYS', '30')),
    }
    result = admin_supabase.rpc('run_production_retention', values).execute().data
    if not isinstance(result, dict):
        raise RuntimeError('Invalid retention response')
    logger.info('Retention completed counts=%s', result)
    return result
