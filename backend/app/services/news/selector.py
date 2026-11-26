from datetime import datetime, timedelta, timezone
import os

from app.lib.supabase import create_supabase_client

from .clustering import cluster_stories
from .ranker import rank_candidates
from .relevance import calculate_relevance_score, is_relevant
from .personalization import interest_bonus


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_STORIES_PER_CATEGORY = 5

DEFAULT_HOURS = 24

MAX_DATABASE_ROWS = 50

MAX_RANKING_CANDIDATES = 20

CLUSTER_SIMILARITY_THRESHOLD = 0.45
MAX_STORIES_PER_PUBLISHER = 2


def stable_category_rows(rows: list[dict]) -> list[dict]:
    """Canonicalize category order independently of PostgREST row order."""
    return sorted(
        rows,
        key=lambda selected: (
            str((selected.get("categories") or {}).get("slug") or ""),
            str(selected.get("category_id") or ""),
        ),
    )


def stable_categories(categories: list[dict]) -> list[dict]:
    """Canonicalize plain category records used by scheduled selection."""
    return sorted(
        categories,
        key=lambda category: (
            str(category.get("slug") or ""),
            str(category.get("id") or ""),
        ),
    )


def story_feedback_scores(rows: list[dict]) -> dict[str, int]:
    """Aggregate opposing feedback independently of database row order."""
    scores: dict[str, int] = {}
    for row in rows:
        story_id = str(row.get("story_id") or "")
        action = row.get("action")
        if not story_id or action not in {"more_like_this", "less_like_this"}:
            continue
        delta = 18 if action == "more_like_this" else -18
        scores[story_id] = scores.get(story_id, 0) + delta
    return scores


def configured_story_limit():
    """Bound server configuration; invalid configuration fails before provider work."""
    value = int(os.getenv('BRIEFING_STORIES_PER_CATEGORY', '5'))
    if not 1 <= value <= 10:
        raise ValueError('BRIEFING_STORIES_PER_CATEGORY must be between 1 and 10')
    return value


def select_publisher_balanced(clusters, limit, max_per_publisher=MAX_STORIES_PER_PUBLISHER):
    """Keep ranked cluster leaders while preferring more publisher variety."""
    leaders = [
        {**cluster[0], 'supporting_sources': [
            {key: story.get(key) for key in ('id', 'category_id', 'title', 'description', 'source', 'url', 'image_url', 'published_at')}
            for story in cluster[1:4]]}
        for cluster in clusters if cluster
    ]
    distinct_publishers = {(story.get("source") or "unknown").casefold().strip() for story in leaders}
    if len(distinct_publishers) <= 1:
        return leaders[:limit]
    selected, deferred, counts = [], [], {}
    for story in leaders:
        publisher = (story.get("source") or "unknown").casefold().strip()
        if counts.get(publisher, 0) < max_per_publisher:
            selected.append(story)
            counts[publisher] = counts.get(publisher, 0) + 1
        else:
            deferred.append(story)
        if len(selected) >= limit:
            return selected

    # Prefer publisher diversity, but use remaining eligible stories
    # when the preferred per-publisher cap leaves unused slots.
    remaining_slots = limit - len(selected)

    if remaining_slots > 0:
        selected.extend(deferred[:remaining_slots])

    return selected[:limit]



# ============================================================
# SELECT RECENT STORIES
# ============================================================

