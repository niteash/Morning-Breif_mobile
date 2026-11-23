import asyncio
import logging

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.lib.supabase import admin_supabase
from app.services.briefing.jobs import generate_and_save, GenerationBusy, GenerationLimited
from app.services.news.batch import IngestionBusy, run_ingestion_batch
from app.services.news.relevance import is_relevant
from app.services.news.ranker import rank_candidates
from app.services.news.clustering import cluster_stories
from app.services.news.selector import configured_story_limit, select_publisher_balanced
from app.services.news.personalization import interest_bonus
from app.services.notification_delivery import deliver_all_notifications
from app.services.account_deletion import process_account_deletions
from app.services.entitlements import (
    EntitlementUnavailable,
    TrialAccessDenied,
    require_generation_access,
)


logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

_in_progress: set[str] = set()

DEFAULT_TIMEZONE = "Asia/Yangon"
DEFAULT_DELIVERY_HOUR = 7
DEFAULT_DELIVERY_MINUTE = 0
PREPARATION_LEAD_MINUTES = 30
DELIVERY_CATCH_UP_MINUTES = 24 * 60

DEFAULT_STORIES_PER_CATEGORY = 5
NEWS_LOOKBACK_HOURS = 24
MAX_DATABASE_ROWS = 50
MAX_RANKING_CANDIDATES = 20
CLUSTER_SIMILARITY_THRESHOLD = 0.45
PROFILE_PAGE_SIZE = 100
DELIVERY_CONCURRENCY = 4
DELIVERY_QUEUE_SIZE = 8


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


def select_recent_news(category: dict, preferences: dict | None = None) -> list[dict]:
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
        .lte("published_at", datetime.now(timezone.utc).isoformat())
        .order("published_at", desc=True)
        .limit(MAX_DATABASE_ROWS)
        .execute()
    )

    candidates = []

    for story in response.data or []:
        preferences = preferences or {}
        if (story.get('source') or '').casefold().strip() in preferences.get('hidden_publishers', set()):
            continue
        story['_preference_score'] = (
            preferences.get('story_scores', {}).get(str(story.get('id')), 0)
            + interest_bonus(story, category_slug, preferences.get('profile'))
        )
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

    return select_publisher_balanced(clusters, configured_story_limit())


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
    preferences = {'hidden_publishers': set(), 'hidden_categories': set(), 'story_scores': {}, 'profile': {}}
    try:
        profile_rows = (admin_supabase.table('profiles').select('horoscope_sign,crypto_watchlist')
                        .eq('id', user_id).limit(1).execute().data or [])
        preferences['profile'] = profile_rows[0] if profile_rows else {}
        rows = (admin_supabase.table('story_feedback')
                .select('story_id,action,news_items(category_id,source)')
                .eq('user_id', user_id).execute().data or [])
        for row in rows:
            article = row.get('news_items') or {}
            if row.get('action') == 'hide_publisher':
                preferences['hidden_publishers'].add((article.get('source') or '').casefold().strip())
            elif row.get('action') == 'hide_topic':
                preferences['hidden_categories'].add(str(article.get('category_id')))
            elif row.get('action') in {'more_like_this', 'less_like_this'}:
                preferences['story_scores'][str(row.get('story_id'))] = 18 if row['action'] == 'more_like_this' else -18
    except Exception:
        logger.info('Story personalization unavailable; using category preferences')

    for category in categories:
        if str(category.get('id')) in preferences['hidden_categories']:
            continue
        stories = select_recent_news(category, preferences)

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


# =========================================
# BRIEFING GENERATION
# =========================================

async def generate_scheduled_briefing(profile: dict) -> None:
    """Generate and store the briefing for the scheduled local delivery date."""

    user_id = profile.get("id")

    if not user_id:
        logger.error("Cannot generate a briefing without a user ID.")
        return

    due_at = delivery_due_at(profile, datetime.now(timezone.utc))
    if due_at is None:
        return
    briefing_date = due_at.date().isoformat()

    lock_key = f"{user_id}:{briefing_date}"

    if lock_key in _in_progress:
        logger.info(
            "Generation already running for user %s.",
            user_id,
        )
        return

    _in_progress.add(lock_key)

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

        # Avoid even selecting/processing stories for inactive or expired accounts.
        # The durable generation service repeats this check immediately before claim.
        await asyncio.to_thread(require_generation_access, user_id)

        # 2. Collect the user's selected news categories.
        categories = await asyncio.to_thread(
            collect_user_news,
            user_id,
        )

        if not categories:
            # Feed refresh runs as its own scheduled task. Do not retry it once
            # per due user here: a quiet feed could otherwise trigger repeated
            # upstream requests throughout the catch-up window.
            logger.warning("No relevant news for scheduled briefing; generation skipped")
            return

        logger.info(
            "Generating briefing for user %s across %d categories.",
            user_id,
            len(categories),
        )

        await asyncio.to_thread(
            generate_and_save, user_id, briefing_date, categories, None,
            {'quick': 3, 'standard': 7, 'detailed': 13}.get(profile.get('briefing_length'), 7),
        )

    except (GenerationBusy, GenerationLimited, TrialAccessDenied, EntitlementUnavailable):
        logger.info("Scheduled generation deferred by database coordination")

    except Exception as error:
        # Provider/Storage exception bodies may contain private request details.
        logger.error("Scheduled briefing failed category=%s", type(error).__name__)

    finally:
        _in_progress.discard(lock_key)


