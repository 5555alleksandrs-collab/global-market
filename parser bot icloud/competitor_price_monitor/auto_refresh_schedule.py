from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_DAILY_TIME = "10:00"
DEFAULT_TIMEZONE_NAME = "Europe/Moscow"


def normalize_daily_time(raw_value: str, default: str = DEFAULT_DAILY_TIME) -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        raw = default

    parts = raw.split(":", 1)
    if len(parts) != 2:
        return default

    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return default

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return default
    return "{0:02d}:{1:02d}".format(hour, minute)


def get_zoneinfo(timezone_name: str) -> ZoneInfo:
    name = str(timezone_name or "").strip() or DEFAULT_TIMEZONE_NAME
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE_NAME)


def calculate_next_daily_run(
    *,
    now: datetime | None = None,
    daily_time: str = DEFAULT_DAILY_TIME,
    timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> datetime:
    zone = get_zoneinfo(timezone_name)
    current = now.astimezone(zone) if now is not None else datetime.now(zone)
    normalized = normalize_daily_time(daily_time)
    hour, minute = [int(part) for part in normalized.split(":", 1)]

    candidate = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= current:
        candidate = candidate + timedelta(days=1)
    return candidate


def seconds_until_next_daily_run(
    *,
    now: datetime | None = None,
    daily_time: str = DEFAULT_DAILY_TIME,
    timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> float:
    current = now or datetime.now(get_zoneinfo(timezone_name))
    next_run = calculate_next_daily_run(
        now=current,
        daily_time=daily_time,
        timezone_name=timezone_name,
    )
    return max((next_run - current.astimezone(next_run.tzinfo)).total_seconds(), 0.0)


def format_daily_schedule_text(
    daily_time: str,
    timezone_name: str,
) -> str:
    normalized_time = normalize_daily_time(daily_time)
    zone = str(timezone_name or "").strip() or DEFAULT_TIMEZONE_NAME
    if zone == DEFAULT_TIMEZONE_NAME:
        return "каждый день в {0} МСК".format(normalized_time)
    return "каждый день в {0} ({1})".format(normalized_time, zone)


__all__ = [
    "DEFAULT_DAILY_TIME",
    "DEFAULT_TIMEZONE_NAME",
    "calculate_next_daily_run",
    "format_daily_schedule_text",
    "get_zoneinfo",
    "normalize_daily_time",
    "seconds_until_next_daily_run",
]
