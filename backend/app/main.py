from app.routes.bookmarks import router as bookmarks_router
from contextlib import asynccontextmanager
import logging
import os
import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.account_deletion import router as deletion_router
from app.routes.entitlements import router as entitlements_router
from app.routes.health import router as health_router
from app.routes.categories import router as categories_router
from app.routes.users import router as users_router
from app.routes.news import router as news_router
from app.routes.news_ingestion import router as news_ingestion_router
from app.routes.billing import router as billing_router
from app.routes.operations import router as operations_router
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

# SDK HTTP logs can contain signed URLs; keep routine requests out of logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
ACCOUNT_DELETION_WORKER_ENABLED = os.getenv("ACCOUNT_DELETION_WORKER_ENABLED", "false").lower() == "true"
PUSH_DELIVERY_ENABLED = os.getenv("PUSH_DELIVERY_ENABLED", "false").lower() == "true"
NEWS_INGESTION_ENABLED = os.getenv("NEWS_INGESTION_ENABLED", "false").lower() == "true"
GENERATION_WORKER_ENABLED = os.getenv("GENERATION_WORKER_ENABLED", "false").lower() == "true"
RETENTION_WORKER_ENABLED = os.getenv("RETENTION_WORKER_ENABLED", "false").lower() == "true"
AUTOMATIC_BRIEFING_PREFERENCES_ENABLED = os.getenv(
    "AUTOMATIC_BRIEFING_PREFERENCES_ENABLED", "false"
).lower() == "true"
DELIVERY_SCHEDULER_ENABLED = SCHEDULER_ENABLED and AUTOMATIC_BRIEFING_PREFERENCES_ENABLED
SAFE_PUSH_DELIVERY_ENABLED = PUSH_DELIVERY_ENABLED and AUTOMATIC_BRIEFING_PREFERENCES_ENABLED
APP_ENV = os.getenv("APP_ENV", "development").lower()
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]


# =========================================
# APPLICATION LIFESPAN
# =========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background services when the API starts."""

    logger.info("Starting Morning Brief API...")

    try:
        if DELIVERY_SCHEDULER_ENABLED or NEWS_INGESTION_ENABLED or SAFE_PUSH_DELIVERY_ENABLED or ACCOUNT_DELETION_WORKER_ENABLED or GENERATION_WORKER_ENABLED or RETENTION_WORKER_ENABLED:
            start_scheduler(
                deliveries_enabled=DELIVERY_SCHEDULER_ENABLED,
                push_enabled=SAFE_PUSH_DELIVERY_ENABLED,
                deletion_enabled=ACCOUNT_DELETION_WORKER_ENABLED,
                ingestion_enabled=NEWS_INGESTION_ENABLED,
                ingestion_interval_minutes=int(os.getenv("NEWS_INGESTION_INTERVAL_MINUTES", "30")) if NEWS_INGESTION_ENABLED else 30,
                generation_worker_enabled=GENERATION_WORKER_ENABLED,
                retention_enabled=RETENTION_WORKER_ENABLED,
            )
            logger.info("Configured background jobs started.")
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
    docs_url=None if APP_ENV == "production" else "/docs",
    redoc_url=None if APP_ENV == "production" else "/redoc",
    openapi_url=None if APP_ENV == "production" else "/openapi.json",
)


@app.middleware("http")
async def secure_response_headers(request, call_next):
    request_id = request.headers.get("x-request-id", "")
    if not request_id or len(request_id) > 128 or not request_id.isascii():
        request_id = secrets.token_hex(16)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


# =========================================
# CORS
# =========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


# =========================================
# API ROUTES
# =========================================

app.include_router(health_router)
app.include_router(categories_router)
app.include_router(users_router)
app.include_router(deletion_router)
app.include_router(entitlements_router)
app.include_router(bookmarks_router)
app.include_router(news_router)
app.include_router(news_ingestion_router)
app.include_router(billing_router)
app.include_router(operations_router)
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
        "scheduler": "enabled" if DELIVERY_SCHEDULER_ENABLED else "disabled",
        "account_deletion_worker": "enabled" if ACCOUNT_DELETION_WORKER_ENABLED else "disabled",
        "push_delivery": "enabled" if SAFE_PUSH_DELIVERY_ENABLED else "disabled",
        "news_ingestion": "enabled" if NEWS_INGESTION_ENABLED else "disabled",
        "generation_worker": "enabled" if GENERATION_WORKER_ENABLED else "disabled",
        "retention_worker": "enabled" if RETENTION_WORKER_ENABLED else "disabled",
    }
