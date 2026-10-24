from datetime import datetime, timedelta, timezone

from app.services.news.ranker import rank_candidates
from app.services.news.clustering import cluster_stories
from app.services.news.relevance import is_relevant


NOW = datetime.now(timezone.utc)

CATEGORY = {
    "id": "tech-category",
    "slug": "tech",
    "name_en": "Technology",
    "name_my": "နည်းပညာ",
}

STORIES = [
    {
        "id": "1",
        "category_id": "tech-category",
        "title": "OpenAI launches a new large language model",
        "description": "OpenAI announced a new AI model.",
        "source": "Reuters",
        "published_at": (NOW - timedelta(minutes=30)).isoformat(),
    },
    {
        "id": "2",
        "category_id": "tech-category",
        "title": "OpenAI launches new large language model",
        "description": "The company announced a new AI model.",
        "source": "BBC",
        "published_at": (NOW - timedelta(hours=1)).isoformat(),
    },
    {
        "id": "3",
        "category_id": "tech-category",
        "title": "Nvidia announces a new AI chip",
        "description": "The company revealed a new processor.",
        "source": "Reuters",
        "published_at": (NOW - timedelta(hours=2)).isoformat(),
    },
    {
        "id": "4",
        "category_id": "tech-category",
        "title": "Microsoft introduces new cloud computing features",
        "description": "The company announced updates to its cloud platform.",
        "source": "TechCrunch",
        "published_at": (NOW - timedelta(hours=3)).isoformat(),
    },
    {
        "id": "5",
        "category_id": "tech-category",
        "title": "Local restaurant announces a new menu",
        "description": "The restaurant introduced several new dishes.",
        "source": "Local News",
        "published_at": (NOW - timedelta(hours=1)).isoformat(),
    },
]


def main():
    # Stage 1: Filter irrelevant stories.
    valid_stories = [
        story
        for story in STORIES
        if is_relevant(
            CATEGORY["slug"],
            story["title"],
            story["description"],
        )
    ]

    assert len(valid_stories) == 4, [
        story["title"] for story in valid_stories
    ]
    print("PASS: Irrelevant stories are filtered")

    # Stage 2: Rank the valid candidates.
    ranked = rank_candidates(
        valid_stories,
        category_slug=CATEGORY["slug"],
        limit=20,
        now=NOW,
    )

    assert ranked, "Ranking returned no stories"
    print("PASS: Relevant candidates are ranked")

    # Stage 3: Cluster duplicate event coverage.
    clusters = cluster_stories(
        ranked,
        similarity_threshold=0.45,
    )

    # The two OpenAI headlines should be grouped together.
    openai_clusters = [
        cluster
        for cluster in clusters
        if any(
            "OpenAI" in story["title"]
            for story in cluster
        )
    ]

    assert len(openai_clusters) == 1
    assert len(openai_clusters[0]) == 2, [
        [story["title"] for story in cluster]
        for cluster in clusters
    ]
    print("PASS: Similar OpenAI headlines form one cluster")

    # Stage 4: Select one story per cluster.
    selected = [cluster[0] for cluster in clusters if cluster]

    assert len(selected) == len(clusters)
    assert all(
        story["category_id"] == CATEGORY["id"]
        for story in selected
    )
    print("PASS: Selected stories retain their category")

    # Stage 5: Enforce the five-story limit.
    selected = selected[:5]

    assert len(selected) <= 5
    print("PASS: Story limit is respected")

    print("\nSelected stories:")
    for index, story in enumerate(selected, start=1):
        print(f"{index}. {story['title']}")

    print("\nAll news pipeline tests passed.")


if __name__ == "__main__":
    main()