# =========================================
# SCHEDULE CHECK
# =========================================

def is_delivery_due(profile: dict, now: datetime) -> bool:
    """Whether a profile is inside its generation window.

    Start preparation ahead of the requested delivery time, then allow a bounded
    catch-up window for slow provider/storage work and delayed worker ticks.
    """
    due_at = delivery_due_at(profile, now)
    if due_at is None:
        return False
    elapsed = (now.astimezone(timezone.utc) - due_at.astimezone(timezone.utc)).total_seconds()
    return -PREPARATION_LEAD_MINUTES * 60 <= elapsed <= DELIVERY_CATCH_UP_MINUTES * 60


def delivery_due_at(profile: dict, now: datetime) -> datetime | None:
    """Return the local scheduled instant whose preparation window contains now."""
    if not profile.get("id") or now.tzinfo is None:
        return None
    local = now.astimezone(get_user_timezone(profile))
    hour = profile.get("delivery_hour")
    minute = profile.get("delivery_minute")
    hour = DEFAULT_DELIVERY_HOUR if hour is None else hour
    minute = DEFAULT_DELIVERY_MINUTE if minute is None else minute
    if not isinstance(hour, int) or not isinstance(minute, int) or not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    schedule = profile.get("delivery_schedule") or "daily"
    if schedule not in {"daily", "weekdays"}:
        return None
    due_today = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local.weekday() >= 5 and profile.get('separate_weekend_schedule'):
        weekend_hour = profile.get('weekend_delivery_hour', 8)
        weekend_minute = profile.get('weekend_delivery_minute', 0)
        if isinstance(weekend_hour, int) and isinstance(weekend_minute, int):
            due_today = local.replace(hour=weekend_hour, minute=weekend_minute, second=0, microsecond=0)
    due_tomorrow = due_today + timedelta(days=1)
    instant = now.astimezone(timezone.utc)

    def eligible(due: datetime, *, allow_late: bool) -> bool:
        if schedule == "weekdays" and due.weekday() >= 5:
            return False
        elapsed = (instant - due.astimezone(timezone.utc)).total_seconds()
        latest = DELIVERY_CATCH_UP_MINUTES * 60 if allow_late else 0
        return -PREPARATION_LEAD_MINUTES * 60 <= elapsed <= latest

    # If the next local delivery is within its preparation lead, prefer it over
    # a nearly day-old delivery candidate (important for 00:00-hour schedules).
    if eligible(due_tomorrow, allow_late=False):
        return due_tomorrow
    if eligible(due_today, allow_late=True):
        return due_today
    if eligible(due_tomorrow, allow_late=True):
        return due_tomorrow
    return None


def fetch_profile_page(after_id: str | None = None) -> list[dict]:
    """Use a stable cursor; offsets can skip users when earlier rows are deleted."""
    query = admin_supabase.table("profiles").select(
        "id, timezone, delivery_hour, delivery_minute, delivery_schedule, automatic_briefing_enabled"
    ).eq("automatic_briefing_enabled", True)
    if after_id:
        query = query.gt("id", after_id)
    return query.order("id").limit(PROFILE_PAGE_SIZE).execute().data or []


