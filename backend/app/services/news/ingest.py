from uuid import UUID

from app.lib.supabase import admin_supabase

from .normalize import normalize_article
from .relevance import is_relevant
from .rss import fetch_rss_feed


def ingest_feed(
    feed_url: str,
    category_id: UUID,
    source: str,
) -> dict:
    """
    Fetch RSS articles, filter irrelevant stories,
    remove duplicates, and insert valid articles
    into Supabase.
    """

    # -----------------------------------------
    # 1. Get category information
    # -----------------------------------------

    category_response = (
        admin_supabase
        .table("categories")
        .select("id, slug, name_en, name_my")
        .eq("id", str(category_id))
        .limit(1)
        .execute()
    )

    if not category_response.data:
        raise ValueError(
            f"Category not found: {category_id}"
        )

    category = category_response.data[0]

    category_slug = category["slug"]

    # -----------------------------------------
    # 2. Fetch RSS feed
    # -----------------------------------------

    articles = fetch_rss_feed(feed_url)

    inserted = 0
    skipped = 0

    # -----------------------------------------
    # 3. Process every article
    # -----------------------------------------

    for article in articles:

        # Normalize article
        normalized = normalize_article(article)

        # -------------------------------------
        # Skip missing title
        # -------------------------------------

        if not normalized["title"]:
            skipped += 1
            continue

        # -------------------------------------
        # Skip missing URL
        # -------------------------------------

        if not normalized["url"]:
            skipped += 1
            continue

        # -------------------------------------
        # Category relevance filtering
        # -------------------------------------

        if not is_relevant(
            category_slug,
            normalized["title"],
            normalized["description"],
        ):
            skipped += 1
            continue

        # -------------------------------------
        # Skip articles without publication date
        # -------------------------------------

        if not normalized["published_at"]:
            skipped += 1
            continue

        # -------------------------------------
        # Check duplicate
        # -------------------------------------

        existing = (
            admin_supabase
            .table("news_items")
            .select("id")
            .eq(
                "content_hash",
                normalized["content_hash"],
            )
            .limit(1)
            .execute()
        )

        if existing.data:
            skipped += 1
            continue

        # -------------------------------------
        # Create database row
        # -------------------------------------

        row = {
            "category_id": str(category_id),
            "source": source,
            "title": normalized["title"],
            "description": normalized["description"],
            "url": normalized["url"],
            "author": normalized["author"],
            "published_at": normalized["published_at"],
            "content_hash": normalized["content_hash"],
        }

        # -------------------------------------
        # Insert article
        # -------------------------------------

        response = (
            admin_supabase
            .table("news_items")
            .insert(row)
            .execute()
        )

        if response.data:
            inserted += 1
        else:
            skipped += 1

    # -----------------------------------------
    # 4. Return ingestion statistics
    # -----------------------------------------

    return {
        "source": source,
        "category": category_slug,
        "inserted": inserted,
        "skipped": skipped,
        "total": len(articles),
    }