from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import math

from backend.core.timezone import (
    DEFAULT_TIMEZONE,
    ensure_timezone as _ensure_timezone,
    local_naive_to_utc as _local_naive_to_utc,
    safe_zone as _safe_zone,
    utc_to_local_naive as _utc_to_local_naive,
    validate_timezone_name,
)
from backend.domain.models import SlotStatus

try:  # pragma: no cover - FastAPI may not be installed in some test environments
    from fastapi.params import Param as _FastAPIParam
except Exception:  # pragma: no cover - fall back when FastAPI is unavailable
    _FastAPIParam = None  # type: ignore[assignment]


DEFAULT_TZ = DEFAULT_TIMEZONE


def safe_zone(tz_str: Optional[str]) -> ZoneInfo:
    return _safe_zone(tz_str)


def ensure_timezone(tz_str: Optional[str]) -> ZoneInfo:
    return _ensure_timezone(tz_str)


def local_naive_to_utc(local_dt: datetime, tz_str: str) -> datetime:
    return _local_naive_to_utc(local_dt, tz_str)


def utc_to_local_naive(utc_dt: datetime, tz_str: str) -> datetime:
    return _utc_to_local_naive(utc_dt, tz_str)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_local(dt_utc: datetime, tz_str: str) -> str:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    local = dt_utc.astimezone(safe_zone(tz_str))
    return local.strftime("%d.%m %H:%M")


def fmt_utc(dt_utc: datetime) -> str:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(timezone.utc).strftime("%d.%m %H:%M")


def format_optional_local(
    dt: Optional[datetime],
    tz: Optional[str],
    fmt: str = "%d.%m.%Y %H:%M",
) -> Optional[str]:
    """Format ``dt`` for the provided ``tz`` if both are present."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    tz_name = tz or DEFAULT_TZ
    try:
        local = dt.astimezone(safe_zone(tz_name))
    except Exception:
        local = dt.astimezone(ZoneInfo(DEFAULT_TZ))
    return local.strftime(fmt)


def norm_status(st) -> Optional[str]:
    if st is None:
        return None
    raw_value = st.value if hasattr(st, "value") else st
    return str(raw_value).upper()


STATUS_FILTERS = {"FREE", "PENDING", "BOOKED", "CONFIRMED_BY_CANDIDATE", "CANCELED"}


def status_filter(value: Optional[str]) -> Optional[str]:
    candidate = (value or "").strip().upper() or None
    if candidate in STATUS_FILTERS:
        return candidate
    return None


def status_to_db(value: str):
    enum_candidate = getattr(SlotStatus, value, None)
    if isinstance(enum_candidate, SlotStatus):
        return enum_candidate.value
    return enum_candidate if enum_candidate is not None else value


def status_filters(values: Optional[Iterable[str]]) -> list[str]:
    """Normalize a collection of status query values."""

    if not values:
        return []
    normalized: list[str] = []
    for raw in values:
        if raw is None:
            continue
        if isinstance(raw, str):
            chunks = [segment.strip() for segment in raw.split(",")]
        else:
            chunks = [str(raw).strip()]
        for chunk in chunks:
            if not chunk:
                continue
            upper = chunk.upper()
            if upper in STATUS_FILTERS and upper not in normalized:
                normalized.append(upper)
    return normalized


def ensure_sequence(items: Optional[Iterable[str]]) -> Sequence[str]:
    if not items:
        return ()
    return tuple(str(item).strip() for item in items if str(item).strip())


def parse_optional_int(value: Optional[str]) -> Optional[int]:
    if _FastAPIParam is not None and isinstance(value, _FastAPIParam):
        value = value.default  # type: ignore[assignment]
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def paginate(total: int, page: int, per_page: int) -> Tuple[int, int, int]:
    per_page = max(1, min(100, per_page or 20))
    pages_total = max(1, math.ceil(total / per_page)) if total else 1
    page = max(1, min(page or 1, pages_total))
    offset = (page - 1) * per_page
    return pages_total, page, offset


def recruiter_time_to_utc(date: str, time: str, recruiter_tz: Optional[str]) -> Optional[datetime]:
    try:
        dt_local = datetime.fromisoformat(f"{date}T{time}")
    except ValueError:
        return None
    dt_local = dt_local.replace(tzinfo=safe_zone(recruiter_tz))
    return dt_local.astimezone(timezone.utc)


def initials(name: Optional[str]) -> str:
    """Return uppercased initials for recruiter card avatars."""
    if not name:
        return "?"
    cleaned = name.replace("-", " ")
    parts = [segment for segment in cleaned.split() if segment]
    if not parts:
        return "?"
    if len(parts) == 1:
        letters = [char for char in parts[0] if char.isalpha()]
        if not letters:
            return parts[0][:2].upper()
        return "".join(letters[:2]).upper()
    letters = [part[0] for part in parts if part and part[0].isalpha()]
    return "".join(letters[:2]).upper() or "?"
