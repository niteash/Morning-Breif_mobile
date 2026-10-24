import logging

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.lib.supabase import admin_supabase

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/push",
    tags=["Push Notifications"],
)


class RegisterDeviceRequest(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    platform: str = Field(default="android")


def get_user_id(user) -> str:
    """Extract the authenticated user ID from supported auth responses."""

    if isinstance(user, dict):
        user_id = (
            user.get("user_id")
            or user.get("id")
            or user.get("sub")
        )
    else:
        user_id = (
            getattr(user, "user_id", None)
            or getattr(user, "id", None)
            or getattr(user, "sub", None)
        )

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user ID is missing.",
        )

    return str(user_id)
@router.post("/register")
async def register_device(
    request: RegisterDeviceRequest,
    user=Depends(get_current_user),
):
    """Register or reactivate an FCM token for the current user."""

    user_id = get_user_id(user)
    platform = request.platform.lower().strip()

    if platform not in {"android", "ios", "web"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported platform.",
        )

    token = request.token.strip()

    if not token:
        raise HTTPException(
            status_code=400,
            detail="FCM token cannot be empty.",
        )

    try:
        # Reassigning the token allows a device to change accounts.
        # The token's UNIQUE constraint prevents duplicate records.
        response = (
            admin_supabase.table("device_tokens")
            .upsert(
                {
                    "user_id": user_id,
                    "fcm_token": token,
                    "platform": platform,
                    "is_active": True,
                    "updated_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                },
                on_conflict="fcm_token",
            )
            .execute()
        )

        if not response.data:
            raise RuntimeError(
                "Supabase did not return the registered device."
            )

        return {
            "success": True,
            "message": "Device registered for push notifications.",
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to register device for user %s.",
            user_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not register the device.",
        )


@router.delete("/unregister")
async def unregister_device(
    request: RegisterDeviceRequest,
    user=Depends(get_current_user),
):
    """Deactivate an FCM token belonging to the current user."""

    user_id = get_user_id(user)

    try:
        (
            admin_supabase.table("device_tokens")
            .update({
                "is_active": False,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            })
            .eq("user_id", user_id)
            .eq("fcm_token", request.token.strip())
            .execute()
        )

        return {
            "success": True,
            "message": "Device unregistered.",
        }

    except Exception:
        logger.exception(
            "Failed to unregister device for user %s.",
            user_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not unregister the device.",
        )