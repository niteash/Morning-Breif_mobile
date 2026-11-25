"""Shared local-date contract for scheduled and requested briefings."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Asia/Yangon"


def user_timezone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ValueError, ZoneInfoNotFoundError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def briefing_date(name: str | None, now: datetime | None = None) -> str:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Briefing time must be timezone-aware")
    return instant.astimezone(user_timezone(name)).date().isoformat()


def get_briefing_date(client, user_id: str) -> str:
    response = (client.table("profiles").select("timezone")
                .eq("id", user_id).limit(1).execute())
    rows = response.data or []
    return briefing_date(rows[0].get("timezone") if rows else None)
