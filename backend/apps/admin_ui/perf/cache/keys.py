"""Cache key builders for admin_ui hot endpoints.

Rules:
- Never include PII (names, phone numbers, free-text).
- Always include scope for personalized responses (principal type/id).
- Normalize unordered params (e.g. status lists) to avoid accidental cache misses.
"""

from __future__ import annotations

from hashlib import sha1
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


def dashboard_incoming(
    *,
    principal: Principal | None,
    limit: int | None = None,
    page: int = 1,
    page_size: int | None = None,
    city_id: int | None = None,
    status: str = "all",
    owner: str = "all",
    waiting: str = "all",
    ai_level: str = "all",
    sort: str = "priority",
    search: str | None = None,
) -> Key:
    normalized_page_size = int(page_size or limit or 100)
    normalized_search = (search or "").strip().lower()
    search_key = "q0"
    if normalized_search:
        search_key = f"q{sha1(normalized_search.encode('utf-8')).hexdigest()[:12]}"
    return Key(
        "dashboard:incoming:v2:"
        f"{_principal_scope(principal)}:"
        f"p{int(page)}:ps{normalized_page_size}:"
        f"c{city_id or 'all'}:"
        f"s{(status or 'all').strip().lower()}:"
        f"o{(owner or 'all').strip().lower()}:"
        f"w{(waiting or 'all').strip().lower()}:"
        f"ai{(ai_level or 'all').strip().lower()}:"
        f"sort{(sort or 'priority').strip().lower()}:"
        f"{search_key}"
    )


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
    include_tasks: bool = False,
) -> Key:
    statuses_key = ",".join(
        sorted((s or "").strip().lower() for s in (statuses or []) if (s or "").strip())
    )
    return Key(
        "calendar:events:v1:"
        f"{start_date.isoformat()}:{end_date.isoformat()}:"
        f"r{recruiter_id or 'all'}:c{city_id or 'all'}:"
        f"s{statuses_key or 'all'}:"
        f"tz{tz_name}:x{int(bool(include_canceled))}:t{int(bool(include_tasks))}"
    )
