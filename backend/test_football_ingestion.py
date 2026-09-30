from app.services.news.feeds import FOOTBALL_FEED
from app.services.news.ingest import ingest_feed


FOOTBALL_CATEGORY_ID = "51d3202c-890e-4732-ab10-dbf7f3431d73"


def main():
    print("\n==============================")
    print("FOOTBALL NEWS INGESTION")
    print("==============================\n")

    result = ingest_feed(
        feed_url=FOOTBALL_FEED,
        category_id=FOOTBALL_CATEGORY_ID,
        source="Google News Football",
    )

    print("\nRESULT:")
    print(result)


if __name__ == "__main__":
    main()