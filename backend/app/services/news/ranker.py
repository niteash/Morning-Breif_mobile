from datetime import datetime, timezone
import re
from typing import Any

from .relevance import calculate_relevance_score, normalize_text


# Trusted publishers receive a modest ranking bonus.
# This is a ranking heuristic, not a guarantee of accuracy.
TRUSTED_SOURCES = {
    "reuters",
    "associated press",
    "ap news",
    "bbc",
    "financial times",
    "bloomberg",
    "the guardian",
    "france 24",
    "al jazeera",
    "cnn",
    "the new york times",
    "washington post",
    "the wall street journal",
    "cnbc",
    "techcrunch",
    "the verge",
    "ars technica",
    "espn",
    "sky sports",
}


# Google News RSS frequently stores the aggregator as the source while
# placing the original publisher at the end of the headline.
PUBLISHER_ALIASES = {
    "reuters": ("reuters",),
    "associated press": ("associated press", "ap news"),
    "bbc": ("bbc", "bbc news", "bbc sport"),
    "financial times": ("financial times",),
    "bloomberg": ("bloomberg",),
    "the guardian": ("the guardian", "guardian"),
    "france 24": ("france 24",),
    "al jazeera": ("al jazeera",),
    "cnn": ("cnn",),
    "the new york times": ("the new york times", "nytimes"),
    "washington post": ("the washington post", "washington post"),
    "the wall street journal": ("the wall street journal", "wsj"),
    "cnbc": ("cnbc",),
    "techcrunch": ("techcrunch",),
    "the verge": ("the verge",),
    "ars technica": ("ars technica",),
    "espn": ("espn",),
    "sky sports": ("sky sports",),
    "nikkei asia": ("nikkei asia",),
    "the irrawaddy": ("the irrawaddy", "irrawaddy"),
    "the diplomat": ("the diplomat",),
}


def extract_publisher(story: dict[str, Any]) -> str:
    """Extract the original publisher when Google News is the feed source."""
    raw_source = str(story.get("source") or "").strip()
    raw_title = str(story.get("title") or "").strip()
    normalized_source = normalize_text(raw_source)

    aggregator_sources = {
        "google news world",
        "google news business",
        "google news technology",
        "google news football",
        "google news myanmar",
    }

    if normalized_source not in aggregator_sources:
        return normalized_source

    # Google News titles often end with " - Publisher".
    for publisher, aliases in PUBLISHER_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            pattern = (
                r"\s[-–—|:]\s*"
                + re.escape(alias)
                + r"\s*$"
            )
            if re.search(pattern, raw_title, flags=re.IGNORECASE):
                return publisher

    # Some feeds use an unseparated publisher suffix.
    for publisher, aliases in PUBLISHER_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            pattern = r"\s+" + re.escape(alias) + r"\s*$"
            if re.search(pattern, raw_title, flags=re.IGNORECASE):
                return publisher

    return normalized_source

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by",
    "for", "from", "has", "have", "in", "into", "is", "it",
    "its", "of", "on", "or", "that", "the", "their", "this",
    "to", "was", "were", "will", "with", "after", "amid",
    "over", "under", "new", "says", "say", "how", "why",
    "what", "when", "who",
}


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp into an aware UTC datetime."""
    if not value:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _title_tokens(title: str) -> set[str]:
    """Return normalized, meaningful title words."""
    text = normalize_text(title)
    tokens = re.findall(r"[a-z0-9]+", text)

    return {
        token
        for token in tokens
        if token not in STOP_WORDS and len(token) > 1
    }


def title_similarity(title_a: str, title_b: str) -> float:
    """Compute Jaccard similarity between two normalized titles."""
    words_a = _title_tokens(title_a)
    words_b = _title_tokens(title_b)

    if not words_a or not words_b:
        return 0.0

    union = words_a | words_b

    return len(words_a & words_b) / len(union)


def calculate_similarity(title_a: str, title_b: str) -> float:
    """Backward-compatible alias used by clustering.py."""
    return title_similarity(title_a, title_b)

def calculate_source_score(source: str | None) -> int:
    """Give recognized publishers a modest ranking bonus."""
    normalized_source = normalize_text(source)

    if not normalized_source:
        return 0

    if normalized_source in {
        "google news world",
        "google news business",
        "google news technology",
        "google news football",
        "google news myanmar",
    }:
        return 2

    if any(
        trusted_source in normalized_source
        for trusted_source in TRUSTED_SOURCES
    ):
        return 12

    return 2


def calculate_freshness_score(
    published_at: Any,
    now: datetime | None = None,
) -> int:
    """
    Score recency. Stories older than 24 hours receive no bonus.

    The selector should still enforce the requested time window.
    """
    published = _parse_timestamp(published_at)

    if published is None:
        return 0

    current_time = now or datetime.now(timezone.utc)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    current_time = current_time.astimezone(timezone.utc)

    age_hours = (
        current_time - published
    ).total_seconds() / 3600

    # Future timestamps should not receive an inflated freshness score.
    if age_hours < -1:
        return 0

    age_hours = max(0, age_hours)

    if age_hours < 1:
        return 30
    if age_hours < 3:
        return 27
    if age_hours < 6:
        return 24
    if age_hours < 12:
        return 20
    if age_hours < 18:
        return 16
    if age_hours <= 24:
        return 12

    return 0


def calculate_story_score(
    story: dict[str, Any],
    category_slug: str | None = None,
    now: datetime | None = None,
) -> float:
    """Calculate a ranking score for an individual news story."""
    title = story.get("title") or ""
    description = story.get("description") or ""
    source = extract_publisher(story)

    score = calculate_freshness_score(
        story.get("published_at"),
        now=now,
    )

    score += calculate_source_score(source)

    if description.strip():
        score += 3

    if (story.get("author") or "").strip():
        score += 1

    # Relevance is calculated against the story's actual category.
    category = category_slug

    if category is None:
        category = story.get("category_slug") or story.get("category")

    if isinstance(category, dict):
        category = category.get("slug")

    if category:
        relevance_score = calculate_relevance_score(
            category_slug=str(category),
            title=title,
            description=description,
        )
        score += relevance_score * 2

    return score


def _deduplicate_exact_titles(
    stories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove exact normalized title duplicates, keeping the best-ranked."""
    result = []
    seen_titles = set()

    for story in stories:
        normalized_title = normalize_text(story.get("title") or "")

        if not normalized_title:
            continue

        if normalized_title in seen_titles:
            continue

        seen_titles.add(normalized_title)
        result.append(story)

    return result


