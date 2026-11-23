from uuid import UUID
from datetime import datetime, timedelta, timezone
import logging
import os
from postgrest.exceptions import APIError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Literal

from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)
AUTOMATIC_BRIEFING_PREFERENCES_ENABLED = os.getenv(
    "AUTOMATIC_BRIEFING_PREFERENCES_ENABLED", "false"
).lower() == "true"


# =========================================
# Request Models
# =========================================

class UserPreferences(BaseModel):
    timezone: str = "Asia/Yangon"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("Use a valid IANA timezone")
        return value

    delivery_hour: int = Field(
        default=7,
        ge=0,
        le=23,
    )

    delivery_minute: int = Field(
        default=0,
        ge=0,
        le=59,
    )

    # Optional so older mobile clients can update time/timezone without
    # accidentally resetting the newer daily delivery preferences.
    automatic_briefing_enabled: bool | None = None
    daily_reminder_enabled: bool | None = None
    auto_play_when_open: bool | None = None
    delivery_schedule: Literal["daily", "weekdays"] | None = None
    briefing_length: Literal['quick', 'standard', 'detailed'] | None = None
    weekend_delivery_hour: int | None = Field(default=None, ge=0, le=23)
    weekend_delivery_minute: int | None = Field(default=None, ge=0, le=59)
    separate_weekend_schedule: bool | None = None
    breaking_news_enabled: bool | None = None
    data_saver_enabled: bool | None = None
    auto_download_wifi: bool | None = None
    listening_streak_enabled: bool | None = None
    horoscope_sign: Literal['aries','taurus','gemini','cancer','leo','virgo','libra','scorpio','sagittarius','capricorn','aquarius','pisces'] | None = None
    crypto_watchlist: list[Literal['BTC','ETH','SOL','XRP','BNB','DOGE','ADA','AVAX','DOT','LINK']] | None = Field(default=None, max_length=10)

    @field_validator('crypto_watchlist')
    @classmethod
    def unique_crypto_watchlist(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError('Choose each crypto asset once')
        return value


class UserCategories(BaseModel):
    category_ids: list[UUID] = Field(min_length=1, max_length=50)


class UserProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    phone_number: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{6,14}$")
    avatar_path: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f-]{36}/[0-9]{13}-[0-9a-f-]{36}\.(jpg|jpeg|png|webp)$",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ListeningProgressUpdate(BaseModel):
    briefing_id: UUID
    position_seconds: int = Field(ge=0, le=86400)
    listened_seconds: int = Field(ge=0, le=86400)
    completed: bool = False


@router.put('/me/listening-progress')
def update_listening_progress(payload: ListeningProgressUpdate,
                              current_user: dict = Depends(get_current_user)):
    client = create_supabase_client(current_user['access_token'])
    try:
        owned = (client.table('briefings').select('id,duration_seconds')
                 .eq('id', str(payload.briefing_id)).eq('user_id', current_user['user_id'])
                 .limit(1).execute().data or [])
        if not owned:
            raise HTTPException(404, 'Briefing not found')
        duration = owned[0].get('duration_seconds') or 86400
        position = min(payload.position_seconds, duration)
        rows = (client.table('listening_progress').upsert({
            'user_id': current_user['user_id'], 'briefing_id': str(payload.briefing_id),
            'position_seconds': position, 'listened_seconds': min(payload.listened_seconds, duration),
            'completed': payload.completed or position >= max(0, duration - 10),
            'last_listened_at': datetime.now(timezone.utc).isoformat(),
        }, on_conflict='user_id,briefing_id').execute().data or [])
        return {'progress': rows[0] if rows else None}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Listening progress is temporarily unavailable')


@router.get('/me/listening-summary')
def get_listening_summary(current_user: dict = Depends(get_current_user)):
    try:
        since = datetime.now(timezone.utc) - timedelta(days=7)
        rows = (create_supabase_client(current_user['access_token'])
                .table('listening_progress').select('listened_seconds,completed,last_listened_at')
                .eq('user_id', current_user['user_id']).gte('last_listened_at', since.isoformat())
                .order('last_listened_at', desc=True).execute().data or [])
        days = sorted({str(row['last_listened_at'])[:10] for row in rows}, reverse=True)
        streak = 0
        cursor = datetime.now(timezone.utc).date()
        for day in days:
            parsed = datetime.fromisoformat(day).date()
            if parsed == cursor or (streak == 0 and parsed == cursor - timedelta(days=1)):
                streak += 1; cursor = parsed - timedelta(days=1)
            elif parsed < cursor:
                break
        return {'minutes': round(sum(row.get('listened_seconds') or 0 for row in rows) / 60),
                'completed_briefings': sum(1 for row in rows if row.get('completed')),
                'streak_days': streak}
    except Exception:
        raise HTTPException(503, 'Listening summary is temporarily unavailable')


# =========================================
# GET USER PREFERENCES
# =========================================

@router.get("/me/preferences")
async def get_user_preferences(
    current_user: dict = Depends(
        get_current_user
    ),
):
    user_id = current_user["user_id"]
    access_token = current_user[
        "access_token"
    ]

    supabase = create_supabase_client(
        access_token
    )

    try:
        fields = "id,name,phone_number,avatar_path,timezone,delivery_hour,delivery_minute,subscription_status,briefing_length,weekend_delivery_hour,weekend_delivery_minute,separate_weekend_schedule,breaking_news_enabled,data_saver_enabled,auto_download_wifi,listening_streak_enabled,horoscope_sign,crypto_watchlist"
        if AUTOMATIC_BRIEFING_PREFERENCES_ENABLED:
            fields += ",automatic_briefing_enabled,daily_reminder_enabled,auto_play_when_open,delivery_schedule"
        response = (
            supabase.table("profiles").select(fields)
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found",
            )

        profile = response.data[0]
        if not AUTOMATIC_BRIEFING_PREFERENCES_ENABLED:
            profile.update({"automatic_briefing_enabled": False, "daily_reminder_enabled": False, "auto_play_when_open": False,
                            "delivery_schedule": "daily"})
        profile["automatic_delivery_preferences_available"] = AUTOMATIC_BRIEFING_PREFERENCES_ENABLED
        return {"profile": profile}

    except HTTPException:
        raise

    except Exception as error:
        logger.warning("Preference read failed: error_type=%s", type(error).__name__)

        raise HTTPException(
            status_code=500,
            detail="Failed to get user preferences. Please try again later.",
        )


