from app.lib.supabase import admin_supabase

from .relevance import is_relevant


def cleanup_category(category_slug: str) -> dict:
    """
    Remove existing news articles that are no longer
    relevant to their category.

    This is intended for development/data cleanup.
    """

    # -----------------------------------------
    # 1. Get category
    # -----------------------------------------

    category_response = (
        admin_supabase
        .table("categories")
        .select("id, slug")
        .eq("slug", category_slug)
        .limit(1)
        .execute()
    )

    if not category_response.data:
        raise ValueError(
            f"Category not found: {category_slug}"
        )

    category_id = category_response.data[0]["id"]

    # -----------------------------------------
    # 2. Get existing stories
    # -----------------------------------------

    response = (
        admin_supabase
        .table("news_items")
        .select(
            "id, title, description"
        )
        .eq(
            "category_id",
            category_id,
        )
        .execute()
    )

    stories = response.data

    deleted = 0
    kept = 0

    # -----------------------------------------
    # 3. Check relevance
    # -----------------------------------------

    for story in stories:

        relevant = is_relevant(
            category_slug,
            story.get("title", ""),
            story.get("description"),
        )

        if relevant:
            kept += 1
            continue

        # -------------------------------------
        # Delete irrelevant story
        # -------------------------------------

        (
            admin_supabase
            .table("news_items")
            .delete()
            .eq("id", story["id"])
            .execute()
        )

        deleted += 1

    return {
        "category": category_slug,
        "total_checked": len(stories),
        "kept": kept,
        "deleted": deleted,
    }