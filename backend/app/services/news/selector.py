from datetime import datetime, timedelta, timezone

from app.lib.supabase import create_supabase_client

from .clustering import cluster_stories
from .ranker import rank_candidates
from .relevance import calculate_relevance_score, is_relevant


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_STORIES_PER_CATEGORY = 5

DEFAULT_HOURS = 24

MAX_DATABASE_ROWS = 50

MAX_RANKING_CANDIDATES = 20

CLUSTER_SIMILARITY_THRESHOLD = 0.45


# ============================================================
# SELECT RECENT STORIES
# ============================================================

async def select_recent_stories(
    user_id: str,
    access_token: str,
    stories_per_category: int = DEFAULT_STORIES_PER_CATEGORY,
    hours: int = DEFAULT_HOURS,
):

    print()
    print("========================================")
    print("SELECTING RECENT STORIES")
    print("USER ID:", user_id)
    print("REQUESTED WINDOW:", hours, "hours")
    print("========================================")

    # ========================================================
    # 1. SUPABASE CLIENT
    # ========================================================

    supabase = create_supabase_client(
        access_token
    )

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
        print(str(error))

        return []

    selected_categories = (
        category_response.data
        or []
    )

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

    now = datetime.now(
        timezone.utc
    )

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
            print(
                str(error)
            )

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

        selected_stories = []

        for cluster_index, cluster in enumerate(
            clusters,
            start=1,
        ):

            if not cluster:
                continue

            # Because candidates are already ranked,
            # first story is the strongest story.
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

            selected_stories.append(
                best_story
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

            if (
                len(selected_stories)
                >= stories_per_category
            ):
                break

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