"""Durable account cleanup; never accepts user IDs or object paths from the client."""
import asyncio
import logging
from uuid import UUID

from supabase_auth.errors import AuthApiError
from app.lib.supabase import admin_supabase

logger = logging.getLogger(__name__)


def account_is_active(user_id: str) -> bool:
    result = admin_supabase.rpc('account_is_active', {'p_user_id': user_id}).execute().data
    if not isinstance(result, bool):
        raise RuntimeError('Account availability check failed')
    return result


def request_deletion(user_id: str, access_token: str) -> dict:
    job = admin_supabase.rpc('request_account_deletion', {'p_user_id': user_id}).execute().data
    if not isinstance(job, dict) or job.get('user_id') != user_id:
        raise RuntimeError('Deletion request was not recorded')
    try:
        admin_supabase.auth.admin.sign_out(access_token, scope='global')
    except Exception as error:
        # The durable marker/RLS already denies account activity; the worker bans
        # and deletes Auth even if session revocation is temporarily unavailable.
        logger.warning('Deletion session revocation deferred: error_type=%s', type(error).__name__)
    return {'status': 'requested', 'requested_at': job['requested_at']}


def _ignore_missing_user(operation):
    try:
        operation()
    except AuthApiError as error:
        if error.status != 404:
            raise


def clean_audio(job: dict) -> None:
    user_id = str(UUID(job['user_id']))
    params = {'p_user_id': user_id, 'p_lease_token': job['lease_token']}
    for _ in range(20):
        paths = admin_supabase.rpc('deletion_object_paths', params).execute().data
        if not isinstance(paths, list):
            raise RuntimeError('Invalid deletion inventory')
        if not paths:
            return
        if any(not isinstance(path, str) or not path.startswith(user_id + '/')
               or any(part in ('', '.', '..') for part in path.split('/')) for path in paths):
            raise RuntimeError('Unsafe deletion inventory')
        # Storage API deletes the object bytes and metadata together. Never SQL-delete storage.objects.
        admin_supabase.storage.from_('briefings').remove(paths)
    raise RuntimeError('More audio remains; cleanup will continue on a later attempt')


def process_one_deletion() -> bool:
    job = admin_supabase.rpc('claim_account_deletion', {}).execute().data
    if not job:
        return False
    params = {'p_user_id': job['user_id'], 'p_lease_token': job['lease_token']}
    try:
        _ignore_missing_user(lambda: admin_supabase.auth.admin.update_user_by_id(job['user_id'], {'ban_duration': '876000h'}))
        clean_audio(job)
        _ignore_missing_user(lambda: admin_supabase.auth.admin.delete_user(job['user_id']))
        # Sweep again after Auth deletion; the upload path also checks before and after upload.
        clean_audio(job)
        accepted = admin_supabase.rpc('finish_account_deletion', {**params, 'p_success': True}).execute().data
        if accepted is not True:
            raise RuntimeError('Deletion lease was superseded')
    except Exception as error:
        logger.warning('Account cleanup deferred: error_type=%s', type(error).__name__)
        try:
            admin_supabase.rpc('finish_account_deletion', {**params, 'p_success': False}).execute()
        except Exception:
            logger.warning('Deletion lease will expire for retry')
    return True


async def process_account_deletions() -> None:
    # Sequential, bounded external operations; DB lease supports worker restart.
    for _ in range(4):
        try:
            if not await asyncio.to_thread(process_one_deletion):
                break
        except Exception as error:
            logger.warning('Account deletion worker unavailable: error_type=%s', type(error).__name__)
            break