async def select_recent_stories(
    user_id: str,
    access_token: str,
    stories_per_category: int | None = None,
    hours: int = DEFAULT_HOURS,
    now: datetime | None = None,
):

    print()
    print("========================================")
    print("SELECTING RECENT STORIES")
    print("USER ID: [redacted]")
    print("REQUESTED WINDOW:", hours, "hours")
    print("========================================")

    stories_per_category = configured_story_limit() if stories_per_category is None else stories_per_category
    if not 1 <= stories_per_category <= 10:
        raise ValueError("Story limit must be between 1 and 10")

    # ========================================================
    # 1. SUPABASE CLIENT
    # ========================================================

    supabase = create_supabase_client(
        access_token
    )

    feedback_rows = []
    try:
        feedback_rows = (supabase.table('story_feedback')
                         .select('story_id,action,news_items(category_id,source)')
                         .eq('user_id', user_id).execute().data or [])
    except Exception:
        # Personalization is optional; a stale/missing preference must not make
        # the core news feed unavailable.
        feedback_rows = []
    hidden_categories = {
        str((row.get('news_items') or {}).get('category_id')) for row in feedback_rows
        if row.get('action') == 'hide_topic'
    }
    hidden_publishers = {
        str((row.get('news_items') or {}).get('source') or '').casefold().strip()
        for row in feedback_rows if row.get('action') == 'hide_publisher'
    }
    story_preferences = story_feedback_scores(feedback_rows)
    profile_preferences = {}
    try:
        rows = (supabase.table('profiles').select('horoscope_sign,crypto_watchlist')
                .eq('id', user_id).limit(1).execute().data or [])
        profile_preferences = rows[0] if rows else {}
    except Exception:
        profile_preferences = {}

    # ========================================================
    # 2. USER CATEGORIES
    # ========================================================

    print()
    print("========================================")
    print("FETCHING USER CATEGORIES")
    print("========================================")

    try:

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
            .eq(
                "user_id",
                user_id,
            )
            .execute()
        )

    except Exception as error:

        print()
        print("CATEGORY QUERY ERROR:")
        print(type(error).__name__)

        return []

    selected_categories = (
        category_response.data
        or []
    )
    selected_categories = stable_category_rows(selected_categories)

    print()

    print(
        "USER SELECTED CATEGORIES"
    )

    for selected in selected_categories:

        category = selected.get(
            "categories"
        )

        if not category:
            continue

        print(
            "CATEGORY ID:",
            selected.get(
                "category_id"
            ),
        )

        print(
            "SLUG:",
            category.get(
                "slug"
            ),
        )

        print(
            "NAME EN:",
            category.get(
                "name_en"
            ),
        )

        print(
            "NAME MY:",
            category.get(
                "name_my"
            ),
        )

        print("----------------------------------------")

    print(
        "TOTAL SELECTED CATEGORIES:",
        len(selected_categories),
    )

    print(
        "========================================"
    )

    if not selected_categories:

        print(
            "NO USER CATEGORIES FOUND"
        )

        return []

    # ========================================================
    # 3. TIME WINDOW
    # ========================================================

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Selection evaluation timestamp must include a timezone")
    now = now.astimezone(timezone.utc)

    since = (
        now
        - timedelta(
            hours=hours
        )
    )

    since_iso = since.isoformat()

    now_iso = now.isoformat()

    print()
    print("========================================")
    print("NEWS TIME WINDOW")
    print("========================================")
    print("NOW:", now_iso)
    print("SINCE:", since_iso)
    print("WINDOW:", hours, "hours")
    print("========================================")

    # ========================================================
    # FINAL RESULTS
    # ========================================================

    results = []

    # ========================================================
    # 4. PROCESS EACH CATEGORY
    # ========================================================

    for selected in selected_categories:

        category_id = selected.get(
            "category_id"
        )

        category = selected.get(
            "categories"
        )

        if not category:

            print()
            print(
                "CATEGORY RELATIONSHIP NOT FOUND:"
            )
            print(
                category_id
            )

            continue

        category_slug = category.get(
            "slug",
            ""
        )

        category_name = category.get(
            "name_en",
            "Unknown"
        )

        if str(category_id) in hidden_categories:
            continue

        print()
        print("========================================")
        print("PROCESSING CATEGORY")
        print("========================================")
        print(
            "CATEGORY ID:",
            category_id,
        )
        print(
            "CATEGORY:",
            category_name,
        )
        print(
            "SLUG:",
            category_slug,
        )
        print("========================================")

        # ====================================================
        # 5. FETCH NEWS
        # ====================================================

        print()
        print(
            "FETCHING RECENT NEWS FOR:",
            category_name,
        )

        print(
            "CATEGORY ID FILTER:",
            category_id,
        )

        try:

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
                .eq(
                    "category_id",
                    category_id,
                )
                .gte(
                    "published_at",
                    since_iso,
                )
                .lte(
                    "published_at",
                    now_iso,
                )
                .order(
                    "published_at",
                    desc=True,
                )
                .order(
                    "id",
                    desc=False,
                )
                .limit(
                    MAX_DATABASE_ROWS
                )
                .execute()
            )

            raw_stories = (
                response.data
                or []
            )

        except Exception as error:

            print()
            print(
                "NEWS QUERY ERROR:"
            )
            print(type(error).__name__)

            results.append(
                {
                    "category": category,
                    "stories": [],
                }
            )

            continue

        print()
        print(
            "RAW NEWS ROWS FOUND:",
            len(raw_stories),
        )

        # ====================================================
        # 6. VALIDATE NEWS
        # ====================================================

        validated_stories = []

        for story in raw_stories:

            if (story.get('source') or '').casefold().strip() in hidden_publishers:
                continue

            title = (
                story.get(
                    "title"
                )
                or ""
            ).strip()

            description = (
                story.get(
                    "description"
                )
                or ""
            ).strip()

            if not title:
                continue

            # ----------------------------------------------
            # Ensure category ID is correct
            # ----------------------------------------------

            if (
                story.get(
                    "category_id"
                )
                != category_id
            ):
                print(
                    "SKIPPING WRONG CATEGORY:",
                    title,
                )

                continue

            # ----------------------------------------------
            # Relevance validation
            # ----------------------------------------------

            relevant = is_relevant(
                category=category_slug,
                title=title,
                description=description,
            )

            if not relevant:

                print()
                print(
                    "FILTERED IRRELEVANT:"
                )

                print(
                    "CATEGORY:",
                    category_name,
                )

                print(
                    "TITLE:",
                    title,
                )

                continue

            # ----------------------------------------------
            # Relevance score
            # ----------------------------------------------

            relevance_score = (
                calculate_relevance_score(
                    category_slug=category_slug,
                    title=title,
                    description=description,
                )
            )

            story["_relevance_score"] = (
                relevance_score
            )
            story['_preference_score'] = (
                story_preferences.get(str(story.get('id')), 0)
                + interest_bonus(story, category_slug, profile_preferences)
            )

            validated_stories.append(
                story
            )

        print()
        print(
            "VALIDATED NEWS ROWS:",
            len(validated_stories),
        )

        # ====================================================
        # 7. SHOW VALIDATED STORIES
        # ====================================================

        if validated_stories:

            print()
            print(
                "VALIDATED STORIES:"
            )

            for index, story in enumerate(
                validated_stories,
                start=1,
            ):

                print(
                    f"{index}.",
                    story.get(
                        "title"
                    ),
                )

                print(
                    "   SOURCE:",
                    story.get(
                        "source"
                    ),
                )

                print(
                    "   PUBLISHED:",
                    story.get(
                        "published_at"
                    ),
                )

                print(
                    "   RELEVANCE:",
                    story.get(
                        "_relevance_score"
                    ),
                )

        else:

            print()
            print(
                "NO RELEVANT STORIES FOUND"
            )

            results.append(
                {
                    "category": category,
                    "stories": [],
                }
            )

            continue

        # ====================================================
        # 8. RANK
        # ====================================================

        print()
        print(
            "RANKING CANDIDATES..."
        )

        ranked_candidates = (
            rank_candidates(
                validated_stories,
                category_slug=category_slug,
                limit=MAX_RANKING_CANDIDATES,
                now=now,
            )
        )

        print(
            "RANKED CANDIDATES:",
            len(ranked_candidates),
        )

        # ====================================================
        # 9. CLUSTER
        # ====================================================

        print()
        print(
            "CLUSTERING STORIES..."
        )

        clusters = cluster_stories(
            ranked_candidates,
            similarity_threshold=(
                CLUSTER_SIMILARITY_THRESHOLD
            ),
        )

        print(
            "CLUSTERS CREATED:",
            len(clusters),
        )

        # ====================================================
        # 10. SELECT ONE STORY PER EVENT
        # ====================================================

        print()
        print(
            "SELECTING BEST STORY FROM EACH CLUSTER..."
        )

        selected_stories = select_publisher_balanced(clusters, stories_per_category)

        for cluster_index, cluster in enumerate(clusters, start=1):
            if not cluster:
                continue
            best_story = cluster[0]

            # Remove internal score fields before returning.
            best_story.pop(
                "_relevance_score",
                None,
            )

            best_story.pop(
                "_score",
                None,
            )

            print()
            print(
                f"CLUSTER {cluster_index}"
            )

            print(
                "CLUSTER SIZE:",
                len(cluster),
            )

            print(
                "SELECTED:",
                best_story.get(
                    "title"
                ),
            )

            print(
                "SOURCE:",
                best_story.get(
                    "source"
                ),
            )

            print(
                "PUBLISHED:",
                best_story.get(
                    "published_at"
                ),
            )


        # ====================================================
        # 11. FINAL CATEGORY RESULT
        # ====================================================

        print()
        print(
            "FINAL STORIES FOR CATEGORY:",
            category_name,
        )

        print(
            "COUNT:",
            len(selected_stories),
        )

        results.append(
            {
                "category": category,
                "stories": selected_stories,
            }
        )

    # ========================================================
    # 12. FINAL SUMMARY
    # ========================================================

    print()
    print("========================================")
    print("STORY SELECTION COMPLETE")
    print("========================================")

    print(
        "USER:",
        user_id,
    )

    print(
        "REQUESTED WINDOW:",
        hours,
        "hours",
    )

    print()

    for result in results:

        category = result.get(
            "category",
            {}
        )

        category_name = category.get(
            "name_en",
            "Unknown",
        )

        category_slug = category.get(
            "slug",
            "unknown",
        )

        stories = result.get(
            "stories",
            [],
        )

        print(
            f"{category_name} "
            f"({category_slug}): "
            f"{len(stories)} stories"
        )

    print()
    print("========================================")

    return results
