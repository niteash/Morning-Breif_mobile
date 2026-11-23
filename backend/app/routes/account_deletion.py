import asyncio
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from app.dependencies.auth import get_verified_user
from app.lib.supabase import admin_supabase
from app.services.account_deletion import request_deletion

router = APIRouter(prefix='/api/v1/users/me', tags=['Account deletion'])


def deletion_enabled():
    return os.getenv('ACCOUNT_DELETION_ENABLED', 'false').lower() == 'true'


class DeleteConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmation: Literal['DELETE']


@router.get('/deletion')
async def deletion_status(user=Depends(get_verified_user)):
    try:
        response = await asyncio.to_thread(lambda: admin_supabase.table('account_deletion_jobs')
            .select('state').eq('user_id', user['user_id']).limit(1).execute())
        # Disabling new requests must not hide an already accepted deletion.
        return {'enabled': deletion_enabled(), 'status': 'requested' if response.data else None}
    except Exception as error:
        raise HTTPException(status_code=503, detail='Unable to check deletion status') from error


@router.delete('', status_code=202)
async def delete_my_account(body: DeleteConfirmation, user=Depends(get_verified_user)):
    if not deletion_enabled():
        raise HTTPException(status_code=503, detail='Account deletion is temporarily unavailable')
    try:
        return await asyncio.to_thread(request_deletion, user['user_id'], user['access_token'])
    except Exception as error:
        raise HTTPException(status_code=503, detail='Unable to confirm deletion. Please check its status and retry.') from error