async def check_due_users() -> dict:
    """Scan every profile page with a bounded queue and four delivery workers."""
    counts = {"profiles_scanned": 0, "queued": 0, "attempted": 0, "expired": 0, "task_errors": 0,
              "scan_complete": False}
    queue = asyncio.Queue(maxsize=DELIVERY_QUEUE_SIZE)

    async def deliver():
        while True:
            profile = await queue.get()
            try:
                if profile is None:
                    return
                # A queued user can leave the catch-up window while others generate.
                if not is_delivery_due(profile, datetime.now(timezone.utc)):
                    counts["expired"] += 1
                    continue
                counts["attempted"] += 1
                try:
                    await generate_scheduled_briefing(profile)
                except Exception as error:
                    counts["task_errors"] += 1
                    logger.warning("Delivery task failed: error_type=%s", type(error).__name__)
            finally:
                queue.task_done()

    async with asyncio.TaskGroup() as group:
        for _ in range(DELIVERY_CONCURRENCY):
            group.create_task(deliver())
        cursor = None
        try:
            while True:
                profiles = await asyncio.to_thread(fetch_profile_page, cursor)
                if not profiles:
                    counts["scan_complete"] = True
                    break
                # Do not infer end-of-data from a short page: server row limits vary.
                next_cursor = profiles[-1].get("id")
                if not next_cursor or (cursor and next_cursor <= cursor):
                    raise RuntimeError("Profile pagination did not advance")
                now = datetime.now(timezone.utc)
                for profile in profiles:
                    counts["profiles_scanned"] += 1
                    if is_delivery_due(profile, now):
                        await queue.put(profile)
                        counts["queued"] += 1
                cursor = next_cursor
        except Exception as error:
            logger.warning("Profile scan incomplete: error_type=%s", type(error).__name__)
        for _ in range(DELIVERY_CONCURRENCY):
            await queue.put(None)
    logger.info("Scheduled scan complete: %s", counts)
    return counts


async def ingest_scheduled_news() -> None:
    started = datetime.now(timezone.utc)
    try:
        result = await run_ingestion_batch()
        if result.get('totals', {}).get('inserted', 0) > 0:
            queued = await asyncio.to_thread(
                lambda: admin_supabase.rpc('enqueue_breaking_news', {
                    'p_since': started.isoformat(),
                }).execute().data)
            logger.info('Breaking-news alerts queued: count=%s', queued)
    except IngestionBusy:
        logger.info("Skipping overlapping ingestion batch")
    except Exception as error:
        logger.warning("Scheduled ingestion failed: error_type=%s", type(error).__name__)


# =========================================
# SCHEDULER LIFECYCLE
# =========================================

def start_scheduler(*, deliveries_enabled: bool = False, ingestion_enabled: bool = False,
                    ingestion_interval_minutes: int = 30, push_enabled: bool = False,
                    deletion_enabled: bool = False, generation_worker_enabled: bool = False,
                    retention_enabled: bool = False) -> None:
    """Enable only requested jobs in one dedicated process, with no overlapping ticks."""
    if not deliveries_enabled and not ingestion_enabled and not push_enabled and not deletion_enabled and not generation_worker_enabled and not retention_enabled:
        return
    if ingestion_enabled and not 5 <= ingestion_interval_minutes <= 1440:
        raise ValueError("News ingestion interval must be between 5 and 1440 minutes")
    if scheduler.running:
        return
    if deliveries_enabled:
        scheduler.add_job(
            check_due_users, trigger=IntervalTrigger(minutes=1),
            id="morning_brief_delivery_checker", replace_existing=True,
            max_instances=1, coalesce=True, misfire_grace_time=55,
        )
    if ingestion_enabled:
        scheduler.add_job(
            ingest_scheduled_news, trigger=IntervalTrigger(minutes=ingestion_interval_minutes),
            id="morning_brief_news_ingestion", replace_existing=True,
            max_instances=1, coalesce=True, misfire_grace_time=60,
            next_run_time=datetime.now(timezone.utc),
        )
    if push_enabled:
        scheduler.add_job(
            deliver_all_notifications, trigger=IntervalTrigger(minutes=1),
            id="morning_brief_push_delivery", replace_existing=True,
            max_instances=1, coalesce=True, misfire_grace_time=55,
        )
    if deletion_enabled:
        scheduler.add_job(
            process_account_deletions, trigger=IntervalTrigger(minutes=1),
            id="morning_brief_account_deletion", replace_existing=True,
            max_instances=1, coalesce=True, misfire_grace_time=55,
        )
    if generation_worker_enabled:
        from app.services.generation_queue import process_generation_requests
        scheduler.add_job(
            process_generation_requests, trigger=IntervalTrigger(seconds=3),
            id="morning_brief_generation_queue", replace_existing=True,
            max_instances=1, coalesce=True, misfire_grace_time=2,
            next_run_time=datetime.now(timezone.utc),
        )
    if retention_enabled:
        from app.services.retention import run_retention
        scheduler.add_job(
            run_retention, trigger=IntervalTrigger(hours=24),
            id='morning_brief_retention', replace_existing=True,
            max_instances=1, coalesce=True, misfire_grace_time=3600,
        )
    scheduler.start()
    logger.info("Worker started: deliveries=%s ingestion=%s", deliveries_enabled, ingestion_enabled)


def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""

    if not scheduler.running:
        return

    scheduler.shutdown(wait=False)

    logger.info("Morning Brief scheduler stopped.")
