"""Authoritative DB-clock entitlement; public device grants deliberately fail closed."""
import os
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests
from app.lib.supabase import admin_supabase

STAGING_URL = 'https://wwtntxknfjagdjdgiaxu.supabase.co'
STATES = {'trial_active', 'trial_ended', 'verification_required', 'onboarding_required', 'claim_required'}
logger = logging.getLogger(__name__)
RPC_NAMES = {'get_account_trial', 'claim_staging_account_trial'}
DATABASE_CODE_RE = re.compile(r'^[A-Z0-9_-]{1,24}$')
REVENUECAT_API_URL = 'https://api.revenuecat.com/v1/subscribers/'


class EntitlementUnavailable(Exception):
    def __init__(self, message: str = 'Trial status is temporarily unavailable', category: str = 'database_unavailable'):
        super().__init__(message)
        self.category = category


class TrialAccessDenied(Exception):
    pass


def is_staging() -> bool:
    return os.getenv('APP_ENV') == 'staging' and os.getenv('SUPABASE_URL', '').rstrip('/') == STAGING_URL


def staging_claim_enabled() -> bool:
    return is_staging() and os.getenv('TRIAL_STAGING_ACCOUNT_ENABLED', 'false').lower() == 'true'


def _cached_purchase_entitlement(user_id: str, *, max_age_seconds: int | None = None) -> tuple[bool, dict | None]:
    """Return (cache_hit, entitlement). Missing migrations degrade to a live check."""
    ttl = max_age_seconds if max_age_seconds is not None else int(os.getenv('REVENUECAT_CACHE_SECONDS', '300'))
    ttl = max(30, min(ttl, 86_400))
    try:
        rows = (admin_supabase.table('purchase_entitlements')
                .select('active,expires_at,checked_at')
                .eq('user_id', user_id).limit(1).execute().data or [])
        if not rows:
            return False, None
        row = rows[0]
        checked_at = _timestamp(row.get('checked_at'))
        if checked_at < datetime.now(timezone.utc) - timedelta(seconds=ttl):
            return False, None
        expires_at = _timestamp(row['expires_at']) if row.get('expires_at') else None
        if not row.get('active') or (expires_at and datetime.now(timezone.utc) >= expires_at):
            return True, None
        return True, {
            'status': 'subscription_active', 'expires_at': expires_at.isoformat() if expires_at else None,
            'can_generate': True, 'claim_mode': 'device_required', 'entitlement_kind': 'purchase',
        }
    except Exception:
        return False, None


def _write_purchase_cache(user_id: str, *, active: bool, expires_at: datetime | None,
                          environment: str = 'unknown') -> None:
    try:
        admin_supabase.table('purchase_entitlements').upsert({
            'user_id': user_id,
            'active': active,
            'expires_at': expires_at.isoformat() if expires_at else None,
            'environment': environment if environment in {'production', 'sandbox'} else 'unknown',
            'source': 'revenuecat',
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }, on_conflict='user_id').execute()
    except Exception as error:
        logger.info('Purchase cache write unavailable: error_type=%s', type(error).__name__)


def _purchase_entitlement(user_id: str, *, force: bool = False) -> dict | None:
    api_key = os.getenv('REVENUECAT_API_KEY', '').strip()
    entitlement_id = os.getenv('REVENUECAT_ENTITLEMENT_ID', 'premium').strip()
    if not api_key:
        return None
    if not entitlement_id or len(entitlement_id) > 128:
        raise EntitlementUnavailable('Purchase configuration is invalid', 'billing_configuration')
    if not force:
        hit, cached = _cached_purchase_entitlement(user_id)
        if hit:
            return cached
    try:
        response = requests.get(
            REVENUECAT_API_URL + quote(user_id, safe=''),
            headers={'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'},
            timeout=6,
            allow_redirects=False,
        )
        if response.status_code == 404:
            _write_purchase_cache(user_id, active=False, expires_at=None)
            return None
        if response.status_code != 200:
            raise RuntimeError(f'revenuecat_http_{response.status_code}')
        payload = response.json()
        subscriber = payload.get('subscriber') if isinstance(payload, dict) else None
        entitlement = subscriber.get('entitlements', {}).get(entitlement_id) if isinstance(subscriber, dict) else None
        if not isinstance(entitlement, dict):
            _write_purchase_cache(user_id, active=False, expires_at=None)
            return None
        expires_at = entitlement.get('expires_date')
        grace_at = entitlement.get('grace_period_expires_date')
        candidates = []
        for value in (expires_at, grace_at):
            if value is not None:
                candidates.append(_timestamp(value))
        active_until = max(candidates) if candidates else None
        active = entitlement.get('refunded_at') is None and (
            active_until is None or datetime.now(timezone.utc) < active_until
        )
        environment = 'sandbox' if entitlement.get('is_sandbox') is True else 'production'
        _write_purchase_cache(user_id, active=active, expires_at=active_until, environment=environment)
        if not active:
            return None
        return {
            'status': 'subscription_active',
            'expires_at': active_until.isoformat() if active_until else None,
            'can_generate': True,
            'claim_mode': 'device_required',
            'entitlement_kind': 'purchase',
        }
    except EntitlementUnavailable:
        raise
    except Exception as error:
        logger.warning('Purchase verification failed: error_type=%s', type(error).__name__)
        grace = max(300, min(int(os.getenv('REVENUECAT_CACHE_GRACE_SECONDS', '86400')), 86_400))
        hit, cached = _cached_purchase_entitlement(user_id, max_age_seconds=grace)
        if hit and cached:
            logger.info('Using recently verified unexpired purchase during billing outage')
            return cached
        raise EntitlementUnavailable('Purchase verification is temporarily unavailable', 'billing_unavailable') from error


