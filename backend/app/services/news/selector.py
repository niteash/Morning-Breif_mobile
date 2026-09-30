from datetime import datetime, timedelta, timezone

from app.lib.supabase import create_supabase_client

from .clustering import cluster_stories
from .ranker import rank_candidates


async def select_recent_stories(
    user_id: str,
    access_token: str,
    stories_per_category: int = 5,
    hours: int = 24,
):
    """
    Select recent stories for the user's categories.

    Pipeline:

        user categories
              ↓
        recent news
              ↓
        rank candidates
              ↓
        event clustering
              ↓
        select best story from each cluster
              ↓
        final stories
    """

    supabase = create_supabase_client(access_token)

    # --------------------------------------------------
    # 1. Get user's selected categories
    # --------------------------------------------------

    category_response = (
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

    selected_categories = category_response.data

    if not selected_categories:
        return []

    # --------------------------------------------------
    # 2. Calculate time window
    # --------------------------------------------------

    now = datetime.now(timezone.utc)

    since = now - timedelta(hours=hours)

    since_iso = since.isoformat()
    now_iso = now.isoformat()

    results = []

    # --------------------------------------------------
    # 3. Process each category
    # --------------------------------------------------

    for selected in selected_categories:

        category_id = selected["category_id"]

        category = selected.get("categories")

        if not category:
            continue

        # --------------------------------------------------
        # 4. Fetch recent stories
        # --------------------------------------------------

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
            .eq("category_id", category_id)
            .gte("published_at", since_iso)
            .lte("published_at", now_iso)
            .order("published_at", desc=True)
            .limit(30)
            .execute()
        )

        stories = response.data

        if not stories:

            results.append(
                {
                    "category": category,
                    "stories": [],
                }
            )

            continue

        # --------------------------------------------------
        # 5. Rank candidates
        # --------------------------------------------------

        ranked_candidates = rank_candidates(
            stories,
            limit=15,
        )

        # --------------------------------------------------
        # 6. Cluster similar stories
        # --------------------------------------------------

        clusters = cluster_stories(
            ranked_candidates,
            similarity_threshold=0.35,
        )

        # --------------------------------------------------
        # 7. Select best story from each cluster
        # --------------------------------------------------

        selected_stories = []

        for cluster in clusters:

            if not cluster:
                continue

            # First story is the highest-ranked
            # story in this cluster.
            best_story = cluster[0]

            selected_stories.append(best_story)

            if len(selected_stories) >= stories_per_category:
                break

        # --------------------------------------------------
        # 8. Add category result
        # --------------------------------------------------

        results.append(
            {
                "category": category,
                "stories": selected_stories,
            }
        )

    return results