# =========================================
# UPDATE USER PREFERENCES
# =========================================

@router.put("/me/preferences")
async def update_user_preferences(
    preferences: UserPreferences,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    automatic_fields = {"automatic_briefing_enabled", "daily_reminder_enabled", "auto_play_when_open", "delivery_schedule", "weekend_delivery_hour", "weekend_delivery_minute", "separate_weekend_schedule"}
    if not AUTOMATIC_BRIEFING_PREFERENCES_ENABLED and automatic_fields.intersection(preferences.model_fields_set):
        raise HTTPException(status_code=503, detail="Automatic delivery settings are not configured")

    supabase = create_supabase_client(access_token)

    try:
        # -----------------------------------------
        # Check whether profile already exists
        # -----------------------------------------

        existing = (
            supabase
            .table("profiles")
            .select("id")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )


        # -----------------------------------------
        # Profile doesn't exist → create it
        # -----------------------------------------

        if not existing.data:
            new_profile = {
                "id": user_id,
                "timezone": preferences.timezone,
                "delivery_hour": preferences.delivery_hour,
                "delivery_minute": preferences.delivery_minute,
                "subscription_status": "free",
            }
            if AUTOMATIC_BRIEFING_PREFERENCES_ENABLED:
                new_profile.update({
                    "automatic_briefing_enabled": preferences.automatic_briefing_enabled or False,
                    "daily_reminder_enabled": preferences.daily_reminder_enabled or False,
                    "auto_play_when_open": preferences.auto_play_when_open or False,
                    "delivery_schedule": preferences.delivery_schedule or "daily",
                })
            create_response = (
                supabase
                .table("profiles")
                .insert(new_profile)
                .execute()
            )

            if not create_response.data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create user profile",
                )

            return {
                "message": "Preferences saved successfully",
                "profile": create_response.data[0],
            }

        # -----------------------------------------
        # Profile exists → update it
        # -----------------------------------------

        updates = preferences.model_dump(exclude_unset=True)
        response = (
            supabase
            .table("profiles")
            .update(updates)
            .eq("id", user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to update user preferences",
            )

        return {
            "message": "Preferences updated successfully",
            "profile": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as error:
        logger.warning(
            "Preference update failed: error_type=%s", type(error).__name__
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to update user preferences. Please try again later.",
        )


@router.put("/me/profile")
async def update_user_profile(
    profile: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    updates = profile.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide a profile field to update")
    avatar_path = updates.get("avatar_path")
    if avatar_path is not None and not avatar_path.startswith(f"{user_id}/"):
        raise HTTPException(status_code=422, detail="Invalid profile image path")

    supabase = create_supabase_client(current_user["access_token"])
    try:
        response = (
            supabase.table("profiles")
            .update(updates)
            .eq("id", user_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="User profile not found")
        return {"message": "Profile updated successfully", "profile": response.data[0]}
    except HTTPException:
        raise
    except Exception as error:
        logger.warning("Profile update failed: error_type=%s", type(error).__name__)
        raise HTTPException(status_code=500, detail="Failed to update profile. Please try again later.")

# =========================================
# GET USER CATEGORIES
# =========================================

@router.get("/me/categories")
async def get_user_categories(
    current_user: dict = Depends(
        get_current_user
    ),
):
    user_id = current_user["user_id"]
    access_token = current_user[
        "access_token"
    ]

    supabase = create_supabase_client(
        access_token
    )

    try:
        response = (
            supabase
            .table("user_categories")
            .select(
                """
                category_id,
                categories(
                    id,
                    slug,
                    name_en,
                    name_my
                )
                """
            )
            .eq("user_id", user_id)
            .execute()
        )

        return {
            "categories": response.data
        }

    except Exception as error:
        logger.warning("Category read failed: error_type=%s", type(error).__name__)

        raise HTTPException(
            status_code=500,
            detail="Failed to get user categories. Please try again later.",
        )


# =========================================
# UPDATE USER CATEGORIES
# =========================================

@router.put("/me/categories")
async def update_user_categories(
    categories: UserCategories,
    current_user: dict = Depends(
        get_current_user
    ),
):
    user_id = current_user["user_id"]
    access_token = current_user[
        "access_token"
    ]

    if not categories.category_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one category "
                "must be selected"
            ),
        )

    supabase = create_supabase_client(
        access_token
    )

    try:
        response = supabase.rpc("replace_my_categories", {
            "p_category_ids": sorted({str(value) for value in categories.category_ids}),
        }).execute()
        if not response.data:
            raise HTTPException(status_code=503, detail="Unable to save categories. Please try again later.")
        return {"message": "Categories updated successfully", "categories": response.data}

    except HTTPException:
        raise

    except APIError as error:
        if error.code == "22023":
            raise HTTPException(status_code=422, detail="Select available categories and complete your profile first.")
        raise HTTPException(status_code=503, detail="Unable to save categories. Please try again later.")

    except Exception as error:
        logger.warning("Category update failed: error_type=%s", type(error).__name__)

        raise HTTPException(
            status_code=503,
            detail="Failed to update user categories. Please try again later.",
        )
