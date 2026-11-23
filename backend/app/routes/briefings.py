from uuid import UUID
import logging
import os
from fastapi import Query
from datetime import datetime, timezone
import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app.dependencies.auth import get_current_user
from app.lib.supabase import create_supabase_client, admin_supabase
from app.services.briefing.jobs import (
    generate_and_save, generation_disabled, GenerationUnavailable, GenerationBusy, GenerationLimited, LostGenerationLease, GenerationDisabled,
)
from app.services.entitlements import require_generation_access, get_trial
from app.services.news.batch import run_ingestion_batch, IngestionBusy
from app.services.news.selector import select_recent_stories
from app.services.storage import (
    create_briefing_signed_url,
)
from app.services.briefing.dates import get_briefing_date
from app.services.briefing.pipeline import PipelineStageError
from app.services.entitlements import TrialAccessDenied, EntitlementUnavailable


router = APIRouter(
    prefix="/api/v1/briefings",
    tags=["Briefings"],
)
logger = logging.getLogger(__name__)
ON_DEMAND_NEWS_REFRESH_ENABLED = os.getenv("ON_DEMAND_NEWS_REFRESH_ENABLED", "false").lower() == "true"


def has_usable_stories(categories: list[dict]) -> bool:
    return any((story.get("title") or "").strip()
               for group in categories for story in group.get("stories", []))


# =========================================================
# REQUEST MODEL
# =========================================================


class GenerateBriefingRequest(BaseModel):
    regeneration_id: str | None = Field(default=None, max_length=128)


class QueueBriefingRequest(BaseModel):
    request_key: str = Field(min_length=8, max_length=128)
    length: Literal['quick', 'standard', 'detailed'] = 'standard'


class PronunciationReportRequest(BaseModel):
    phrase: str = Field(min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=500)


REQUEST_FIELDS = (
    'id,user_id,briefing_date,request_key,length,state,progress,message,'
    'error_code,briefing_id,created_at,started_at,finished_at,updated_at'
)


@router.post('/requests', status_code=202)
def queue_briefing(
    request: QueueBriefingRequest,
    current_user: dict = Depends(get_current_user),
):
    """Persist an idempotent request; a separate worker performs paid work."""
    try:
        entitlement = get_trial(current_user['user_id'])
        if not entitlement.get('can_generate'):
            raise HTTPException(403, 'An active plan is required for generation')
        if request.length != 'standard' and entitlement.get('entitlement_kind') != 'purchase':
            raise HTTPException(403, {
                'code': 'premium_length_required',
                'message': 'Quick and detailed briefings are premium features.',
            })
        client = create_supabase_client(current_user['access_token'])
        day = get_briefing_date(client, current_user['user_id'])
        job = admin_supabase.rpc('enqueue_briefing_request', {
            'p_user_id': current_user['user_id'], 'p_date': day, 'p_request_key': request.request_key,
            'p_length': request.length,
            'p_priority': 10 if entitlement.get('entitlement_kind') == 'purchase' else 0,
        }).execute().data
        if not isinstance(job, dict) or job.get('user_id') != current_user['user_id']:
            raise RuntimeError('Invalid queue response')
        return {'request': {key: job.get(key) for key in REQUEST_FIELDS.split(',')}}
    except HTTPException:
        raise
    except Exception as error:
        logger.warning('Generation enqueue failed: error_type=%s', type(error).__name__)
        raise HTTPException(503, 'Generation queue is temporarily unavailable')


