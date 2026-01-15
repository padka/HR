"""
Timezone utilities for consistent datetime handling across the application.

Principles:
1. Storage: Always UTC aware datetime in PostgreSQL
2. API: Accept ISO8601 with timezone or (datetime + timezone_name)
3. UI: Display in UTC / Recruiter TZ / Candidate TZ

Usage:
    from backend.core.timezone_utils import normalize_to_utc, to_local_time

    # Normalize input
    utc_dt = normalize_to_utc(naive_dt, "Europe/Moscow")

    # Display
    local_str = format_for_ui(utc_dt, "Asia/Novosibirsk")
"""

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, available_timezones

__all__ = [
    "normalize_to_utc",
    "to_local_time",
    "format_for_ui",
    "ensure_aware",
    "parse_timezone",
    "DEFAULT_TIMEZONE",
]

DEFAULT_TIMEZONE = "UTC"

# Cache of valid timezone names (lowercase -> canonical)
_TZ_CACHE = {name.lower(): name for name in available_timezones()}


def parse_timezone(tz_name: Optional[str]) -> ZoneInfo:
    """
    Parse timezone name to ZoneInfo object.

    Handles:
    - None -> UTC
    - Case-insensitive matching
    - Spaces and underscores

    Args:
        tz_name: Timezone name like "Europe/Moscow" or "europe/moscow"

    Returns:
        ZoneInfo object

    Raises:
        ValueError: If timezone is invalid
    """
    if tz_name is None:
        return ZoneInfo(DEFAULT_TIMEZONE)

    cleaned = tz_name.strip()
    if cleaned == "":
        raise ValueError("Timezone is empty")

    # Normalize: strip, lowercase, replace spaces
    normalized = cleaned.lower().replace(" ", "_")

    # Try exact match first
    if normalized in _TZ_CACHE:
        canonical = _TZ_CACHE[normalized]
        return ZoneInfo(canonical)

    # Try as-is (might be already canonical)
    try:
        return ZoneInfo(cleaned)
    except Exception:
        pass

    raise ValueError(f"Invalid timezone: {tz_name}")


def ensure_aware(dt: datetime, tz_name: Optional[str] = None) -> datetime:
    """
    Ensure datetime is timezone-aware.

    If naive:
    - Use provided tz_name
    - Default to UTC if no tz_name

    If already aware:
    - Return as-is

    Args:
        dt: datetime object (naive or aware)
        tz_name: Timezone name to assume if naive

    Returns:
        Timezone-aware datetime
    """
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        # Already aware
        return dt

    # Naive datetime - make it aware
    if tz_name:
        tz = parse_timezone(tz_name)
    else:
        tz = timezone.utc

    return dt.replace(tzinfo=tz)


def normalize_to_utc(
    dt: datetime,
    tz_name: Optional[str] = None
) -> datetime:
    """
    Convert any datetime to UTC aware.

    Handles:
    - Naive datetime + timezone name
    - Aware datetime in any timezone
    - Already UTC datetime

    Args:
        dt: datetime object (naive or aware)
        tz_name: Timezone to assume if dt is naive

    Returns:
        UTC aware datetime

    Examples:
        >>> from datetime import datetime
        >>> naive = datetime(2025, 11, 26, 15, 0)
        >>> utc = normalize_to_utc(naive, "Europe/Moscow")
        >>> utc.tzinfo
        datetime.timezone.utc
    """
    # Ensure aware first
    aware_dt = ensure_aware(dt, tz_name)

    # Convert to UTC
    return aware_dt.astimezone(timezone.utc)


def to_local_time(dt: datetime, tz_name: str) -> datetime:
    """
    Convert UTC datetime to local timezone.

    Args:
        dt: datetime object (should be aware, will be made aware if not)
        tz_name: Target timezone name

    Returns:
        Datetime in target timezone

    Examples:
        >>> from datetime import datetime, timezone
        >>> utc_dt = datetime(2025, 11, 26, 12, 0, tzinfo=timezone.utc)
        >>> moscow_dt = to_local_time(utc_dt, "Europe/Moscow")
        >>> moscow_dt.hour
        15  # Moscow is UTC+3
    """
    # Ensure datetime is aware
    aware_dt = ensure_aware(dt)

    # Parse target timezone
    local_tz = parse_timezone(tz_name)

    # Convert
    return aware_dt.astimezone(local_tz)


