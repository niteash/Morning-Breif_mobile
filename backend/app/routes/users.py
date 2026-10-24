from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client


router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)


# =========================================
# Request Models
# =========================================

class UserPreferences(BaseModel):
    timezone: str = "Asia/Yangon"

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


class UserCategories(BaseModel):
    category_ids: list[UUID]


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
        response = (
            supabase
            .table("profiles")
            .select(
                """
                id,
                name,
                timezone,
                delivery_hour,
                delivery_minute,
                subscription_status
                """
            )
            .eq("id", user_id)
            .limit(1)
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

    except HTTPException:
        raise

    except Exception as error:
        print(
            "GET USER PREFERENCES ERROR:",
            str(error),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to get user preferences: "
                f"{str(error)}"
            ),
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

    print()
    print("=================================")
    print("UPDATING USER PREFERENCES")
    print("USER ID:", user_id)
    print("TIMEZONE:", preferences.timezone)
    print("DELIVERY HOUR:", preferences.delivery_hour)
    print("DELIVERY MINUTE:", preferences.delivery_minute)
    print("=================================")

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

        print(
            "EXISTING PROFILE:",
            existing.data,
        )

        # -----------------------------------------
        # Profile doesn't exist → create it
        # -----------------------------------------

        if not existing.data:
            print("PROFILE NOT FOUND")
            print("CREATING PROFILE...")

            create_response = (
                supabase
                .table("profiles")
                .insert({
                    "id": user_id,
                    "timezone": preferences.timezone,
                    "delivery_hour": preferences.delivery_hour,
                    "delivery_minute": preferences.delivery_minute,
                    "subscription_status": "free",
                })
                .execute()
            )

            print(
                "PROFILE CREATION RESPONSE:",
                create_response.data,
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

        response = (
            supabase
            .table("profiles")
            .update({
                "timezone": preferences.timezone,
                "delivery_hour": preferences.delivery_hour,
                "delivery_minute": preferences.delivery_minute,
            })
            .eq("id", user_id)
            .execute()
        )

        print(
            "PROFILE UPDATE RESPONSE:",
            response.data,
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
        import traceback

        print()
        print(
            "========== USER PREFERENCES ERROR =========="
        )
        print("ERROR:", str(error))
        traceback.print_exc()
        print(
            "============================================"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update user preferences: "
                f"{str(error)}"
            ),
        )

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
        print(
            "GET USER CATEGORIES ERROR:",
            str(error),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to get user categories: "
                f"{str(error)}"
            ),
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
        # Delete existing categories
        delete_response = (
            supabase
            .table("user_categories")
            .delete()
            .eq("user_id", user_id)
            .execute()
        )

        print(
            "OLD CATEGORIES DELETED:",
            delete_response.data,
        )

        # Create new rows
        rows = [
            {
                "user_id": user_id,
                "category_id": str(
                    category_id
                ),
            }
            for category_id
            in categories.category_ids
        ]

        print(
            "INSERTING CATEGORIES:",
            rows,
        )

        insert_response = (
            supabase
            .table("user_categories")
            .insert(rows)
            .execute()
        )

        if not insert_response.data:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Failed to update "
                    "user categories"
                ),
            )

        return {
            "message": (
                "Categories updated successfully"
            ),
            "categories": (
                insert_response.data
            ),
        }

    except HTTPException:
        raise

    except Exception as error:
        print(
            "UPDATE USER CATEGORIES ERROR:",
            str(error),
        )

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update user categories: "
                f"{str(error)}"
            ),
        )