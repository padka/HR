from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Tuple
from zoneinfo import ZoneInfo

import math

from backend.domain.models import SlotStatus
from backend.core.settings import get_settings
from backend.core.time_utils import local_to_utc


DEFAULT_TZ = get_settings().timezone or "Europe/Moscow"


def safe_zone(tz_str: Optional[str]) -> ZoneInfo:
    """Return ZoneInfo, falling back to Europe/Moscow."""
    try:
        return ZoneInfo(tz_str or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


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


STATUS_FILTERS = {"FREE", "PENDING", "BOOKED", "CONFIRMED_BY_CANDIDATE"}


def status_filter(value: Optional[str]) -> Optional[str]:
    candidate = (value or "").strip().upper() or None
    if candidate in STATUS_FILTERS:
        return candidate
    return None


def status_to_db(value: str):
    enum_candidate = getattr(SlotStatus, value, None)
    return enum_candidate if enum_candidate is not None else value


def parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
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
    try:
        return local_to_utc(dt_local, recruiter_tz or DEFAULT_TZ)
    except ValueError:
        return None


def render_or_empty(value: Optional[Any], placeholder: str = "нет данных") -> str:
    if value is None:
        return placeholder
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or placeholder
    if value == "":
        return placeholder
    return str(value)