def format_for_ui(
    dt: datetime,
    tz_name: str,
    format_str: str = "%Y-%m-%d %H:%M",
    show_tz: bool = False
) -> str:
    """
    Format datetime for UI in specified timezone.

    Args:
        dt: datetime object (naive or aware)
        tz_name: Target timezone for display
        format_str: strftime format string
        show_tz: If True, append timezone abbreviation

    Returns:
        Formatted string

    Examples:
        >>> from datetime import datetime, timezone
        >>> utc_dt = datetime(2025, 11, 26, 12, 0, tzinfo=timezone.utc)
        >>> format_for_ui(utc_dt, "Europe/Moscow")
        '2025-11-26 15:00'
        >>> format_for_ui(utc_dt, "Europe/Moscow", show_tz=True)
        '2025-11-26 15:00 MSK'
    """
    local_dt = to_local_time(dt, tz_name)
    formatted = local_dt.strftime(format_str)

    if show_tz:
        tz_abbr = local_dt.tzname()
        formatted = f"{formatted} {tz_abbr}"

    return formatted


def get_offset_minutes(tz_name: str, dt: Optional[datetime] = None) -> int:
    """
    Get UTC offset in minutes for a timezone at given datetime.

    Args:
        tz_name: Timezone name
        dt: Datetime to check (default: now). Needed for DST handling.

    Returns:
        Offset in minutes (positive for east of UTC)

    Examples:
        >>> get_offset_minutes("Europe/Moscow")
        180  # UTC+3
        >>> get_offset_minutes("America/New_York")  # Depends on DST
        -300  # UTC-5 (winter) or -240 (summer)
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = ensure_aware(dt)

    tz = parse_timezone(tz_name)
    localized = dt.astimezone(tz)
    offset = localized.utcoffset()

    if offset is None:
        return 0

    return int(offset.total_seconds() / 60)


def is_same_moment(dt1: datetime, dt2: datetime) -> bool:
    """
    Check if two datetimes represent the same moment in time.

    Handles timezone differences correctly.

    Args:
        dt1: First datetime
        dt2: Second datetime

    Returns:
        True if same moment

    Examples:
        >>> from datetime import datetime, timezone
        >>> utc = datetime(2025, 11, 26, 12, 0, tzinfo=timezone.utc)
        >>> moscow = datetime(2025, 11, 26, 15, 0, tzinfo=ZoneInfo("Europe/Moscow"))
        >>> is_same_moment(utc, moscow)
        True
    """
    utc1 = normalize_to_utc(dt1)
    utc2 = normalize_to_utc(dt2)
    return utc1 == utc2


def datetime_range_overlap(
    start1: datetime,
    end1: datetime,
    start2: datetime,
    end2: datetime
) -> bool:
    """
    Check if two datetime ranges overlap.

    All datetimes are normalized to UTC before comparison.

    Args:
        start1: Start of first range
        end1: End of first range
        start2: Start of second range
        end2: End of second range

    Returns:
        True if ranges overlap

    Examples:
        >>> from datetime import datetime, timezone, timedelta
        >>> now = datetime.now(timezone.utc)
        >>> datetime_range_overlap(
        ...     now, now + timedelta(hours=1),
        ...     now + timedelta(minutes=30), now + timedelta(hours=2)
        ... )
        True
    """
    # Normalize all to UTC
    start1_utc = normalize_to_utc(start1)
    end1_utc = normalize_to_utc(end1)
    start2_utc = normalize_to_utc(start2)
    end2_utc = normalize_to_utc(end2)

    # Check overlap: start1 < end2 AND start2 < end1
    return start1_utc < end2_utc and start2_utc < end1_utc
