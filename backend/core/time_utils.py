from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

from backend.core.settings import get_settings
from backend.core.timezone_utils import (
    normalize_to_utc,
    parse_timezone,
    ensure_aware as tz_ensure_aware,
)


_SETTINGS = get_settings()
_DEFAULT_TZ = (_SETTINGS.timezone or "UTC").strip() or "UTC"


def _safe_zone(tz_name: Optional[str]) -> ZoneInfo:
    """
    Return ZoneInfo for tz_name or raise ValueError if it cannot be resolved.

    DEPRECATED: Use parse_timezone from timezone_utils instead.
    """
    try:
        return parse_timezone(tz_name or _DEFAULT_TZ)
    except ValueError:
        # Fallback to UTC on error
        return ZoneInfo("UTC")


def ensure_aware_utc(dt: datetime) -> datetime:
    """
    Return a timezone-aware UTC datetime.

    This function now uses timezone_utils for consistency.
    """
    return normalize_to_utc(dt)


def local_to_utc(dt: datetime, tz_name: Optional[str]) -> datetime:
    """
    Convert a local datetime (naive or aware) to UTC.

    This function now uses timezone_utils for consistency.
    """
    return normalize_to_utc(dt, tz_name)


def parse_form_datetime(value: Union[str, datetime], tz_name: Optional[str]) -> datetime:
    """Parse form input into a UTC-aware datetime."""
    if isinstance(value, datetime):
        candidate = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("datetime value is required")
        normalized = text.replace(" ", "T")
        try:
            candidate = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("invalid datetime format") from exc
    else:
        raise TypeError("value must be datetime or ISO string")
    return local_to_utc(candidate, tz_name)


__all__ = [
    "ensure_aware_utc",
    "local_to_utc",
    "parse_form_datetime",
]
