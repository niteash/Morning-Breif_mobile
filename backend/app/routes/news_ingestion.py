import asyncio
import logging
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.news.ingest import ingest_feed
from app.services.news.batch import IngestionBusy, run_ingestion_batch
from app.dependencies.operator import require_operator
from app.services.news.categories import resolve_category_ids
from app.services.news.sources import (
    NEWS_SOURCES,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/news",
    tags=["News Ingestion"],
    dependencies=[Depends(require_operator)],
)

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


@router.post("/ingest")
async def ingest_news(request: IngestRequest):
    """Ingest one RSS feed."""

    # Only server-reviewed feed/category/source combinations can reach the fetcher.
    # Authentication alone must not permit arbitrary network requests.
    configured = next((feed for feed in NEWS_SOURCES if
        feed["url"] == request.feed_url
        and feed["name"] == request.source
    ), None)
    if not configured:
        raise HTTPException(status_code=422, detail="Feed is not configured")

    try:
        category_ids = await asyncio.to_thread(resolve_category_ids)
    except Exception as error:
        raise HTTPException(status_code=503, detail="News categories are unavailable") from error
    if request.category_id != category_ids[configured['category']]:
        raise HTTPException(status_code=422, detail="Feed category does not match")

    try:
        result = await asyncio.to_thread(
            ingest_feed,
            feed_url=request.feed_url,
            category_id=request.category_id,
            source=request.source,
        )

        return {
            "success": result.get("skipped_insert_failure", 0) == 0,
            **result,
        }

    except Exception as error:
        logger.warning("RSS ingestion failed: error_type=%s", type(error).__name__)

        raise HTTPException(
            status_code=500,
            detail="RSS ingestion failed. Check the backend logs.",
        ) from error


@router.post("/ingest-all")
async def ingest_all_news():
    """Ingest all configured RSS feeds concurrently."""

    try:
        return await run_ingestion_batch()
    except IngestionBusy as error:
        raise HTTPException(status_code=409, detail="News ingestion is already running") from error
    except Exception as error:
        logger.warning("RSS batch unavailable: error_type=%s", type(error).__name__)
        raise HTTPException(status_code=503, detail="News categories or ingestion are unavailable") from error


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
            for category in sorted({feed['category'] for feed in NEWS_SOURCES})
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
