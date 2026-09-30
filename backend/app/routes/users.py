from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client


router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)


# =========================
# Request Models
# =========================

class UserPreferences(BaseModel):
    timezone: str = "Asia/Yangon"
    delivery_hour: int = Field(default=7, ge=0, le=23)
    delivery_minute: int = Field(default=0, ge=0, le=59)


class UserCategories(BaseModel):
    category_ids: list[UUID]


# =========================
# Preferences
# =========================

@router.get("/me/preferences")
async def get_user_preferences(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    supabase = create_supabase_client(access_token)

    response = (
        supabase
        .table("profiles")
        .select(
            "id, name, timezone, delivery_hour, "
            "delivery_minute, subscription_status"
        )
        .eq("id", user_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="User profile not found",
        )

    return {
        "profile": response.data[0]
    }


@router.put("/me/preferences")
async def update_user_preferences(
    preferences: UserPreferences,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    supabase = create_supabase_client(access_token)

    response = (
        supabase
        .table("profiles")
        .update(
            {
                "timezone": preferences.timezone,
                "delivery_hour": preferences.delivery_hour,
                "delivery_minute": preferences.delivery_minute,
            }
        )
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


# =========================
# Categories
# =========================

@router.get("/me/categories")
async def get_user_categories(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    supabase = create_supabase_client(access_token)

    response = (
        supabase
        .table("user_categories")
        .select(
            "category_id, categories(id, slug, name_en, name_my)"
        )
        .eq("user_id", user_id)
        .execute()
    )

    return {
        "categories": response.data
    }


@router.put("/me/categories")
async def update_user_categories(
    categories: UserCategories,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    if not categories.category_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one category must be selected",
        )

    supabase = create_supabase_client(access_token)

    # Remove existing selections
    delete_response = (
        supabase
        .table("user_categories")
        .delete()
        .eq("user_id", user_id)
        .execute()
    )

    # Insert new selections
    rows = [
        {
            "user_id": user_id,
            "category_id": str(category_id),
        }
        for category_id in categories.category_ids
    ]

    insert_response = (
        supabase
        .table("user_categories")
        .insert(rows)
        .execute()
    )

    if not insert_response.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to update user categories",
        )

    return {
        "message": "Categories updated successfully",
        "categories": insert_response.data,
    }