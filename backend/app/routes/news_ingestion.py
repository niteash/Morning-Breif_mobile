import asyncio
import logging
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.news.ingest import ingest_feed
from app.services.news.sources import (
    CATEGORY_IDS,
    MAX_HEADLINE_AGE_HOURS,
    NEWS_SOURCES,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/news",
    tags=["News Ingestion"],
)

# Maximum concurrent RSS fetch/ingestion operations.
MAX_CONCURRENT_FEEDS = 8


class IngestRequest(BaseModel):
    feed_url: str = Field(min_length=10, max_length=2048)
    category_id: UUID
    source: str = Field(min_length=1, max_length=100)

    @field_validator("feed_url")
    @classmethod
    def validate_feed_url(cls, value: str) -> str:
        parsed = urlparse(value)

        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("feed_url must be a valid HTTP or HTTPS URL")

        return value


async def _ingest_one(
    feed: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        try:
            result = await asyncio.to_thread(
                ingest_feed,
                feed_url=feed["url"],
                category_id=CATEGORY_IDS[feed["category"]],
                source=feed["name"],
            )

            logger.info(
                "RSS ingestion complete: source=%s category=%s inserted=%s",
                feed["name"],
                feed["category"],
                result.get("inserted", 0),
            )

            return {
                "source": feed["name"],
                "category": feed["category"],
                "feed_url": feed["url"],
                "success": True,
                "result": result,
            }

        except Exception as error:
            logger.exception(
                "RSS feed failed: source=%s",
                feed["name"],
            )

            return {
                "source": feed["name"],
                "category": feed["category"],
                "feed_url": feed["url"],
                "success": False,
                "error": str(error),
            }


@router.post("/ingest")
async def ingest_news(request: IngestRequest):
    """Ingest one RSS feed."""

    try:
        result = await asyncio.to_thread(
            ingest_feed,
            feed_url=request.feed_url,
            category_id=request.category_id,
            source=request.source,
        )

        return {
            "success": True,
            **result,
        }

    except Exception as error:
        logger.exception("RSS ingestion failed.")

        raise HTTPException(
            status_code=500,
            detail="RSS ingestion failed. Check the backend logs.",
        ) from error


@router.post("/ingest-all")
async def ingest_all_news():
    """Ingest all configured RSS feeds concurrently."""

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

    results = await asyncio.gather(
        *[
            _ingest_one(feed, semaphore)
            for feed in NEWS_SOURCES
        ]
    )

    successful = sum(
        1 for result in results if result["success"]
    )

    failed = len(results) - successful

    totals = {
        "articles_seen": 0,
        "inserted": 0,
        "fresh_inserted": 0,
        "fallback_inserted": 0,
        "skipped": 0,
    }

    for result in results:
        if not result["success"]:
            continue

        stats = result["result"]

        for key in totals:
            totals[key] += stats.get(key, 0)

    return {
        "message": "RSS ingestion run completed",
        "total_feeds": len(NEWS_SOURCES),
        "successful_feeds": successful,
        "failed_feeds": failed,
        "max_article_age_hours": MAX_HEADLINE_AGE_HOURS,
        "totals": totals,
        "results": results,
    }


@router.get("/feeds")
async def list_news_feeds():
    """List all configured publisher feeds."""

    return {
        "total_feeds": len(NEWS_SOURCES),
        "categories": {
            category: sum(
                1
                for feed in NEWS_SOURCES
                if feed["category"] == category
            )
            for category in CATEGORY_IDS
        },
        "feeds": [
            {
                "name": feed["name"],
                "category": feed["category"],
                "feed_url": feed["url"],
            }
            for feed in NEWS_SOURCES
        ],
    }