import asyncio
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.auth import get_current_user
from app.services.entitlements import get_trial, claim_trial, EntitlementUnavailable

router = APIRouter(prefix='/api/v1/entitlements', tags=['Entitlements'])


async def run(operation, user):
    try:
        return await asyncio.to_thread(operation, user['user_id'])
    except EntitlementUnavailable as error:
        detail = (
            'Trial database migration is not installed'
            if error.category == 'migration_missing'
            else 'Entitlement status is temporarily unavailable'
        )
        raise HTTPException(status_code=503, detail=detail) from None


@router.get('/me')
async def status(user: dict = Depends(get_current_user)):
    return await run(get_trial, user)


@router.post('/claim')
async def claim(user: dict = Depends(get_current_user)):
    return await run(claim_trial, user)
