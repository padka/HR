"""Centralised timezone utilities used across the backend."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "DEFAULT_TIMEZONE",
    "InvalidTimezoneError",
    "safe_zone",
    "validate_timezone_name",
    "ensure_timezone",
    "local_naive_to_utc",
    "utc_to_local_naive",
]


DEFAULT_TIMEZONE = "Europe/Moscow"


class InvalidTimezoneError(ValueError):
    """Raised when a provided timezone identifier cannot be resolved."""


def safe_zone(tz_name: Optional[str]) -> ZoneInfo:
    """Return a ZoneInfo instance, falling back to DEFAULT_TIMEZONE."""

    candidate = (tz_name or "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(candidate)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def validate_timezone_name(tz_name: Optional[str]) -> str:
    """Validate ``tz_name`` and return it if resolvable."""

    candidate = (tz_name or "").strip()
    if not candidate:
        raise InvalidTimezoneError("Timezone must be provided")
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise InvalidTimezoneError(f"Invalid timezone: {candidate}") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise InvalidTimezoneError(f"Invalid timezone: {candidate}") from exc
    return candidate


def ensure_timezone(tz_name: Optional[str]) -> ZoneInfo:
    """Return a ZoneInfo object or raise InvalidTimezoneError."""

    return ZoneInfo(validate_timezone_name(tz_name))


def local_naive_to_utc(local_dt: datetime, tz_name: str) -> datetime:
    zone = ensure_timezone(tz_name)
    if local_dt.tzinfo is None:
        localized = local_dt.replace(tzinfo=zone)
    else:
        localized = local_dt.astimezone(zone)
    return localized.astimezone(timezone.utc)


def utc_to_local_naive(utc_dt: datetime, tz_name: str) -> datetime:
    zone = ensure_timezone(tz_name)
    aware = utc_dt if utc_dt.tzinfo is not None else utc_dt.replace(tzinfo=timezone.utc)
    local = aware.astimezone(zone)
    return local.replace(tzinfo=None)
