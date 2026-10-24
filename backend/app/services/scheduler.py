import asyncio
import inspect
import logging
import os
import tempfile

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.lib.supabase import admin_supabase
from app.services.ai.gemini import generate_briefing_script
from app.services.news.relevance import is_relevant
from app.services.news.ranker import rank_candidates
from app.services.news.clustering import cluster_stories
from app.services.storage import upload_briefing_audio
from app.services.tts.azure import generate_speech
from app.services.push_notifications import send_briefing_notification


logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

_in_progress: set[str] = set()

DEFAULT_TIMEZONE = "Asia/Yangon"
DEFAULT_DELIVERY_HOUR = 7
DEFAULT_DELIVERY_MINUTE = 0

DEFAULT_STORIES_PER_CATEGORY = 5
NEWS_LOOKBACK_HOURS = 24
MAX_DATABASE_ROWS = 50
MAX_RANKING_CANDIDATES = 20
CLUSTER_SIMILARITY_THRESHOLD = 0.45


# =========================================
# TIMEZONE HELPERS
# =========================================

def get_user_timezone(profile: dict) -> ZoneInfo:
    """Return the user's timezone, falling back to Myanmar time."""

    timezone_name = profile.get("timezone") or DEFAULT_TIMEZONE

    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning(
            "Invalid timezone %r for user %s. Using %s.",
            timezone_name,
            profile.get("id"),
            DEFAULT_TIMEZONE,
        )
        return ZoneInfo(DEFAULT_TIMEZONE)


# =========================================
# NEWS SELECTION
# =========================================

def select_user_categories(user_id: str) -> list[dict]:
    """Retrieve categories selected by a user."""

    response = (
        admin_supabase.table("user_categories")
        .select("category_id, categories(id, slug, name_en, name_my)")
        .eq("user_id", user_id)
        .execute()
    )

    categories = []

    for row in response.data or []:
        category = row.get("categories")

        if isinstance(category, dict):
            categories.append(category)
        elif isinstance(category, list):
            categories.extend(
                item for item in category if isinstance(item, dict)
            )

    return categories


def select_recent_news(category: dict) -> list[dict]:
    """Fetch, filter, rank, and deduplicate recent stories."""

    category_id = category.get("id")
    category_slug = category.get("slug", "")

    if not category_id:
        return []

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=NEWS_LOOKBACK_HOURS)
    ).isoformat()

    response = (
        admin_supabase.table("news_items")
        .select("*")
        .eq("category_id", category_id)
        .gte("published_at", cutoff)
        .order("published_at", desc=True)
        .limit(MAX_DATABASE_ROWS)
        .execute()
    )

    candidates = []

    for story in response.data or []:
        title = (story.get("title") or "").strip()

        if not title:
            continue

        if not is_relevant(
            category_slug,
            title,
            story.get("description") or "",
        ):
            continue

        candidates.append(story)

    if not candidates:
        return []

    ranked = rank_candidates(
        candidates,
        category_slug=category_slug,
        limit=MAX_RANKING_CANDIDATES,
    )

    clusters = cluster_stories(
        ranked,
        similarity_threshold=CLUSTER_SIMILARITY_THRESHOLD,
    )

    selected = [
        cluster[0]
        for cluster in clusters
        if cluster
    ]

    return selected[:DEFAULT_STORIES_PER_CATEGORY]


def collect_user_news(user_id: str) -> list[dict]:
    """Build one combined briefing from the user's selected categories."""

    categories = select_user_categories(user_id)

    if not categories:
        logger.info(
            "Skipping user %s: no categories selected.",
            user_id,
        )
        return []

    result = []

    for category in categories:
        stories = select_recent_news(category)

        if not stories:
            logger.info(
                "No recent stories for user %s in category %s.",
                user_id,
                category.get("slug"),
            )
            continue

        result.append({
            "category": category,
            "stories": stories,
        })

    return result


# =========================================
# DATABASE HELPERS
# =========================================

def get_existing_briefing(
    user_id: str,
    briefing_date: str,
) -> dict | None:
    """Retrieve a briefing for a user and local date."""

    response = (
        admin_supabase.table("briefings")
        .select("id, status, audio_url")
        .eq("user_id", user_id)
        .eq("briefing_date", briefing_date)
        .limit(1)
        .execute()
    )

    rows = response.data or []
    return rows[0] if rows else None


def save_briefing(
    user_id: str,
    briefing_date: str,
    script: str,
    storage_path: str,
) -> None:
    """Persist the completed briefing."""

    record = {
        "user_id": user_id,
        "briefing_date": briefing_date,
        "title": "Morning Brief",
        "script": script,
        "audio_url": storage_path,
        "status": "ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    (
        admin_supabase.table("briefings")
        .upsert(
            record,
            on_conflict="user_id,briefing_date",
        )
        .execute()
    )


# =========================================
# PUSH NOTIFICATIONS
# =========================================

async def notify_user_briefing_ready(
    user_id: str,
    briefing_date: str,
) -> None:
    """Notify every active device belonging to the user."""

    try:
        response = await asyncio.to_thread(
            lambda: (
                admin_supabase.table("device_tokens")
                .select("id, fcm_token")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .execute()
            )
        )

        devices = response.data or []

        if not devices:
            logger.info(
                "No active push devices for user %s.",
                user_id,
            )
            return

        for device in devices:
            token = device.get("fcm_token")

            if not token:
                continue

            try:
                sent = await asyncio.to_thread(
                    send_briefing_notification,
                    token,
                    briefing_date,
                )

                if not sent:
                    logger.warning(
                        "Push notification was not sent to a device "
                        "belonging to user %s.",
                        user_id,
                    )

            except Exception:
                logger.exception(
                    "Failed to notify a device belonging to user %s.",
                    user_id,
                )

    except Exception:
        logger.exception(
            "Could not retrieve push devices for user %s.",
            user_id,
        )


