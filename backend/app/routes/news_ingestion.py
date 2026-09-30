from uuid import UUID

from fastapi import APIRouter

from app.services.news.ingest import ingest_feed


router = APIRouter(
    prefix="/api/v1/news",
    tags=["News Ingestion"],
)


@router.post("/ingest")
async def ingest_news(
    feed_url: str,
    category_id: UUID,
    source: str,
):
    result = ingest_feed(
        feed_url=feed_url,
        category_id=category_id,
        source=source,
    )

    return result