def _deduplicate_similar_titles(
    stories: list[dict[str, Any]],
    similarity_threshold: float = 0.78,
) -> list[dict[str, Any]]:
    """
    Remove highly similar headlines.

    A higher threshold is deliberately used to reduce accidental removal
    of different stories that happen to share a few keywords.
    """
    result = []

    for story in stories:
        title = story.get("title") or ""

        if not title.strip():
            continue

        duplicate_found = False

        for selected_story in result:
            similarity = title_similarity(
                title,
                selected_story.get("title") or "",
            )

            if similarity >= similarity_threshold:
                duplicate_found = True
                break

        if not duplicate_found:
            result.append(story)

    return result


def rank_stories(
    stories: list[dict[str, Any]],
    category_slug: str | None = None,
    limit: int = 10,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Rank stories, remove duplicates, and return the top results.

    Input dictionaries are copied so this function does not mutate the
    caller's original story records.
    """
    if limit <= 0:
        return []

    ranked_stories = []

    for original_story in stories:
        story = dict(original_story)

        story["_score"] = calculate_story_score(
            story,
            category_slug=category_slug,
            now=now,
        )

        ranked_stories.append(story)

    ranked_stories.sort(
        key=lambda item: item["_score"],
        reverse=True,
    )

    ranked_stories = _deduplicate_exact_titles(ranked_stories)

    ranked_stories = _deduplicate_similar_titles(
        ranked_stories,
        similarity_threshold=0.78,
    )

    return [
        {
            key: value
            for key, value in story.items()
            if key != "_score"
        }
        for story in ranked_stories[:limit]
    ]


def rank_candidates(
    stories: list[dict[str, Any]],
    category_slug: str | None = None,
    limit: int = 20,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Rank candidate stories without removing similar headlines.

    This function is intended for the selector, which applies its own
    story clustering afterward.
    """
    if limit <= 0:
        return []

    ranked_stories = []

    for original_story in stories:
        story = dict(original_story)

        story["_score"] = calculate_story_score(
            story,
            category_slug=category_slug,
            now=now,
        )

        ranked_stories.append(story)

    ranked_stories.sort(
        key=lambda item: item["_score"],
        reverse=True,
    )

    ranked_stories = _deduplicate_exact_titles(ranked_stories)

    return [
        {
            key: value
            for key, value in story.items()
            if key != "_score"
        }
        for story in ranked_stories[:limit]
    ]