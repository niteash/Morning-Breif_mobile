from app.services.news.feeds import (
    TECHNOLOGY_FEED,
    BUSINESS_FEED,
    FOOTBALL_FEED,
    WORLD_FEED,
    MYANMAR_FEED,
    CRYPTO_FEED,
    PSYCHOLOGY_FEED,
    HOROSCOPE_FEED,
)
from app.services.news.ingest import ingest_feed
from app.services.news.categories import resolve_category_ids


FEEDS = [
    {
        "feed_url": TECHNOLOGY_FEED,
        "category": "technology",
        "source": "Google News Technology",
    },
    {
        "feed_url": BUSINESS_FEED,
        "category": "business",
        "source": "Google News Business",
    },
    {
        "feed_url": FOOTBALL_FEED,
        "category": "football",
        "source": "Google News Football",
    },
    {
        "feed_url": WORLD_FEED,
        "category": "world",
        "source": "Google News World",
    },
    {
        "feed_url": MYANMAR_FEED,
        "category": "myanmar",
        "source": "Google News Myanmar",
    },
    {
        "feed_url": CRYPTO_FEED,
        "category": "crypto",
        "source": "Google News Crypto",
    },
    {
        "feed_url": PSYCHOLOGY_FEED,
        "category": "psychology",
        "source": "Google News Psychology",
    },
    {
        "feed_url": HOROSCOPE_FEED,
        "category": "horoscope",
        "source": "Google News Horoscope",
    },
]


def run_all_ingestion():
    results = []
    category_ids = resolve_category_ids()

    for feed in FEEDS:
        print(f"\nINGESTING: {feed['source']}")

        result = ingest_feed(
            feed_url=feed["feed_url"],
            category_id=category_ids[feed["category"]],
            source=feed["source"],
        )

        print(result)
        results.append(result)

    return results
