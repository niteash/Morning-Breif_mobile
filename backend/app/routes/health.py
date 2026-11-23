import asyncio

from fastapi import APIRouter, HTTPException, Response

from app.lib.supabase import admin_supabase


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health_check(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "ok",
        "service": "morning-brief-api",
    }


@router.get("/ready")
async def readiness_check(response: Response):
    """Verify the API can reach its required database without reading user data."""
    response.headers["Cache-Control"] = "no-store"

    def check_database() -> None:
        admin_supabase.table("categories").select("id").limit(1).execute()

    try:
        await asyncio.wait_for(asyncio.to_thread(check_database), timeout=4)
    except Exception:
        raise HTTPException(status_code=503, detail="Service is not ready") from None
    return {"status": "ready", "service": "morning-brief-api"}
