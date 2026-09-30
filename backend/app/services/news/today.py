from datetime import datetime, timedelta, timezone

from app.lib.supabase import create_supabase_client


async def get_today_news(
    user_id: str,
    access_token: str,
    limit_per_category: int = 10,
):
    supabase = create_supabase_client(access_token)

    # --------------------------------------------------
    # 1. Get user's selected categories
    # --------------------------------------------------

    categories_response = (
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

    selected_categories = categories_response.data

    if not selected_categories:
        return []

    # --------------------------------------------------
    # 2. Calculate the recent-news time window
    # --------------------------------------------------

    now = datetime.now(timezone.utc)

    since = now - timedelta(hours=24)

    since_iso = since.isoformat()

    # --------------------------------------------------
    # 3. Get news for each selected category
    # --------------------------------------------------

    result = []

    for item in selected_categories:
        category_id = item["category_id"]
        category = item.get("categories")

        if not category:
            continue

        news_response = (
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
            .eq("category_id", category_id)
            .gte("published_at", since_iso)
            .order("published_at", desc=True)
            .limit(limit_per_category)
            .execute()
        )

        result.append(
            {
                "category": category,
                "stories": news_response.data,
            }
        )

    return result