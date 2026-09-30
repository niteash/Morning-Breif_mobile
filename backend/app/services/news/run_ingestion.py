from app.services.news.feeds import (
    TECHNOLOGY_FEED,
    BUSINESS_FEED,
    FOOTBALL_FEED,
    WORLD_FEED,
    MYANMAR_FEED,
)
from app.services.news.ingest import ingest_feed


FEEDS = [
    {
        "feed_url": TECHNOLOGY_FEED,
        "category_id": "bd5d3262-e705-4595-859b-1b63e775e445",
        "source": "Google News Technology",
    },
    {
        "feed_url": BUSINESS_FEED,
        "category_id": "0be82b81-4a28-4456-9c2f-83b185777846",
        "source": "Google News Business",
    },
    {
        "feed_url": FOOTBALL_FEED,
        "category_id": "51d3202c-890e-4732-ab10-dbf7f3431d73",
        "source": "Google News Football",
    },
    {
        "feed_url": WORLD_FEED,
        "category_id": "b96b933b-7fa4-4bbd-ae82-2b653ffdc1bb",
        "source": "Google News World",
    },
    {
        "feed_url": MYANMAR_FEED,
        "category_id": "fc9d5cba-d415-4515-a2b5-b5d03d9d7666",
        "source": "Google News Myanmar",
    },
]


def run_all_ingestion():
    results = []

    for feed in FEEDS:
        print(f"\nINGESTING: {feed['source']}")

        result = ingest_feed(
            feed_url=feed["feed_url"],
            category_id=feed["category_id"],
            source=feed["source"],
        )

        print(result)
        results.append(result)

    return results