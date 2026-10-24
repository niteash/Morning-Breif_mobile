import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.lib.supabase import admin_supabase

from .normalize import (
    normalize_article,
    create_title_hash,
)
from .relevance import is_relevant
from .rss import fetch_rss_feed


logger = logging.getLogger(__name__)


# Articles older than this are excluded from ingestion.
MAX_ARTICLE_AGE_HOURS = 36

# Articles published within the last 24 hours are considered fresh.
FRESH_ARTICLE_AGE_HOURS = 24


def parse_published_at(value) -> datetime | None:
    """
    Convert a publication timestamp into a timezone-aware UTC datetime.

    Accepts datetime objects and ISO-8601 strings.
    Invalid, missing, or timezone-naive timestamps return None.
    """
    if not value:
        return None

    try:
        if isinstance(value, datetime):
            published_at = value
        else:
            published_at = datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )

        if published_at.tzinfo is None:
            return None

        return published_at.astimezone(timezone.utc)

    except (TypeError, ValueError, OverflowError):
        return None


def ingest_feed(
    feed_url: str,
    category_id: UUID,
    source: str,
) -> dict:
    """
    Fetch RSS articles and insert relevant, recent, unique stories.

    Rules:
    - Missing or invalid publication dates are rejected.
    - Future-dated articles are rejected.
    - Articles older than MAX_ARTICLE_AGE_HOURS are rejected.
    - Articles outside the category's relevance are rejected.
    - Existing content hashes are not inserted again.
    - Existing normalized title hashes are checked to reduce
      duplicate headlines across publishers.
    - Articles published within 24 hours are counted as fresh.

    Requires the news_items table to contain a nullable text column
    named title_hash.
    """

    now = datetime.now(timezone.utc)

    fresh_cutoff = now - timedelta(
        hours=FRESH_ARTICLE_AGE_HOURS
    )

    oldest_allowed = now - timedelta(
        hours=MAX_ARTICLE_AGE_HOURS
    )

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

    stats = {
        "source": source,
        "category": category_slug,
        "total": len(articles),
        "inserted": 0,
        "fresh_inserted": 0,
        "fallback_inserted": 0,
        "skipped_missing_title": 0,
        "skipped_missing_url": 0,
        "skipped_invalid_date": 0,
        "skipped_too_old": 0,
        "skipped_irrelevant": 0,
        "skipped_duplicate": 0,
        "skipped_insert_failure": 0,
    }

    # Cache hashes encountered during this feed run.
    # This avoids repeating database queries for the same
    # exact title or URL within one RSS response.
    seen_content_hashes: set[str] = set()
    seen_title_hashes: set[str] = set()

    # -----------------------------------------
    # 3. Process articles
    # -----------------------------------------

    for article in articles:
        normalized = normalize_article(article)

        title = normalized.get("title")
        url = normalized.get("url")
        description = normalized.get("description")
        content_hash = normalized.get("content_hash")

        if not title:
            stats["skipped_missing_title"] += 1
            continue

        if not url:
            stats["skipped_missing_url"] += 1
            continue

        # -------------------------------------
        # 3a. Validate publication date
        # -------------------------------------

        published_at = parse_published_at(
            normalized.get("published_at")
        )

        if published_at is None:
            stats["skipped_invalid_date"] += 1
            continue

        if published_at > now:
            stats["skipped_invalid_date"] += 1
            continue

        if published_at < oldest_allowed:
            stats["skipped_too_old"] += 1
            continue

        # -------------------------------------
        # 3b. Validate category relevance
        # -------------------------------------

        if not is_relevant(
            category=category_slug,
            title=title,
            description=description,
        ):
            stats["skipped_irrelevant"] += 1
            continue

        if not content_hash:
            stats["skipped_insert_failure"] += 1
            logger.warning(
                "Missing content hash for article: %s",
                title,
            )
            continue

        title_hash = create_title_hash(title)

        # -------------------------------------
        # 4. Check duplicates in this feed run
        # -------------------------------------

        if (
            content_hash in seen_content_hashes
            or title_hash in seen_title_hashes
        ):
            stats["skipped_duplicate"] += 1
            continue

        # Record the fingerprints for subsequent articles
        # in this same RSS response.
        seen_content_hashes.add(content_hash)
        seen_title_hashes.add(title_hash)

        # -------------------------------------
        # 5. Check existing exact-article duplicate
        # -------------------------------------

        try:
            existing_exact = (
                admin_supabase
                .table("news_items")
                .select("id")
                .eq("content_hash", content_hash)
                .limit(1)
                .execute()
            )

            if existing_exact.data:
                stats["skipped_duplicate"] += 1
                continue

            # ---------------------------------
            # 6. Check normalized-title duplicate
            # ---------------------------------

            existing_title = (
                admin_supabase
                .table("news_items")
                .select("id")
                .eq("title_hash", title_hash)
                .limit(1)
                .execute()
            )

            if existing_title.data:
                stats["skipped_duplicate"] += 1
                continue

        except Exception:
            logger.exception(
                "Failed duplicate checks for article: %s",
                title,
            )
            stats["skipped_insert_failure"] += 1
            continue

        # -------------------------------------
        # 7. Prepare database row
        # -------------------------------------

        row = {
            "category_id": str(category_id),
            "source": source,
            "title": title,
            "description": description,
            "url": url,
            "author": normalized.get("author"),
            "published_at": published_at.isoformat(),
            "content_hash": content_hash,
            "title_hash": title_hash,
        }

        # -------------------------------------
        # 8. Insert article
        # -------------------------------------

        try:
            response = (
                admin_supabase
                .table("news_items")
                .insert(row)
                .execute()
            )

            if response.data:
                stats["inserted"] += 1

                if published_at >= fresh_cutoff:
                    stats["fresh_inserted"] += 1
                else:
                    stats["fallback_inserted"] += 1

            else:
                stats["skipped_insert_failure"] += 1
                logger.warning(
                    "Article insertion returned no data: %s",
                    title,
                )

        except Exception:
            logger.exception(
                "Failed to insert article: %s",
                title,
            )
            stats["skipped_insert_failure"] += 1

    # -----------------------------------------
    # 9. Return ingestion statistics
    # -----------------------------------------

    stats["skipped"] = (
        stats["skipped_missing_title"]
        + stats["skipped_missing_url"]
        + stats["skipped_invalid_date"]
        + stats["skipped_too_old"]
        + stats["skipped_irrelevant"]
        + stats["skipped_duplicate"]
        + stats["skipped_insert_failure"]
    )

    logger.info(
        "News ingestion completed | source=%s | category=%s | "
        "total=%s | inserted=%s | duplicates=%s | irrelevant=%s",
        source,
        category_slug,
        stats["total"],
        stats["inserted"],
        stats["skipped_duplicate"],
        stats["skipped_irrelevant"],
    )

    return stats