def refresh_purchase_entitlement(user_id: str) -> dict | None:
    """Refresh canonical RevenueCat state after a signed webhook."""
    return _purchase_entitlement(user_id, force=True)


def _timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Invalid entitlement timestamp')
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Entitlement timestamp requires a timezone')
    return parsed


def _read(rpc: str, user_id: str) -> dict:
    try:
        data = admin_supabase.rpc(rpc, {'p_user_id': user_id}).execute().data
        if not isinstance(data, dict) or data.get('status') not in STATES or not data.get('server_now'):
            raise ValueError('Invalid entitlement response')
        server_now = _timestamp(data['server_now'])
        if data['status'] in {'trial_active', 'trial_ended'}:
            started_at, expires_at = _timestamp(data.get('started_at')), _timestamp(data.get('expires_at'))
            if data.get('grant_scope') not in {'staging_account', 'android_device'} or not started_at <= server_now or not started_at < expires_at:
                raise ValueError('Invalid trial')
            # Validate against the database clock, never the mobile clock.
            if (data['status'] == 'trial_active') != (server_now < expires_at):
                raise ValueError('Inconsistent trial status')
        elif any(data.get(field) is not None for field in ('started_at', 'expires_at', 'grant_scope')):
            raise ValueError('Unclaimed entitlement contains a grant')
        return dict(data)
    except Exception as error:
        # Keep diagnostics useful without logging exception text, account IDs, URLs,
        # SQL parameters, bearer tokens, or any user data.
        raw_code = getattr(error, 'code', None)
        db_code = raw_code if isinstance(raw_code, str) and DATABASE_CODE_RE.fullmatch(raw_code) else 'none'
        category = (
            'migration_missing' if db_code in {'PGRST202', 'PGRST205', '42P01', '42883'}
            else 'permission_denied' if db_code == '42501'
            else 'invalid_response' if isinstance(error, (ValueError, TypeError))
            else 'database_unavailable'
        )
        # One formatting placeholder and one sanitized mapping avoids malformed
        # logging arguments and never includes the user ID or provider message.
        logger.error('Entitlement RPC failed diagnostics=%s', {
            'rpc': rpc if rpc in RPC_NAMES else 'unknown',
            'category': category,
            'db_code': db_code,
            'error_type': type(error).__name__,
        })
        message = 'Trial database migration is not installed' if category == 'migration_missing' else 'Trial status is temporarily unavailable'
        raise EntitlementUnavailable(message, category) from error


def get_trial(user_id: str) -> dict:
    result = _read('get_account_trial', user_id)
    # Staging-only grants cannot authorize generation in a public environment.
    allowed = result['status'] == 'trial_active' and (result['grant_scope'] == 'android_device' or is_staging())
    result['can_generate'] = allowed
    result['claim_mode'] = 'staging_account' if staging_claim_enabled() else 'device_required'
    if result['status'] == 'claim_required' and not staging_claim_enabled():
        result.update(status='claim_unavailable', reason='device_verification_unavailable')
    if result.get('grant_scope') == 'staging_account' and not is_staging():
        result.update(status='claim_unavailable', reason='staging_grant_not_public')
    try:
        purchase = _purchase_entitlement(user_id)
    except EntitlementUnavailable:
        # A valid database trial remains usable during a billing-provider outage.
        if allowed:
            result['billing_status'] = 'temporarily_unavailable'
            return result
        raise
    entitlement = purchase or result
    # Usage is informational and must never turn a valid entitlement read into
    # an outage. The database claim remains the authoritative spend fence.
    try:
        rows = (admin_supabase.table('briefing_generation_jobs').select('attempts')
                .eq('user_id', user_id).eq('briefing_date', datetime.now(timezone.utc).date().isoformat())
                .limit(1).execute().data or [])
        used = int(rows[0].get('attempts') or 0) if rows else 0
        entitlement['generation_usage'] = {'used': max(0, min(used, 3)), 'limit': 3, 'remaining': max(0, 3 - used)}
    except Exception:
        pass
    return entitlement


def claim_trial(user_id: str) -> dict:
    current = get_trial(user_id)
    # Existing entitlement is returned unchanged, even after email/password/device changes.
    if current.get('started_at') or current['status'] in {'verification_required', 'onboarding_required'}:
        return current
    if not staging_claim_enabled():
        return current  # No public fallback, even if the client supplies a device ID/token.
    _read('claim_staging_account_trial', user_id)
    return get_trial(user_id)


def require_generation_access(user_id: str) -> None:
    if not get_trial(user_id)['can_generate']:
        raise TrialAccessDenied('An active trial is required for new generation')
