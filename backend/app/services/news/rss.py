import ssl
import urllib.request
from email.utils import parsedate_to_datetime

import certifi
import feedparser


def parse_published_date(entry) -> str | None:
    """
    Extract the publication date from an RSS entry
    and convert it to ISO 8601 format.
    """

    # feedparser usually provides a parsed date here
    if getattr(entry, "published_parsed", None):
        try:
            from datetime import datetime, timezone

            dt = datetime(
                *entry.published_parsed[:6],
                tzinfo=timezone.utc,
            )

            return dt.isoformat()
        except Exception:
            pass

    # Some feeds use updated_parsed instead
    if getattr(entry, "updated_parsed", None):
        try:
            from datetime import datetime, timezone

            dt = datetime(
                *entry.updated_parsed[:6],
                tzinfo=timezone.utc,
            )

            return dt.isoformat()
        except Exception:
            pass

    # Fallback: try the raw published string
    published = entry.get("published")

    if published:
        try:
            return parsedate_to_datetime(
                published
            ).isoformat()
        except Exception:
            pass

    # Final fallback: updated
    updated = entry.get("updated")

    if updated:
        try:
            return parsedate_to_datetime(
                updated
            ).isoformat()
        except Exception:
            pass

    return None


def fetch_rss_feed(feed_url: str) -> list[dict]:
    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )

    request = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140 Safari/537.36"
            )
        },
    )

    with urllib.request.urlopen(
        request,
        context=ssl_context,
        timeout=20,
    ) as response:
        feed_data = response.read()

    feed = feedparser.parse(feed_data)

    articles = []

    for entry in feed.entries:
        articles.append(
            {
                "title": entry.get("title", "").strip(),
                "description": entry.get("summary", "").strip(),
                "url": entry.get("link", "").strip(),
                "published_at": parse_published_date(entry),
                "author": entry.get("author"),
            }
        )

    return articles