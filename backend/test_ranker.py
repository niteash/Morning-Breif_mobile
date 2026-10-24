from datetime import datetime, timedelta, timezone

from app.services.news.ranker import (
    calculate_freshness_score,
    rank_candidates,
    rank_stories,
    title_similarity,
)


NOW = datetime.now(timezone.utc)

STORIES = [
    {
        "id": "1",
        "title": "OpenAI announces a new artificial intelligence model",
        "description": "The company announced a new AI model.",
        "source": "Reuters",
        "author": "News Desk",
        "published_at": (NOW - timedelta(minutes=30)).isoformat(),
        "category_slug": "tech",
    },
    {
        "id": "2",
        "title": "OpenAI announces a new artificial intelligence model",
        "description": "A duplicate of the first article.",
        "source": "Unknown Source",
        "published_at": (NOW - timedelta(hours=2)).isoformat(),
        "category_slug": "tech",
    },
    {
        "id": "3",
        "title": "OpenAI reveals its latest AI model",
        "description": "The technology company revealed new capabilities.",
        "source": "BBC",
        "published_at": (NOW - timedelta(hours=1)).isoformat(),
        "category_slug": "tech",
    },
    {
        "id": "4",
        "title": "Local football club announces a new stadium",
        "description": "The club shared plans for its stadium.",
        "source": "Local News",
        "published_at": (NOW - timedelta(hours=5)).isoformat(),
        "category_slug": "tech",
    },
]


def main():
    # Recent stories should receive a higher freshness score.
    recent_score = calculate_freshness_score(
        NOW - timedelta(minutes=30), now=NOW
    )
    older_score = calculate_freshness_score(
        NOW - timedelta(hours=10), now=NOW
    )

    assert recent_score > older_score
    print("PASS: Recent stories receive higher freshness scores")

    # Similarity should recognize identical normalized headlines.
    similarity = title_similarity(
        "OpenAI announces a new AI model",
        "OpenAI announces a new AI model",
    )
    assert similarity == 1.0
    print("PASS: Identical headlines have similarity 1.0")

    # Exact duplicate headlines should be removed.
    ranked = rank_stories(
        STORIES,
        category_slug="tech",
        limit=10,
        now=NOW,
    )

    titles = [story["title"] for story in ranked]
    assert len(titles) == len(set(titles))
    print("PASS: Exact duplicate headlines are removed")

    # Candidate ranking retains similar but non-identical headlines
    # so the selector can cluster them later.
    candidates = rank_candidates(
        STORIES,
        category_slug="tech",
        limit=20,
        now=NOW,
    )

    assert any(
        story["id"] == "3"
        for story in candidates
    )
    print("PASS: Candidate ranking retains non-identical headlines")

    # Ranking should not mutate the input records.
    assert all("_score" not in story for story in STORIES)
    print("PASS: Original input stories remain unchanged")

    print("\nAll ranking tests passed.")


if __name__ == "__main__":
    main()