# =========================================
# BRIEFING GENERATION
# =========================================

async def generate_scheduled_briefing(profile: dict) -> None:
    """Generate, store, and announce one combined daily briefing."""

    user_id = profile.get("id")

    if not user_id:
        logger.error("Cannot generate a briefing without a user ID.")
        return

    user_timezone = get_user_timezone(profile)
    briefing_date = datetime.now(user_timezone).date().isoformat()

    lock_key = f"{user_id}:{briefing_date}"

    if lock_key in _in_progress:
        logger.info(
            "Generation already running for user %s.",
            user_id,
        )
        return

    _in_progress.add(lock_key)
    local_audio_path = None

    try:
        # 1. Skip an already completed briefing.
        existing = await asyncio.to_thread(
            get_existing_briefing,
            user_id,
            briefing_date,
        )

        if existing and existing.get("status") == "ready":
            logger.info(
                "Briefing already ready for user %s on %s.",
                user_id,
                briefing_date,
            )
            return

        # 2. Collect the user's selected news categories.
        categories = await asyncio.to_thread(
            collect_user_news,
            user_id,
        )

        if not categories:
            logger.warning(
                "No relevant news for user %s; generation skipped.",
                user_id,
            )
            return

        logger.info(
            "Generating briefing for user %s across %d categories.",
            user_id,
            len(categories),
        )

        # 3. Generate the Burmese script.
        script_result = await asyncio.to_thread(
            generate_briefing_script,
            categories=categories,
            regeneration_id=None,
        )

        if inspect.isawaitable(script_result):
            script = await script_result
        else:
            script = script_result

        if not isinstance(script, str) or not script.strip():
            raise RuntimeError(
                "Gemini returned an empty or invalid briefing script."
            )

        script = script.strip()

        # 4. Generate one combined MP3.
        os.makedirs("tmp", exist_ok=True)

        with tempfile.NamedTemporaryFile(
            prefix=f"{user_id}-",
            suffix=".mp3",
            dir="tmp",
            delete=False,
        ) as temp_file:
            local_audio_path = temp_file.name

        await asyncio.to_thread(
            generate_speech,
            text=script,
            output_path=local_audio_path,
        )

        if (
            not os.path.isfile(local_audio_path)
            or os.path.getsize(local_audio_path) == 0
        ):
            raise RuntimeError(
                "Azure TTS did not produce a valid audio file."
            )

        # 5. Upload the audio before marking the briefing ready.
        storage_path = f"{user_id}/{briefing_date}.mp3"

        await asyncio.to_thread(
            upload_briefing_audio,
            file_path=local_audio_path,
            storage_path=storage_path,
        )

        # 6. Persist the completed briefing.
        await asyncio.to_thread(
            save_briefing,
            user_id,
            briefing_date,
            script,
            storage_path,
        )

        logger.info(
            "Briefing saved successfully for user %s on %s.",
            user_id,
            briefing_date,
        )

        # 7. Notify devices only after the database save succeeds.
        await notify_user_briefing_ready(
            user_id=user_id,
            briefing_date=briefing_date,
        )

    except Exception:
        logger.exception(
            "Scheduled briefing failed for user %s.",
            user_id,
        )

    finally:
        if local_audio_path and os.path.exists(local_audio_path):
            try:
                os.remove(local_audio_path)
            except OSError:
                logger.warning(
                    "Could not remove temporary audio file %s.",
                    local_audio_path,
                )

        _in_progress.discard(lock_key)


# =========================================
# SCHEDULE CHECK
# =========================================

async def check_due_users() -> None:
    """Find users whose configured local delivery minute has arrived."""

    logger.info("Checking scheduled briefing deliveries.")

    try:
        response = await asyncio.to_thread(
            lambda: (
                admin_supabase.table("profiles")
                .select(
                    "id, timezone, delivery_hour, delivery_minute"
                )
                .execute()
            )
        )

        profiles = response.data or []

    except Exception:
        logger.exception("Failed to retrieve profiles for scheduling.")
        return

    now_utc = datetime.now(timezone.utc)

    for profile in profiles:
        user_id = profile.get("id")

        if not user_id:
            continue

        user_timezone = get_user_timezone(profile)
        local_now = now_utc.astimezone(user_timezone)

        delivery_hour = profile.get("delivery_hour")
        delivery_minute = profile.get("delivery_minute")

        if delivery_hour is None:
            delivery_hour = DEFAULT_DELIVERY_HOUR

        if delivery_minute is None:
            delivery_minute = DEFAULT_DELIVERY_MINUTE

        if (
            local_now.hour == delivery_hour
            and local_now.minute == delivery_minute
        ):
            logger.info(
                "Delivery time reached for user %s at %s.",
                user_id,
                local_now.isoformat(),
            )

            await generate_scheduled_briefing(profile)


# =========================================
# SCHEDULER LIFECYCLE
# =========================================

def start_scheduler() -> None:
    """Start the periodic delivery-time checker."""

    if scheduler.running:
        logger.info("Scheduler is already running.")
        return

    scheduler.add_job(
        check_due_users,
        trigger=IntervalTrigger(minutes=1),
        id="morning_brief_delivery_checker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=55,
    )

    scheduler.start()

    logger.info(
        "Morning Brief scheduler started; checking every minute."
    )


def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""

    if not scheduler.running:
        return

    scheduler.shutdown(wait=False)

    logger.info("Morning Brief scheduler stopped.")