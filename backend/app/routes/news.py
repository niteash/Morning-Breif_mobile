from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client


router = APIRouter(
    prefix="/api/v1/news",
    tags=["News"],
)


@router.get("")
async def get_news(
    category_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    supabase = create_supabase_client(access_token)

    # If a specific category is requested,
    # return only that category.
    if category_id:
        response = (
            supabase
            .table("news_items")
            .select(
                """
                id,
                category_id,
                source,
                title,
                description,
                url,
                image_url,
                author,
                published_at,
                created_at
                """
            )
            .eq("category_id", str(category_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return {
            "news": response.data,
        }

    # Get the categories selected by this user.
    user_categories_response = (
        supabase
        .table("user_categories")
        .select("category_id")
        .eq("user_id", user_id)
        .execute()
    )

    selected_category_ids = [
        row["category_id"]
        for row in user_categories_response.data
    ]

    if not selected_category_ids:
        return {
            "news": [],
        }

    # Get news belonging to selected categories.
    response = (
        supabase
        .table("news_items")
        .select(
            """
            id,
            category_id,
            source,
            title,
            description,
            url,
            image_url,
            author,
            published_at,
            created_at
            """
        )
        .in_("category_id", selected_category_ids)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return {
        "news": response.data,
    }