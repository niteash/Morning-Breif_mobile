from app.lib.supabase import admin_supabase

from .normalize import normalize_article
from .rss import fetch_rss_feed


def backfill_feed(
    feed_url: str,
    category_id: str,
    source: str,
) -> dict:
    articles = fetch_rss_feed(feed_url)

    updated = 0
    skipped = 0

    for article in articles:
        normalized = normalize_article(article)

        if not normalized["title"]:
            skipped += 1
            continue

        if not normalized["url"]:
            skipped += 1
            continue

        if not normalized["published_at"]:
            skipped += 1
            continue

        content_hash = normalized["content_hash"]

        existing = (
            admin_supabase
            .table("news_items")
            .select("id, published_at")
            .eq("content_hash", content_hash)
            .limit(1)
            .execute()
        )

        if not existing.data:
            skipped += 1
            continue

        existing_row = existing.data[0]

        # Don't update if publication date already exists.
        if existing_row.get("published_at"):
            skipped += 1
            continue

        (
            admin_supabase
            .table("news_items")
            .update({
                "published_at": normalized["published_at"],
            })
            .eq("id", existing_row["id"])
            .execute()
        )

        updated += 1

    return {
        "source": source,
        "updated": updated,
        "skipped": skipped,
        "total": len(articles),
    }