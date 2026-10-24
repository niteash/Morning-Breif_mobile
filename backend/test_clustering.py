from app.services.news.ranker import (
    calculate_similarity,
    title_similarity,
)
from app.services.news.clustering import cluster_stories


def main():
    # 1. Identical headlines should have maximum similarity.
    identical = title_similarity(
        "OpenAI launches a new AI model",
        "OpenAI launches a new AI model",
    )
    assert identical == 1.0
    print("PASS: Identical titles have similarity 1.0")

    # 2. The legacy function must remain available.
    legacy_similarity = calculate_similarity(
        "OpenAI launches a new AI model",
        "OpenAI launches a new AI model",
    )
    assert legacy_similarity == 1.0
    print("PASS: calculate_similarity remains compatible")

    # 3. Similar headlines about the same event should cluster.
    similar_stories = [
        {
            "id": "1",
            "title": "OpenAI launches a new AI model",
        },
        {
            "id": "2",
            "title": "OpenAI launches new AI model",
        },
    ]

    clusters = cluster_stories(
        similar_stories,
        similarity_threshold=0.45,
    )

    assert len(clusters) == 1, clusters
    assert len(clusters[0]) == 2, clusters
    print("PASS: Similar headlines form one cluster")

    # 4. Clearly different topics should remain separate.
    different_stories = [
        {
            "id": "1",
            "title": "OpenAI launches a new AI model",
        },
        {
            "id": "2",
            "title": "Real Madrid wins the Champions League final",
        },
        {
            "id": "3",
            "title": "Central bank cuts interest rates",
        },
    ]

    clusters = cluster_stories(
        different_stories,
        similarity_threshold=0.45,
    )

    assert len(clusters) == 3, clusters
    print("PASS: Unrelated headlines remain separate")

    print("\nAll clustering tests passed.")


if __name__ == "__main__":
    main()
