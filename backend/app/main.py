from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.health import router as health_router
from app.routes.categories import router as categories_router
from app.routes.users import router as users_router
from app.routes.news import router as news_router
from app.routes.news_ingestion import router as news_ingestion_router
from app.routes import briefings
from app.routes import push_notifications
from app.services.scheduler import start_scheduler, stop_scheduler


# =========================================
# LOGGING
# =========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================
# APPLICATION LIFESPAN
# =========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background services when the API starts."""

    logger.info("Starting Morning Brief API...")

    try:
        start_scheduler()
        logger.info("Daily briefing scheduler started.")
    except Exception:
        logger.exception("Failed to start the daily briefing scheduler.")
        raise

    yield

    logger.info("Shutting down Morning Brief API...")

    try:
        stop_scheduler()
        logger.info("Daily briefing scheduler stopped.")
    except Exception:
        logger.exception("Error while stopping the daily briefing scheduler.")


# =========================================
# FASTAPI APPLICATION
# =========================================

app = FastAPI(
    title="Morning Brief API",
    description="Backend API for the Morning Brief application",
    version="1.0.0",
    lifespan=lifespan,
)


# =========================================
# CORS
# =========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================
# API ROUTES
# =========================================

app.include_router(health_router)
app.include_router(categories_router)
app.include_router(users_router)
app.include_router(news_router)
app.include_router(news_ingestion_router)
app.include_router(briefings.router)
app.include_router(push_notifications.router)

# =========================================
# ROOT
# =========================================

@app.get("/")
async def root():
    return {
        "message": "Morning Brief API is running",
        "status": "healthy",
        "scheduler": "enabled",
    }