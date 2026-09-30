from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.categories import router as categories_router
from app.routes.users import router as users_router
from app.routes.news import router as news_router
from app.routes.news_ingestion import router as news_ingestion_router
from app.routes import briefings

app = FastAPI(
    title="Morning Brief API",
    description="Backend API for the Morning Brief application",
    version="1.0.0",
)


app.include_router(health_router)
app.include_router(categories_router)
app.include_router(users_router)
app.include_router(news_router)
app.include_router(news_ingestion_router)
app.include_router(briefings.router)

@app.get("/")
async def root():
    return {
        "message": "Morning Brief API is running"
    }