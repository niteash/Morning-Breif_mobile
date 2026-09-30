from fastapi import APIRouter

from app.lib.supabase import supabase


router = APIRouter(
    prefix="/api/v1/categories",
    tags=["Categories"],
)


@router.get("")
async def get_categories():
    response = (
        supabase
        .table("categories")
        .select("id, slug, name_en, name_my, active")
        .eq("active", True)
        .execute()
    )

    return {
        "categories": response.data
    }