@router.get('/requests/{request_id}')
def get_generation_request(
    request_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    try:
        rows = (create_supabase_client(current_user['access_token'])
                .table('briefing_requests').select(REQUEST_FIELDS)
                .eq('id', str(request_id)).eq('user_id', current_user['user_id'])
                .limit(1).execute().data or [])
        if not rows:
            raise HTTPException(404, 'Generation request not found')
        return {'request': rows[0]}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Generation status is temporarily unavailable')


@router.post('/{briefing_id}/pronunciation-reports', status_code=201)
def report_pronunciation(
    briefing_id: UUID,
    report: PronunciationReportRequest,
    current_user: dict = Depends(get_current_user),
):
    """Record a bounded report without exposing the private review queue."""
    phrase = report.phrase.strip()
    if not phrase:
        raise HTTPException(422, 'Phrase is required')
    try:
        rows = (admin_supabase.table('briefings').select('id').eq('id', str(briefing_id))
                .eq('user_id', current_user['user_id']).limit(1).execute().data or [])
        if not rows:
            raise HTTPException(404, 'Briefing not found')
        created = admin_supabase.table('pronunciation_reports').insert({
            'user_id': current_user['user_id'], 'briefing_id': str(briefing_id),
            'phrase': phrase, 'notes': report.notes.strip() if report.notes else None,
        }).execute().data or []
        return {'report_id': created[0]['id'] if created else None, 'accepted': True}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Pronunciation report could not be saved') from None


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
    print("USER: [redacted]")
    print("========================================")

    try:
        # -------------------------------------------------
        # SELECT RECENT NEWS
        # -------------------------------------------------

        selection_started = time.perf_counter()

        categories = await select_recent_stories(
            user_id=user_id,
            access_token=access_token,
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
            "date": get_briefing_date(create_supabase_client(access_token), user_id),
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
            type(error).__name__,
        )


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
    print("USER: [redacted]")
    print("========================================")

    try:
        # -------------------------------------------------
        # DATABASE QUERY
        # -------------------------------------------------

        supabase = create_supabase_client(
            access_token
        )

        today = get_briefing_date(supabase, user_id)

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
                """ + (",source_metadata" if os.getenv("BRIEFING_SOURCES_ENABLED", "true") == "true" else "")
                + ",chapters,target_minutes"
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
                    type(error).__name__,
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
            type(error).__name__,
        )


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

    try:
        print()
        print("========================================")
        print("GENERATING MORNING BRIEF")
        print("USER: [redacted]")
        print("========================================")

        # -------------------------------------------------
        # GENERATION TIMESTAMP
        # -------------------------------------------------

        generated_at = datetime.now(
            timezone.utc
        )

        today = get_briefing_date(create_supabase_client(access_token), user_id)

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

        if not has_usable_stories(categories):
            # Do not let an unauthorised account trigger network/database work, and
            # do not refresh feeds when audio providers are unavailable anyway.
            await asyncio.to_thread(require_generation_access, user_id)
            if generation_disabled():
                raise GenerationDisabled()
            if not ON_DEMAND_NEWS_REFRESH_ENABLED:
                raise HTTPException(status_code=409, detail={
                    'code': 'no_recent_news', 'status': 'empty',
                    'message': 'No fresh stories are available in the selected categories. News refresh is disabled.',
                })
            try:
                ingestion = await run_ingestion_batch()
                logger.info(
                    "On-demand news refresh complete: successful_feeds=%s failed_feeds=%s inserted=%s",
                    ingestion.get("successful_feeds"), ingestion.get("failed_feeds"),
                    ingestion.get("totals", {}).get("inserted"),
                )
            except IngestionBusy:
                logger.info("On-demand news refresh joined an existing ingestion window")
            categories = await select_recent_stories(
                user_id=user_id, access_token=access_token, hours=24,
            )
            if not has_usable_stories(categories):
                raise HTTPException(status_code=409, detail={
                    'code': 'no_recent_news', 'status': 'empty',
                    'message': 'No fresh stories are available in the selected categories after refreshing reviewed feeds.',
                })

        saved_briefing, _newly_generated = await asyncio.to_thread(
            generate_and_save, user_id, today, categories, request.regeneration_id,
        )
        # -------------------------------------------------
        # SIGNED AUDIO URL
        # -------------------------------------------------

        audio_signed_url = None

        if saved_briefing.get("audio_url"):
            signed_url_started = time.perf_counter()

            try:
                audio_signed_url = create_briefing_signed_url(saved_briefing["audio_url"], expires_in=3600)
            except Exception:
                # The briefing is already saved. A transient signing failure should
                # not invite another paid generation; the saved endpoint can retry.
                audio_signed_url = None

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
                "generated_at": saved_briefing.get("generated_at"),
            },
            "generated_at": saved_briefing.get("generated_at"),
            "categories": categories,
        }

    except TrialAccessDenied:
        raise HTTPException(status_code=403, detail="An active trial is required for new generation")
    except EntitlementUnavailable:
        raise HTTPException(status_code=503, detail="Trial status is temporarily unavailable")
    except GenerationDisabled:
        raise HTTPException(status_code=503, detail={
            'code': 'generation_disabled', 'status': 'disabled',
            'message': 'Audio generation is disabled or providers are not configured on this backend. An authorized audio test is required.',
        })
    except GenerationBusy as error:
        seconds = error.detail.get('retry_after_seconds')
        raise HTTPException(status_code=409, detail=error.detail,
                            headers={'Retry-After': str(seconds)} if seconds is not None else None)
    except GenerationLimited:
        raise HTTPException(status_code=429, detail={
            'code': 'generation_limit_reached',
            'status': 'limited',
            'message': 'Today\'s regeneration limit has been reached. The latest ready audio remains available.',
        })
    except (GenerationUnavailable, LostGenerationLease):
        raise HTTPException(status_code=503, detail="Generation is temporarily unavailable. Please try again later.")
    except ValueError:
        raise HTTPException(status_code=422, detail="No usable news is available yet.")
    except PipelineStageError as error:
        logger.error(
            "Briefing generation pipeline failed: stage=%s error_type=%s",
            error.stage,
            error.error_type,
        )
        raise HTTPException(status_code=503, detail={
            "code": "generation_pipeline_failed",
            "stage": error.stage,
            "message": "Audio generation failed temporarily. Please try again later.",
        })
    except HTTPException:
        raise

    except Exception as error:
        print()
        print("========================================")
        print("BRIEFING GENERATION ERROR")
        print("ERROR:", type(error).__name__)
        print("========================================")

        raise HTTPException(
            status_code=500,
            detail="Briefing generation failed. Please try again later.",
        )


# History uses the caller's JWT/RLS, never a service-role row lookup.

HISTORY_FIELDS = 'id,user_id,briefing_date,title,duration_seconds,status,generated_at,created_at,updated_at'


@router.get('/history')
def get_briefing_history(
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    try:
        rows = (create_supabase_client(current_user['access_token']).table('briefings')
                .select(HISTORY_FIELDS).eq('user_id', current_user['user_id'])
                .order('briefing_date', desc=True).order('id', desc=True)
                .range(offset, offset + limit).execute().data or [])
        return {'briefings': rows[:limit], 'next_offset': offset + limit if len(rows) > limit and offset + limit <= 10000 else None}
    except Exception:
        raise HTTPException(503, 'Briefing history is temporarily unavailable')


@router.get('/history/{briefing_id}')
def get_historical_briefing(briefing_id: UUID, current_user: dict = Depends(get_current_user)):
    try:
        rows = (create_supabase_client(current_user['access_token']).table('briefings')
                .select(HISTORY_FIELDS + ',script,audio_url,chapters,target_minutes' + (',source_metadata' if os.getenv('BRIEFING_SOURCES_ENABLED', 'true') == 'true' else ''))
                .eq('user_id', current_user['user_id']).eq('id', str(briefing_id))
                .limit(1).execute().data or [])
        if not rows:
            raise HTTPException(404, 'Briefing not found')
        briefing = dict(rows[0])
        # Defense in depth before invoking the privileged storage signer.
        if briefing.get('user_id') != current_user['user_id']:
            raise HTTPException(404, 'Briefing not found')
        path = briefing.get('audio_url')
        briefing['audio_url'] = None
        if path and briefing.get('status') == 'ready':
            if (not path.startswith(current_user['user_id'] + '/')
                    or any(part in ('', '.', '..') for part in path.split('/'))
                    or any(char in path for char in ('%', '?', '#', '\\'))):
                raise HTTPException(503, 'Briefing audio is temporarily unavailable')
            briefing['audio_url'] = create_briefing_signed_url(path, expires_in=3600)
        return {'briefing': briefing}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Briefing audio is temporarily unavailable')
