from datetime import datetime, timezone
import os
import time
import traceback

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client
from app.services.ai.gemini import generate_briefing_script
from app.services.news.selector import select_recent_stories
from app.services.scheduler import notify_user_briefing_ready
from app.services.storage import (
    create_briefing_signed_url,
    upload_briefing_audio,
)
from app.services.tts.azure import generate_speech


router = APIRouter(
    prefix="/api/v1/briefings",
    tags=["Briefings"],
)


# =========================================================
# REQUEST MODEL
# =========================================================


class GenerateBriefingRequest(BaseModel):
    regeneration_id: str | None = None


# =========================================================
# GET TODAY'S STORY BRIEFING
# =========================================================


@router.get("/today")
async def get_today_briefing(
    current_user: dict = Depends(get_current_user),
):
    request_started = time.perf_counter()

    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    print()
    print("========================================")
    print("LOADING TODAY'S STORY BRIEFING")
    print("USER:", user_id)
    print("========================================")

    try:
        # -------------------------------------------------
        # SELECT RECENT NEWS
        # -------------------------------------------------

        selection_started = time.perf_counter()

        categories = await select_recent_stories(
            user_id=user_id,
            access_token=access_token,
            stories_per_category=5,
            hours=24,
        )

        selection_duration = (
            time.perf_counter() - selection_started
        )

        # -------------------------------------------------
        # PERFORMANCE METRICS
        # -------------------------------------------------

        total_stories = sum(
            len(category.get("stories", []))
            for category in categories
        )

        print(
            f"[Performance] Story selection: "
            f"{selection_duration:.3f}s"
        )

        print(
            f"[Performance] Categories returned: "
            f"{len(categories)}"
        )

        print(
            f"[Performance] Stories returned: "
            f"{total_stories}"
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        response = {
            "date": datetime.now(
                timezone.utc
            ).date().isoformat(),
            "categories": categories,
        }

        total_duration = (
            time.perf_counter() - request_started
        )

        print(
            f"[Performance] GET /today total: "
            f"{total_duration:.3f}s"
        )

        print("========================================")

        return response

    except Exception as error:
        print(
            "[Performance] GET /today failed:",
            str(error),
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to load today's briefing",
        )


# =========================================================
# GET SAVED AI BRIEFING
# =========================================================


@router.get("/today/saved")
async def get_saved_today_briefing(
    current_user: dict = Depends(get_current_user),
):
    request_started = time.perf_counter()

    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    print()
    print("========================================")
    print("LOADING SAVED BRIEFING")
    print("USER:", user_id)
    print("========================================")

    try:
        # -------------------------------------------------
        # DATABASE QUERY
        # -------------------------------------------------

        supabase = create_supabase_client(
            access_token
        )

        today = datetime.now(
            timezone.utc
        ).date().isoformat()

        query_started = time.perf_counter()

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
                generated_at,
                created_at,
                updated_at
                """
            )
            .eq("user_id", user_id)
            .eq("briefing_date", today)
            .limit(1)
            .execute()
        )

        query_duration = (
            time.perf_counter() - query_started
        )

        print(
            f"[Performance] Saved briefing query: "
            f"{query_duration:.3f}s"
        )

        # -------------------------------------------------
        # NO SAVED BRIEFING
        # -------------------------------------------------

        if not response.data:
            print(
                "[Briefing] No saved briefing found"
            )

            print(
                f"[Performance] GET /today/saved total: "
                f"{time.perf_counter() - request_started:.3f}s"
            )

            return {
                "briefing": None
            }

        briefing = response.data[0]

        # -------------------------------------------------
        # CREATE FRESH SIGNED AUDIO URL
        # -------------------------------------------------

        if briefing.get("audio_url"):
            try:
                signed_url_started = time.perf_counter()

                briefing["audio_url"] = (
                    create_briefing_signed_url(
                        briefing["audio_url"],
                        expires_in=3600,
                    )
                )

                print(
                    "[Performance] Signed URL creation: "
                    f"{time.perf_counter() - signed_url_started:.3f}s"
                )

            except Exception as error:
                print(
                    "[Storage] Signed URL error:",
                    str(error),
                )

                briefing["audio_url"] = None

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        print(
            f"[Performance] GET /today/saved total: "
            f"{time.perf_counter() - request_started:.3f}s"
        )

        print("========================================")

        return {
            "briefing": briefing
        }

    except Exception as error:
        print(
            "[Briefing] Failed to load saved briefing:",
            str(error),
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to load saved briefing",
        )


# =========================================================
# GENERATE / REGENERATE AI BRIEFING
# =========================================================


@router.post("/generate")
async def generate_briefing(
    request: GenerateBriefingRequest,
    current_user: dict = Depends(get_current_user),
):
    request_started = time.perf_counter()

    user_id = current_user["user_id"]
    access_token = current_user["access_token"]

    local_audio_path = None

    try:
        print()
        print("========================================")
        print("GENERATING MORNING BRIEF")
        print("USER:", user_id)
        print("REGENERATION ID:", request.regeneration_id)
        print("========================================")

        # -------------------------------------------------
        # GENERATION TIMESTAMP
        # -------------------------------------------------

        generated_at = datetime.now(
            timezone.utc
        )

        today = generated_at.date().isoformat()

        print(
            "[Briefing] Generation time:",
            generated_at.isoformat(),
        )

        # -------------------------------------------------
        # GET FRESH NEWS
        # -------------------------------------------------

        selection_started = time.perf_counter()

        categories = await select_recent_stories(
            user_id=user_id,
            access_token=access_token,
            stories_per_category=5,
            hours=24,
        )

        print(
            f"[Performance] Story selection: "
            f"{time.perf_counter() - selection_started:.3f}s"
        )

        print(
            "[Briefing] Categories:",
            len(categories),
        )

        if not categories:
            raise RuntimeError(
                "No news categories available"
            )

        # -------------------------------------------------
        # GEMINI SCRIPT GENERATION
        # -------------------------------------------------

        print(
            "[Briefing] Generating Gemini script..."
        )

        gemini_started = time.perf_counter()

        briefing_text = generate_briefing_script(
            categories=categories,
            regeneration_id=request.regeneration_id,
        )

        print(
            f"[Performance] Gemini generation: "
            f"{time.perf_counter() - gemini_started:.3f}s"
        )

        if not briefing_text:
            raise RuntimeError(
                "Gemini returned an empty briefing"
            )

        print(
            "[Briefing] Script generated:",
            len(briefing_text),
            "characters",
        )

        # -------------------------------------------------
        # PREPARE LOCAL AUDIO PATH
        # -------------------------------------------------

        safe_user_id = str(user_id)

        os.makedirs(
            "tmp",
            exist_ok=True,
        )

        local_audio_path = (
            f"tmp/{safe_user_id}-{today}.mp3"
        )

        # -------------------------------------------------
        # AZURE TEXT-TO-SPEECH
        # -------------------------------------------------

        print(
            "[Briefing] Generating Azure TTS..."
        )

        tts_started = time.perf_counter()

        generate_speech(
            text=briefing_text,
            output_path=local_audio_path,
        )

        print(
            f"[Performance] Azure TTS: "
            f"{time.perf_counter() - tts_started:.3f}s"
        )

        if not os.path.exists(local_audio_path):
            raise RuntimeError(
                "Audio generation completed but the file was not found"
            )

        print(
            "[Briefing] Audio generated:",
            local_audio_path,
        )

        # -------------------------------------------------
        # SUPABASE STORAGE
        # -------------------------------------------------

        storage_path = (
            f"{safe_user_id}/{today}.mp3"
        )

        print(
            "[Briefing] Uploading audio..."
        )

        upload_started = time.perf_counter()

        upload_briefing_audio(
            file_path=local_audio_path,
            storage_path=storage_path,
        )

        print(
            f"[Performance] Audio upload: "
            f"{time.perf_counter() - upload_started:.3f}s"
        )

        print(
            "[Briefing] Audio uploaded:",
            storage_path,
        )

        # -------------------------------------------------
        # SAVE DATABASE RECORD
        # -------------------------------------------------

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
            "generated_at": generated_at.isoformat(),
        }

        print(
            "[Briefing] Saving database record..."
        )

        database_started = time.perf_counter()

        response = (
            supabase
            .table("briefings")
            .upsert(
                briefing_payload,
                on_conflict="user_id,briefing_date",
            )
            .execute()
        )

        print(
            f"[Performance] Database save: "
            f"{time.perf_counter() - database_started:.3f}s"
        )

        if not response.data:
            raise RuntimeError(
                "Failed to save briefing"
            )

        saved_briefing = response.data[0]

        print(
            "[Briefing] Briefing saved:",
            saved_briefing["id"],
        )
        # -------------------------------------------------
        # PUSH NOTIFICATION
        # -------------------------------------------------

        try:
            await notify_user_briefing_ready(
                user_id=user_id,
                briefing_date=today,
            )

            print(
                "[Push] Briefing-ready notification workflow completed."
            )

        except Exception:
            # Notification failure must not invalidate a saved briefing.
            print(
                "[Push] Notification failed; briefing remains saved."
            )
            traceback.print_exc()

        # -------------------------------------------------
        # SIGNED AUDIO URL
        # -------------------------------------------------

        audio_signed_url = None

        if saved_briefing.get("audio_url"):
            signed_url_started = time.perf_counter()

            audio_signed_url = (
                create_briefing_signed_url(
                    saved_briefing["audio_url"],
                    expires_in=3600,
                )
            )

            print(
                f"[Performance] Signed URL creation: "
                f"{time.perf_counter() - signed_url_started:.3f}s"
            )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        total_duration = (
            time.perf_counter() - request_started
        )

        print(
            f"[Performance] POST /generate total: "
            f"{total_duration:.3f}s"
        )

        print("========================================")

        return {
            "message": (
                "Morning briefing generated successfully"
            ),
            "briefing": {
                **saved_briefing,
                "audio_url": audio_signed_url,
                "generated_at": generated_at.isoformat(),
            },
            "generated_at": generated_at.isoformat(),
            "categories": categories,
        }

    except Exception as error:
        print()
        print("========================================")
        print("BRIEFING GENERATION ERROR")
        print("ERROR:", str(error))
        traceback.print_exc()
        print("========================================")

        raise HTTPException(
            status_code=500,
            detail=(
                "Briefing generation failed: "
                f"{str(error)}"
            ),
        )

    finally:
        # -------------------------------------------------
        # CLEAN UP LOCAL AUDIO
        # -------------------------------------------------

        if (
            local_audio_path
            and os.path.exists(local_audio_path)
        ):
            try:
                os.remove(local_audio_path)

                print(
                    "[Briefing] Local audio removed:",
                    local_audio_path,
                )

            except OSError as error:
                print(
                    "[Briefing] Local audio cleanup error:",
                    str(error),
                )
