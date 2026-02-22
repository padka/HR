"""Cache key builders for admin_ui hot endpoints.

Rules:
- Never include PII (names, phone numbers, free-text).
- Always include scope for personalized responses (principal type/id).
- Normalize unordered params (e.g. status lists) to avoid accidental cache misses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import Iterable, Optional

from backend.apps.admin_ui.security import Principal


@dataclass(frozen=True)
class Key:
    value: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


def _principal_scope(principal: Principal | None) -> str:
    if principal is None:
        return "anon"
    return f"{principal.type}:{principal.id}"


def dashboard_counts(*, principal: Principal | None) -> Key:
    return Key(f"dashboard:counts:v1:{_principal_scope(principal)}")


def dashboard_incoming(*, principal: Principal | None, limit: int) -> Key:
    return Key(f"dashboard:incoming:v1:{_principal_scope(principal)}:{int(limit)}")


def profile_payload(*, principal: Principal) -> Key:
    return Key(f"profile:payload:v1:{principal.type}:{principal.id}")


def calendar_events(
    *,
    start_date: date_type,
    end_date: date_type,
    recruiter_id: Optional[int],
    city_id: Optional[int],
    statuses: Optional[Iterable[str]],
    tz_name: str,
    include_canceled: bool,
) -> Key:
    statuses_key = ",".join(
        sorted((s or "").strip().lower() for s in (statuses or []) if (s or "").strip())
    )
    return Key(
        "calendar:events:v1:"
        f"{start_date.isoformat()}:{end_date.isoformat()}:"
        f"r{recruiter_id or 'all'}:c{city_id or 'all'}:"
        f"s{statuses_key or 'all'}:"
        f"tz{tz_name}:x{int(bool(include_canceled))}"
    )

