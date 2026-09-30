import hashlib
import re


def clean_text(value: str | None) -> str | None:
    if not value:
        return None

    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def create_content_hash(title: str, url: str) -> str:
    raw = f"{title.strip().lower()}::{url.strip().lower()}"

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def normalize_article(article: dict) -> dict:
    title = clean_text(
        article.get("title")
    ) or ""

    description = clean_text(
        article.get("description")
    )

    url = (
        article.get("url") or ""
    ).strip()

    author = clean_text(
        article.get("author")
    )

    return {
        "title": title,
        "description": description,
        "url": url,
        "published_at": article.get("published_at"),
        "author": author,
        "content_hash": create_content_hash(
            title,
            url,
        ),
    }