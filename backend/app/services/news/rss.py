import logging
import ssl
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
import feedparser

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3

USER_AGENT = (
    "MorningBrief/1.0 "
    "(RSS news aggregation; contact: support@morningbrief.app)"
)


def _normalize_datetime(value) -> str | None:
    """Convert supported date representations to timezone-aware UTC ISO-8601."""

    if not value:
        return None

    try:
        if isinstance(value, datetime):
            dt = value

        elif isinstance(value, (tuple, list)):
            # feedparser's parsed date is a time.struct_time-like sequence.
            dt = datetime(
                *value[:6],
                tzinfo=timezone.utc,
            )

        else:
            raw = str(value).strip()

            # First, try ISO-8601.
            try:
                dt = datetime.fromisoformat(
                    raw.replace("Z", "+00:00")
                )
            except ValueError:
                # Then try RFC 822 / RFC 2822.
                dt = parsedate_to_datetime(raw)

        if dt is None:
            return None

        # Naive timestamps are ambiguous. Do not silently assume UTC.
        if dt.tzinfo is None:
            return None

        return dt.astimezone(timezone.utc).isoformat()

    except (ValueError, TypeError, OverflowError, IndexError):
        return None


def parse_published_date(entry) -> str | None:
    """
    Extract a publication date from RSS or Atom.

    Preference:
    1. published
    2. updated
    3. published_parsed
    4. updated_parsed

    Only timezone-aware timestamps are accepted.
    """

    for field in ("published", "updated"):
        value = entry.get(field)

        if value:
            normalized = _normalize_datetime(value)

            if normalized:
                return normalized

    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)

        if value:
            normalized = _normalize_datetime(value)

            if normalized:
                return normalized

    return None


def _fetch_feed_bytes(feed_url: str) -> bytes:
    """Fetch one RSS feed with bounded retries and explicit timeouts."""

    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )

    last_error = None

    for attempt in range(MAX_RETRIES):
        request = Request(
            feed_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "application/rss+xml, "
                    "application/atom+xml, "
                    "application/xml, "
                    "text/xml, */*"
                ),
            },
        )

        try:
            with urlopen(
                request,
                context=ssl_context,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                return response.read()

        except HTTPError as error:
            last_error = error

            # Do not retry permanent client errors or repeatedly
            # request a feed that is explicitly rate-limiting us.
            if error.code in (403, 404, 410, 419, 429):
                raise

            retryable = error.code >= 500

            if not retryable or attempt == MAX_RETRIES - 1:
                raise

        except (URLError, TimeoutError, OSError) as error:
            last_error = error

            if attempt == MAX_RETRIES - 1:
                raise

        delay = 2 ** attempt

        logger.warning(
            "RSS request failed; retrying in %s seconds: "
            "url=%s attempt=%s/%s error=%s",
            delay,
            feed_url,
            attempt + 1,
            MAX_RETRIES,
            last_error,
        )

        time.sleep(delay)

    raise RuntimeError(
        f"Unable to fetch RSS feed: {feed_url}"
    ) from last_error


def fetch_rss_feed(feed_url: str) -> list[dict]:
    """Fetch and normalize RSS/Atom entries into article dictionaries."""

    logger.info("Fetching RSS feed: %s", feed_url)

    feed_data = _fetch_feed_bytes(feed_url)

    feed = feedparser.parse(feed_data)

    if getattr(feed, "bozo", False):
        logger.warning(
            "Feed parser reported malformed feed data: url=%s error=%s",
            feed_url,
            getattr(feed, "bozo_exception", None),
        )

    if not feed.entries:
        logger.warning(
            "RSS feed returned no entries: %s",
            feed_url,
        )
        return []

    articles = []

    for entry in feed.entries:
        title = str(entry.get("title") or "").strip()
        url = str(entry.get("link") or "").strip()
        description = (
            entry.get("summary")
            or entry.get("description")
            or ""
        )

        article = {
            "title": title,
            "description": str(description).strip(),
            "url": url,
            "published_at": parse_published_date(entry),
            "author": entry.get("author"),
        }

        articles.append(article)

    valid_dates = sum(
        article["published_at"] is not None
        for article in articles
    )

    logger.info(
        "RSS fetch complete: url=%s entries=%s valid_dates=%s",
        feed_url,
        len(articles),
        valid_dates,
    )

    return articles