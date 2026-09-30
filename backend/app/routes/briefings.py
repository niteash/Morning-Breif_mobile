from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client
from app.services.ai.gemini import generate_briefing_script
from app.services.news.selector import select_recent_stories
from app.services.storage import (
    create_briefing_signed_url,
    upload_briefing_audio,
)
from app.services.tts.azure import generate_speech


router = APIRouter(
    prefix="/api/v1/briefings",
    tags=["Briefings"],
)


@router.get("/today")
async def get_today_briefing(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    categories = await select_recent_stories(
        user_id=user_id,
        access_token=access_token,
        stories_per_category=5,
        hours=24,
    )

    return {
        "date": datetime.now(
            timezone.utc
        ).date().isoformat(),
        "categories": categories,
    }


@router.get("/today/saved")
async def get_saved_today_briefing(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    supabase = create_supabase_client(
        access_token
    )

    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    response = (
        supabase
        .table("briefings")
        .select(
            """
            id,
            user_id,
            briefing_date,
            title,
            script,
            audio_url,
            duration_seconds,
            status,
            created_at,
            updated_at
            """
        )
        .eq("user_id", user_id)
        .eq("briefing_date", today)
        .limit(1)
        .execute()
    )

    if not response.data:
        return {
            "briefing": None
        }

    briefing = response.data[0]

    if briefing.get("audio_url"):
        try:
            briefing["audio_url"] = (
                create_briefing_signed_url(
                    briefing["audio_url"],
                    expires_in=3600,
                )
            )
        except Exception as e:
            print(
                "SIGNED URL ERROR:",
                str(e),
            )

    return {
        "briefing": briefing
    }

@router.post("/generate")
async def generate_briefing(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    try:
        print()
        print("================================")
        print("GENERATING MORNING BRIEF")
        print("USER:", user_id)
        print("================================")

        # --------------------------------
        # 1. Get today's selected stories
        # --------------------------------

        categories = await select_recent_stories(
            user_id=user_id,
            access_token=access_token,
            stories_per_category=5,
            hours=24,
        )

        print(
            "CATEGORIES:",
            len(categories),
        )

        # --------------------------------
        # 2. Generate Burmese AI script
        # --------------------------------

        print("GENERATING GEMINI SCRIPT...")

        briefing_text = generate_briefing_script(
            categories
        )

        if not briefing_text:
            raise RuntimeError(
                "Gemini returned an empty briefing"
            )

        print(
            "SCRIPT GENERATED:",
            len(briefing_text),
            "characters",
        )

        # --------------------------------
        # 3. Generate Burmese MP3
        # --------------------------------

        today = datetime.now(
            timezone.utc
        ).date().isoformat()

        safe_user_id = str(user_id)

        local_audio_path = (
            f"tmp/{safe_user_id}-{today}.mp3"
        )

        print(
            "GENERATING AZURE TTS..."
        )

        generate_speech(
            text=briefing_text,
            output_path=local_audio_path,
        )

        print(
            "AUDIO GENERATED:",
            local_audio_path,
        )

        # --------------------------------
        # 4. Upload MP3 to Supabase
        # --------------------------------

        storage_path = (
            f"{safe_user_id}/{today}.mp3"
        )

        print(
            "UPLOADING AUDIO..."
        )

        upload_briefing_audio(
            file_path=local_audio_path,
            storage_path=storage_path,
        )

        print(
            "AUDIO UPLOADED:",
            storage_path,
        )

        # --------------------------------
        # 5. Save briefing to database
        # --------------------------------

        supabase = create_supabase_client(
            access_token
        )

        briefing_payload = {
            "user_id": user_id,
            "briefing_date": today,
            "title": "Morning Brief",
            "script": briefing_text,
            "audio_url": storage_path,
            "status": "ready",
        }

        print(
            "SAVING BRIEFING TO DATABASE..."
        )

        response = (
            supabase
            .table("briefings")
            .upsert(
                briefing_payload,
                on_conflict="user_id,briefing_date",
            )
            .execute()
        )

        if not response.data:
            raise RuntimeError(
                "Failed to save briefing"
            )

        saved_briefing = response.data[0]

        print(
            "BRIEFING SAVED:",
            saved_briefing["id"],
        )

        # --------------------------------
        # 6. Return result
        # --------------------------------

        return {
            "message": (
                "Morning briefing generated "
                "successfully"
            ),
            "briefing": saved_briefing,
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "categories": categories,
        }

    except Exception as e:
        import traceback

        print()
        print(
            "========== BRIEFING GENERATION ERROR =========="
        )
        print(str(e))
        traceback.print_exc()
        print(
            "==============================================="
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Briefing generation failed: "
                f"{str(e)}"
            ),
        )