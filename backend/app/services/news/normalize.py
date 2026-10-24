import hashlib
import re
from html import unescape
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "dclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
}


def clean_text(value: str | None) -> str | None:
    """Remove HTML markup and normalize whitespace."""
    if value is None:
        return None

    value = unescape(str(value))
    value = re.sub(r"<[^>]*>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value or None


def normalize_title(title: str) -> str:
    """Normalize title text for cross-publisher comparison."""
    title = unescape(title or "").lower()
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"[^\w\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def canonicalize_url(url: str) -> str:
    """Remove common tracking parameters from an article URL."""
    url = (url or "").strip()

    if not url:
        return ""

    try:
        parts = urlsplit(url)

        if parts.scheme.lower() not in {"http", "https"}:
            return url

        hostname = (parts.hostname or "").lower()

        if not hostname:
            return url

        port = parts.port
        netloc = hostname

        if port and not (
            (parts.scheme.lower() == "http" and port == 80)
            or (parts.scheme.lower() == "https" and port == 443)
        ):
            netloc = f"{hostname}:{port}"

        filtered_params = []

        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True,
        ):
            lowered = key.lower()

            if lowered.startswith("utm_"):
                continue

            if lowered in TRACKING_PARAMETERS:
                continue

            filtered_params.append((key, value))

        query = urlencode(filtered_params, doseq=True)

        path = parts.path.rstrip("/") or "/"

        return urlunsplit(
            (
                parts.scheme.lower(),
                netloc,
                path,
                query,
                "",
            )
        )

    except (ValueError, UnicodeError):
        return url


def create_content_hash(title: str, url: str) -> str:
    """
    Stable exact-article hash.

    This catches identical normalized titles and canonical URLs.
    Similar headlines from different publishers require a separate
    event-level deduplication step in the selector.
    """
    normalized_title = normalize_title(title)
    canonical_url = canonicalize_url(url).lower()

    raw = f"{normalized_title}::{canonical_url}"

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def create_title_hash(title: str) -> str:
    """Fingerprint a normalized title across different publishers."""
    normalized_title = normalize_title(title)

    return hashlib.sha256(
        normalized_title.encode("utf-8")
    ).hexdigest()


def normalize_article(article: dict) -> dict:
    """Normalize an RSS article before database insertion."""
    title = clean_text(article.get("title")) or ""
    description = clean_text(article.get("description"))
    url = canonicalize_url(
        str(article.get("url") or "")
    )
    author = clean_text(article.get("author"))

    return {
        "title": title,
        "description": description,
        "url": url,
        "published_at": article.get("published_at"),
        "author": author,
        "content_hash": (
            create_content_hash(title, url)
            if title and url
            else None
        ),
        "title_hash": (
            create_title_hash(title)
            if title
            else None
        ),
    }