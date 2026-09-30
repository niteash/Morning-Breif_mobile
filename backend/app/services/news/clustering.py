from .ranker import calculate_similarity


def cluster_stories(
    stories: list[dict],
    similarity_threshold: float = 0.35,
) -> list[list[dict]]:
    """
    Group similar stories into event clusters.

    Example:

    [
        [story1, story2, story3],
        [story4],
        [story5, story6],
    ]
    """

    clusters: list[list[dict]] = []

    for story in stories:

        title = story.get(
            "title",
            "",
        )

        if not title:
            continue

        placed = False

        for cluster in clusters:

            representative = cluster[0]

            similarity = calculate_similarity(
                title,
                representative.get(
                    "title",
                    "",
                ),
            )

            if similarity >= similarity_threshold:

                cluster.append(story)

                placed = True

                break

        if not placed:

            clusters.append(
                [story]
            )

    return clusters