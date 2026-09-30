from datetime import datetime, timezone
import re


STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "from",
    "by",
    "as",
    "at",
    "is",
    "are",
    "was",
    "were",
    "that",
    "this",
    "after",
    "before",
    "amid",
    "says",
    "said",
}


def normalize_title(title: str) -> str:
    """
    Normalize a title so that small formatting differences
    don't make duplicate stories look different.
    """

    title = title.lower().strip()

    title = re.sub(
        r"[^a-z0-9\s]",
        " ",
        title,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


def get_title_words(title: str) -> set[str]:
    """
    Convert title into meaningful words.
    """

    normalized = normalize_title(title)

    words = normalized.split()

    return {
        word
        for word in words
        if word not in STOP_WORDS
        and len(word) > 2
    }


def calculate_similarity(
    title_a: str,
    title_b: str,
) -> float:
    """
    Calculate Jaccard similarity between two titles.

    Example:

    A = {myanmar, airstrike, market, rakhine}
    B = {myanmar, airstrike, market, rakhine, kills}

    similarity = intersection / union
    """

    words_a = get_title_words(title_a)
    words_b = get_title_words(title_b)

    if not words_a or not words_b:
        return 0.0

    intersection = words_a.intersection(words_b)
    union = words_a.union(words_b)

    return len(intersection) / len(union)


def get_story_timestamp(story: dict) -> datetime:
    """
    Safely convert published_at into a datetime.
    """

    value = story.get("published_at")

    if not value:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )

    try:
        timestamp = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        return timestamp

    except Exception:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )


def calculate_story_score(story: dict) -> float:
    """
    Score a story primarily based on freshness.
    """

    score = 0

    published_at = get_story_timestamp(story)

    minimum_datetime = datetime.min.replace(
        tzinfo=timezone.utc
    )

    if published_at != minimum_datetime:

        age_hours = (
            datetime.now(timezone.utc)
            - published_at
        ).total_seconds() / 3600

        if age_hours <= 3:
            score += 100

        elif age_hours <= 6:
            score += 80

        elif age_hours <= 12:
            score += 60

        elif age_hours <= 24:
            score += 40

        elif age_hours <= 48:
            score += 20

    if story.get("description"):
        score += 5

    if story.get("author"):
        score += 2

    return score


def remove_exact_duplicates(
    stories: list[dict],
) -> list[dict]:

    seen_titles = set()

    unique_stories = []

    for story in stories:

        title = normalize_title(
            story.get("title", "")
        )

        if not title:
            continue

        if title in seen_titles:
            continue

        seen_titles.add(title)

        unique_stories.append(story)

    return unique_stories


def remove_similar_stories(
    stories: list[dict],
    similarity_threshold: float = 0.55,
) -> list[dict]:
    """
    Remove stories that appear to describe the
    same event.

    We keep the higher-ranked story and remove
    later stories that are highly similar.
    """

    selected = []

    for story in stories:

        title = story.get("title", "")

        if not title:
            continue

        is_duplicate = False

        for existing in selected:

            existing_title = existing.get(
                "title",
                "",
            )

            similarity = calculate_similarity(
                title,
                existing_title,
            )

            if similarity >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            selected.append(story)

    return selected


def rank_stories(
    stories: list[dict],
    limit: int = 5,
) -> list[dict]:

    # Step 1:
    # Remove exact duplicate titles.
    unique_stories = remove_exact_duplicates(
        stories
    )

    # Step 2:
    # Calculate score.
    for story in unique_stories:
        story["_score"] = calculate_story_score(
            story
        )

    # Step 3:
    # Newest / highest-quality stories first.
    ranked = sorted(
        unique_stories,
        key=lambda story: (
            story["_score"],
            get_story_timestamp(story),
        ),
        reverse=True,
    )

    # Step 4:
    # Remove stories describing almost
    # the same event.
    diverse_stories = remove_similar_stories(
        ranked,
        similarity_threshold=0.55,
    )

    # Step 5:
    # Keep requested number.
    selected = diverse_stories[:limit]

    # Step 6:
    # Never expose internal scoring.
    for story in selected:
        story.pop("_score", None)

    return selected

def rank_candidates(
    stories: list[dict],
    limit: int = 15,
) -> list[dict]:
    """
    Rank candidate stories without removing
    semantically similar stories.

    This is used before event clustering.
    """

    unique_stories = remove_exact_duplicates(
        stories
    )

    for story in unique_stories:
        story["_score"] = calculate_story_score(
            story
        )

    ranked = sorted(
        unique_stories,
        key=lambda story: (
            story["_score"],
            get_story_timestamp(story),
        ),
        reverse=True,
    )

    selected = ranked[:limit]

    for story in selected:
        story.pop("_score", None)

    return selected