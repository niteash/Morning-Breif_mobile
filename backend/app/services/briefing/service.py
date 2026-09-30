from datetime import datetime, timezone

from app.lib.supabase import admin_supabase
from app.services.news.selector import select_recent_stories

from .generator import generate_briefing_script
from .prompt import build_briefing_prompt


async def generate_user_briefing(
    user_id: str,
    access_token: str,
):
    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    # -----------------------------------------
    # 1. Get today's existing briefing
    # -----------------------------------------

    existing = (
        admin_supabase
        .table("briefings")
        .select("*")
        .eq("user_id", user_id)
        .eq("briefing_date", today)
        .limit(1)
        .execute()
    )

    if existing.data:
        briefing = existing.data[0]

        if briefing["status"] == "ready":
            return briefing

        briefing_id = briefing["id"]

        (
            admin_supabase
            .table("briefings")
            .update({
                "status": "generating",
            })
            .eq("id", briefing_id)
            .execute()
        )

    else:
        response = (
            admin_supabase
            .table("briefings")
            .insert({
                "user_id": user_id,
                "briefing_date": today,
                "title": "Morning Brief",
                "status": "generating",
            })
            .execute()
        )

        if not response.data:
            raise RuntimeError(
                "Failed to create briefing"
            )

        briefing_id = response.data[0]["id"]

    # -----------------------------------------
    # 2. Select personalized stories
    # -----------------------------------------

    categories = await select_recent_stories(
        user_id=user_id,
        access_token=access_token,
        stories_per_category=5,
        hours=24,
    )

    categories_with_stories = [
        category
        for category in categories
        if category.get("stories")
    ]

    if not categories_with_stories:

        (
            admin_supabase
            .table("briefings")
            .update({
                "status": "failed",
            })
            .eq("id", briefing_id)
            .execute()
        )

        raise RuntimeError(
            "No recent news available"
        )

    # -----------------------------------------
    # 3. Build Gemini prompt
    # -----------------------------------------

    prompt = build_briefing_prompt(
        categories_with_stories
    )

    # -----------------------------------------
    # 4. Generate Burmese script
    # -----------------------------------------

    try:

        script = generate_briefing_script(
            prompt
        )

    except Exception as error:

        (
            admin_supabase
            .table("briefings")
            .update({
                "status": "failed",
            })
            .eq("id", briefing_id)
            .execute()
        )

        raise error

    # -----------------------------------------
    # 5. Save script
    # -----------------------------------------

    response = (
        admin_supabase
        .table("briefings")
        .update({
            "script": script,
            "status": "ready",
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        })
        .eq("id", briefing_id)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Failed to save briefing"
        )

    # -----------------------------------------
    # 6. Save stories
    # -----------------------------------------

    story_rows = []

    position = 1

    for category in categories_with_stories:

        category_info = category.get(
            "category",
            {}
        )

        category_id = category_info.get(
            "id"
        )

        for story in category.get(
            "stories",
            []
        ):

            story_rows.append({
                "briefing_id": briefing_id,
                "news_item_id": story["id"],
                "category_id": category_id,
                "position": position,
            })

            position += 1

    # Remove previous story relationships

    (
        admin_supabase
        .table("briefing_stories")
        .delete()
        .eq(
            "briefing_id",
            briefing_id,
        )
        .execute()
    )

    if story_rows:

        (
            admin_supabase
            .table("briefing_stories")
            .insert(story_rows)
            .execute()
        )

    return response.data[0]