"""Domain-level slot operations extracted from bot services.

This module provides slot reservation/approval/rejection/confirmation helpers
that are independent of Telegram or HTTP layers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.core.time_utils import ensure_aware_utc
from backend.domain.repositories import (
    ReservationResult,
    approve_slot as _approve_slot,
    confirm_slot_by_candidate as _confirm_slot_by_candidate,
    get_free_slots_by_recruiter as _get_free_slots_by_recruiter,
    get_slot as _get_slot,
    city_has_available_slots as _city_has_available_slots,
    reject_slot as _reject_slot,
    reserve_slot as _reserve_slot,
)

__all__ = [
    "reserve_slot",
    "approve_slot",
    "reject_slot",
    "confirm_slot_by_candidate",
    "get_slot",
    "get_free_slots_by_recruiter",
    "city_has_available_slots",
    "ReservationResult",
    "ensure_slot_not_in_past",
    "SlotValidationError",
]


class SlotValidationError(Exception):
    """Raised when slot validation fails."""


def ensure_slot_not_in_past(
    start_utc: datetime,
    *,
    slot_tz: Optional[str] = None,
    allow_past: bool = False,
    grace_minutes: int = 0,
) -> None:
    """Validate that a slot start is not in the past.

    All validation is done in UTC to ensure correctness across timezones.
    The slot_tz parameter is kept for backwards compatibility but not used.
    """
    normalized_start = ensure_aware_utc(start_utc)
    if allow_past:
        return

    now_utc = datetime.now(timezone.utc)
    threshold = now_utc - timedelta(minutes=max(grace_minutes, 0))

    if normalized_start <= threshold:
        raise SlotValidationError("Slot start time is in the past")


async def reserve_slot(
    slot_id: int,
    candidate_tg_id: Optional[int],
    candidate_fio: str,
    candidate_tz: str,
    *,
    candidate_id: Optional[str] = None,
    candidate_city_id: Optional[int] = None,
    candidate_username: Optional[str] = None,
    purpose: str = "interview",
    expected_recruiter_id: Optional[int] = None,
    expected_city_id: Optional[int] = None,
    allow_candidate_replace: bool = False,
) -> ReservationResult:
    """Thin wrapper to keep bot layer decoupled from persistence layer."""
    return await _reserve_slot(
        slot_id,
        candidate_tg_id,
        candidate_fio,
        candidate_tz,
        candidate_id=candidate_id,
        candidate_city_id=candidate_city_id,
        candidate_username=candidate_username,
        purpose=purpose,
        expected_recruiter_id=expected_recruiter_id,
        expected_city_id=expected_city_id,
        allow_candidate_replace=allow_candidate_replace,
    )


async def approve_slot(slot_id: int):
    return await _approve_slot(slot_id)


async def reject_slot(slot_id: int):
    return await _reject_slot(slot_id)


async def confirm_slot_by_candidate(slot_id: int):
    return await _confirm_slot_by_candidate(slot_id)


async def get_slot(slot_id: int):
    return await _get_slot(slot_id)


async def get_free_slots_by_recruiter(recruiter_id: int, *, city_id: Optional[int] = None):
    return await _get_free_slots_by_recruiter(recruiter_id, city_id=city_id)


async def city_has_available_slots(city_id: int) -> bool:
    return await _city_has_available_slots(city_id)
