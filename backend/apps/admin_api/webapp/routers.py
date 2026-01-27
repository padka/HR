"""FastAPI routers for Telegram WebApp API.

This module provides REST API endpoints for Telegram Mini App (WebApp).
Endpoints are secured with initData validation.

Available endpoints:
- Candidate: /api/webapp/me, /slots, /booking, /reschedule, /cancel
- Recruiter: /api/webapp/recruiter/dashboard, /candidates
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_api.webapp.auth import TelegramUser, get_telegram_webapp_auth
from backend.domain import analytics
from backend.domain.models import (
    SlotStatus,
    SlotStatusTransitionError,
    enforce_slot_transition,
    DEFAULT_INTERVIEW_DURATION_MIN,
)
from backend.domain.repositories import slot_status_free_sql
from backend.core.dependencies import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webapp"])


def _safe_text(sql: str, params: tuple[str, ...]):
    """Return a bound text clause to avoid accidental string interpolation."""
    return text(sql).bindparams(*(bindparam(name) for name in params))


# ============================================================================
# Response Models
# ============================================================================


class CandidateInfo(BaseModel):
    """Candidate information response."""

    user_id: int
    full_name: str
    username: Optional[str] = None
    candidate_id: Optional[int] = None
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    status: Optional[str] = None


class SlotInfo(BaseModel):
    """Available slot information."""

    slot_id: int
    recruiter_id: int
    recruiter_name: str
    start_utc: datetime
    end_utc: datetime
    duration_minutes: int
    is_available: bool
    city_id: int


class BookingInfo(BaseModel):
    """Booking information."""

    booking_id: int
    slot_id: int
    candidate_id: int
    recruiter_name: str
    start_utc: datetime
    end_utc: datetime
    status: str
    meet_link: Optional[str] = None
    address: Optional[str] = None


class IntroDayInfo(BaseModel):
    """Intro day information."""

    intro_day_id: int
    city_id: int
    city_name: str
    date: datetime
    address: str
    contact_name: str
    contact_phone: str
    available_slots: int


# ============================================================================
# Request Models
# ============================================================================


class CreateBookingRequest(BaseModel):
    """Request to create a booking."""

    slot_id: int = Field(..., gt=0)


class RescheduleBookingRequest(BaseModel):
    """Request to reschedule a booking."""

    booking_id: int = Field(..., gt=0)
    new_slot_id: int = Field(..., gt=0)


class CancelBookingRequest(BaseModel):
    """Request to cancel a booking."""

    booking_id: int = Field(..., gt=0)
    reason: Optional[str] = Field(None, max_length=500)


# ============================================================================
# Candidate Endpoints
# ============================================================================


@router.get("/me", response_model=CandidateInfo)
async def get_me(
    user: TelegramUser = Depends(get_telegram_webapp_auth()),
    session: AsyncSession = Depends(get_async_session),
) -> CandidateInfo:
    """Get current user (candidate) information.

    Returns:
        CandidateInfo with user details and candidate status
    """
    # Query candidate info from database
    query = _safe_text(
        """
        SELECT
            u.id as candidate_id,
            ci.id as city_id,
            ci.name as city_name,
            u.candidate_status
        FROM users u
        LEFT JOIN cities ci ON LOWER(ci.name) = LOWER(u.city)
        WHERE u.telegram_id = :telegram_id
        LIMIT 1
        """,
        ("telegram_id",),
    )

    result = await session.execute(query, {"telegram_id": user.user_id})
    row = result.fetchone()

    if row:
        candidate_id, city_id, city_name, candidate_status = row
    else:
        candidate_id = None
        city_id = None
        city_name = None
        candidate_status = None

    return CandidateInfo(
        user_id=user.user_id,
        full_name=user.full_name,
        username=user.username,
        candidate_id=candidate_id,
        city_id=city_id,
        city_name=city_name,
        status=candidate_status,
    )


@router.get("/slots", response_model=List[SlotInfo])
async def get_available_slots(
    city_id: Optional[int] = Query(None, description="Filter by city ID"),
    from_date: Optional[datetime] = Query(None, description="Start date (UTC)"),
    to_date: Optional[datetime] = Query(None, description="End date (UTC)"),
    user: TelegramUser = Depends(get_telegram_webapp_auth()),
    session: AsyncSession = Depends(get_async_session),
) -> List[SlotInfo]:
    """Get available slots for booking.

    Args:
        city_id: Optional city ID filter
        from_date: Optional start date filter (defaults to now)
        to_date: Optional end date filter (defaults to +14 days)
        user: Authenticated Telegram user
        session: Database session

    Returns:
        List of available slots
    """
    # Default date range: now to +14 days
    if from_date is None:
        from_date = datetime.now(timezone.utc)
    if to_date is None:
        to_date = from_date + timedelta(days=14)

    # Log analytics event
    await analytics.log_slot_viewed(
        user_id=user.user_id,
        city_id=city_id,
        metadata={"from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
    )

    # Query available slots
    query = _safe_text(
        """
        SELECT
            s.id as slot_id,
            s.recruiter_id,
            r.name as recruiter_name,
            s.start_utc,
            s.end_utc,
            s.duration_minutes,
            s.city_id
        FROM slots s
        INNER JOIN recruiters r ON s.recruiter_id = r.id
        WHERE """
        + slot_status_free_sql("s")
        + """
            AND (s.candidate_id IS NULL AND s.candidate_tg_id IS NULL)
            AND s.start_utc >= :from_date
            AND s.start_utc <= :to_date
            AND (:city_id IS NULL OR s.city_id = :city_id)
        ORDER BY s.start_utc ASC
        LIMIT 100
        """,
        ("city_id", "from_date", "to_date"),
    )

    result = await session.execute(
        query,
        {"city_id": city_id, "from_date": from_date, "to_date": to_date},
    )

    slots = []
    for row in result:
        slot_id, recruiter_id, recruiter_name, start_utc, end_utc, duration_minutes, slot_city_id = row
        slots.append(
            SlotInfo(
                slot_id=slot_id,
                recruiter_id=recruiter_id,
                recruiter_name=recruiter_name,
                start_utc=start_utc,
                end_utc=end_utc,
                duration_minutes=duration_minutes or DEFAULT_INTERVIEW_DURATION_MIN,
                is_available=True,
                city_id=slot_city_id,
            )
        )

    return slots


@router.post("/booking", response_model=BookingInfo, status_code=status.HTTP_201_CREATED)
async def create_booking(
    request: CreateBookingRequest,
    user: TelegramUser = Depends(get_telegram_webapp_auth()),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Create a new booking.

    Args:
        request: Booking request with slot_id
        user: Authenticated Telegram user
        session: Database session

    Returns:
        Created booking information

    Raises:
        HTTPException: If slot is not available or user not found
    """
    # Get candidate_id from telegram_id
    candidate_query = _safe_text(
        """
        SELECT u.id, u.candidate_id, ci.id
        FROM users u
        LEFT JOIN cities ci ON LOWER(ci.name) = LOWER(u.city)
        WHERE u.telegram_id = :telegram_id
        LIMIT 1
        """,
        ("telegram_id",),
    )
    candidate_result = await session.execute(candidate_query, {"telegram_id": user.user_id})
    candidate_row = candidate_result.fetchone()

    if not candidate_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found. Please complete registration first.",
        )

    candidate_id, candidate_uuid, candidate_city_id = candidate_row

    # Check if slot is available
    slot_query = _safe_text(
        """
        SELECT s.id, s.recruiter_id, r.name, s.start_utc, s.end_utc, s.status, s.city_id
        FROM slots s
        INNER JOIN recruiters r ON s.recruiter_id = r.id
        WHERE s.id = :slot_id
        FOR UPDATE
        """,
        ("slot_id",),
    )
    slot_result = await session.execute(slot_query, {"slot_id": request.slot_id})
    slot_row = slot_result.fetchone()

    if not slot_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found",
        )

    slot_id, recruiter_id, recruiter_name, start_utc, end_utc, slot_status, slot_city_id = slot_row

    status_lower = (slot_status or "").lower()
    if status_lower != SlotStatus.FREE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot is already booked. Please choose another slot.",
        )

    now_utc = datetime.now(timezone.utc)

    # Validate transition to pending
    try:
        next_status = enforce_slot_transition(status_lower, SlotStatus.PENDING)
    except SlotStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    # Mark slot as booked (status-based) and attach candidate info
    effective_city_id = candidate_city_id or slot_city_id
    update_slot_query = _safe_text(
        """
        UPDATE slots
        SET status = :status_pending,
            candidate_id = :candidate_uuid,
            candidate_tg_id = :candidate_tg_id,
            candidate_city_id = :candidate_city_id,
            candidate_fio = :candidate_fio,
            purpose = 'interview',
            updated_at = :updated_at
        WHERE id = :slot_id
        """,
        (
            "status_pending",
            "candidate_uuid",
            "candidate_tg_id",
            "candidate_city_id",
            "candidate_fio",
            "updated_at",
            "slot_id",
        ),
    )
    await session.execute(
        update_slot_query,
        {
            "slot_id": slot_id,
            "status_pending": next_status,
            "candidate_uuid": candidate_uuid,
            "candidate_tg_id": user.user_id,
            "candidate_city_id": effective_city_id,
            "candidate_fio": user.full_name,
            "updated_at": now_utc,
        },
    )

    await session.commit()
    booking_id = slot_id

    # Log analytics event
    await analytics.log_slot_booked(
        user_id=user.user_id,
        candidate_id=candidate_id,
        slot_id=slot_id,
        booking_id=booking_id,
        city_id=slot_city_id,
        metadata={"source": "webapp"},
    )

    return BookingInfo(
        booking_id=booking_id,
        slot_id=slot_id,
        candidate_id=candidate_id,
        recruiter_name=recruiter_name,
        start_utc=start_utc,
        end_utc=end_utc,
        status="pending",
        meet_link=None,
        address=None,
    )


@router.post("/reschedule", response_model=BookingInfo)
async def reschedule_booking(
    request: RescheduleBookingRequest,
    user: TelegramUser = Depends(get_telegram_webapp_auth()),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Reschedule an existing booking to a new slot.

    Args:
        request: Reschedule request with booking_id and new_slot_id
        user: Authenticated Telegram user
        session: Database session

    Returns:
        Updated booking information

    Raises:
        HTTPException: If booking not found or new slot not available
    """
    # Get candidate_id
    candidate_query = _safe_text(
        """
        SELECT u.id, u.candidate_id, ci.id
        FROM users u
        LEFT JOIN cities ci ON LOWER(ci.name) = LOWER(u.city)
        WHERE u.telegram_id = :telegram_id
        LIMIT 1
        """,
        ("telegram_id",),
    )
    candidate_result = await session.execute(candidate_query, {"telegram_id": user.user_id})
    candidate_row = candidate_result.fetchone()

    if not candidate_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    candidate_id, candidate_uuid, candidate_city_id = candidate_row

    old_slot_id = request.booking_id

    # Load current status of the old slot to validate transition to FREE
    old_slot_query = _safe_text(
        """
        SELECT status FROM slots
        WHERE id = :slot_id AND candidate_tg_id = :telegram_id
        FOR UPDATE
        """,
        ("slot_id", "telegram_id"),
    )
    old_slot_result = await session.execute(
        old_slot_query,
        {"slot_id": old_slot_id, "telegram_id": user.user_id},
    )
    old_slot_row = old_slot_result.fetchone()
    if not old_slot_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or does not belong to you",
        )
    old_slot_status = old_slot_row[0]

    # Check if new slot is available
    new_slot_query = _safe_text(
        """
        SELECT s.id, s.recruiter_id, r.name, s.start_utc, s.end_utc, s.status, s.city_id
        FROM slots s
        INNER JOIN recruiters r ON s.recruiter_id = r.id
        WHERE s.id = :slot_id
        FOR UPDATE
        """,
        ("slot_id",),
    )
    new_slot_result = await session.execute(new_slot_query, {"slot_id": request.new_slot_id})
    new_slot_row = new_slot_result.fetchone()

    if not new_slot_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New slot not found")

    new_slot_id, recruiter_id, recruiter_name, start_utc, end_utc, slot_status, new_slot_city_id = new_slot_row

    status_lower = (slot_status or "").lower()
    try:
        new_status = enforce_slot_transition(status_lower, SlotStatus.PENDING)
    except SlotStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    # Validate transition for old slot before finalizing updates
    try:
        enforce_slot_transition(old_slot_status, SlotStatus.FREE)
    except SlotStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    now_utc = datetime.now(timezone.utc)

    # Free old slot
    free_old_slot_query = _safe_text(
        """
        UPDATE slots
        SET status = :status_free,
            candidate_id = NULL,
            candidate_tg_id = NULL,
            candidate_city_id = NULL,
            candidate_fio = NULL,
            purpose = 'interview',
            updated_at = :updated_at
        WHERE id = :slot_id
        """,
        ("status_free", "updated_at", "slot_id"),
    )
    await session.execute(
        free_old_slot_query,
        {"slot_id": old_slot_id, "status_free": SlotStatus.FREE, "updated_at": now_utc},
    )

    # Book new slot
    effective_city_id = candidate_city_id or new_slot_city_id
    book_new_slot_query = _safe_text(
        """
        UPDATE slots
        SET status = :status_pending,
            candidate_id = :candidate_uuid,
            candidate_tg_id = :candidate_tg_id,
            candidate_city_id = :candidate_city_id,
            candidate_fio = :candidate_fio,
            purpose = 'interview',
            updated_at = :updated_at
        WHERE id = :slot_id
        """,
        (
            "status_pending",
            "candidate_uuid",
            "candidate_tg_id",
            "candidate_city_id",
            "candidate_fio",
            "updated_at",
            "slot_id",
        ),
    )
    await session.execute(
        book_new_slot_query,
        {
            "slot_id": new_slot_id,
            "status_pending": new_status,
            "candidate_uuid": candidate_uuid,
            "candidate_tg_id": user.user_id,
            "candidate_city_id": effective_city_id,
            "candidate_fio": user.full_name,
            "updated_at": now_utc,
        },
    )

    await session.commit()

    # Log analytics event
    await analytics.log_slot_rescheduled(
        user_id=user.user_id,
        candidate_id=candidate_id,
        old_booking_id=old_slot_id,
        new_booking_id=new_slot_id,
        new_slot_id=new_slot_id,
        metadata={"old_slot_id": old_slot_id, "source": "webapp"},
    )

    return BookingInfo(
        booking_id=new_slot_id,
        slot_id=new_slot_id,
        candidate_id=candidate_id,
        recruiter_name=recruiter_name,
        start_utc=start_utc,
        end_utc=end_utc,
        status="pending",
        meet_link=None,
        address=None,
    )


@router.post("/cancel", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def cancel_booking(
    request: CancelBookingRequest,
    user: TelegramUser = Depends(get_telegram_webapp_auth()),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Cancel an existing booking.

    Args:
        request: Cancel request with booking_id and optional reason
        user: Authenticated Telegram user
        session: Database session

    Raises:
        HTTPException: If booking not found or doesn't belong to user
    """
    # Get candidate_id
    candidate_query = _safe_text(
        """
        SELECT u.id
        FROM users u
        WHERE u.telegram_id = :telegram_id
        LIMIT 1
        """,
        ("telegram_id",),
    )
    candidate_result = await session.execute(candidate_query, {"telegram_id": user.user_id})
    candidate_row = candidate_result.fetchone()

    if not candidate_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    candidate_id = candidate_row[0]

    slot_id = request.booking_id

    # Load slot status to validate transition
    slot_query = _safe_text(
        """
        SELECT status FROM slots
        WHERE id = :slot_id AND candidate_tg_id = :telegram_id
        FOR UPDATE
        """,
        ("slot_id", "telegram_id"),
    )
    slot_result = await session.execute(
        slot_query, {"slot_id": slot_id, "telegram_id": user.user_id}
    )
    slot_row = slot_result.fetchone()
    if not slot_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or does not belong to you",
        )
    slot_status = slot_row[0]

    try:
        enforce_slot_transition(slot_status, SlotStatus.FREE)
    except SlotStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    now_utc = datetime.now(timezone.utc)

    # Free slot
    free_slot_query = _safe_text(
        """
        UPDATE slots
        SET status = :status_free,
            candidate_id = NULL,
            candidate_tg_id = NULL,
            candidate_city_id = NULL,
            candidate_fio = NULL,
            purpose = 'interview',
            updated_at = :updated_at
        WHERE id = :slot_id
        """,
        ("status_free", "updated_at", "slot_id"),
    )
    await session.execute(
        free_slot_query, {"slot_id": slot_id, "status_free": SlotStatus.FREE, "updated_at": now_utc}
    )

    await session.commit()

    # Log analytics event
    await analytics.log_slot_canceled(
        user_id=user.user_id,
        candidate_id=candidate_id,
        booking_id=slot_id,
        slot_id=slot_id,
        reason=request.reason,
        metadata={"source": "webapp"},
    )


@router.get("/intro_day", response_model=IntroDayInfo)
async def get_intro_day_info(
    city_id: int = Query(..., description="City ID"),
    user: TelegramUser = Depends(get_telegram_webapp_auth()),
    session: AsyncSession = Depends(get_async_session),
) -> IntroDayInfo:
    """Get information about upcoming intro day for a city.

    Args:
        city_id: City ID
        user: Authenticated Telegram user
        session: Database session

    Returns:
        Intro day information

    Raises:
        HTTPException: If no upcoming intro day found
    """
    query = _safe_text(
        """
        SELECT
            id.id as intro_day_id,
            id.city_id,
            c.name as city_name,
            id.date,
            id.address,
            id.contact_name,
            id.contact_phone,
            id.available_slots
        FROM intro_days id
        INNER JOIN cities c ON id.city_id = c.id
        WHERE id.city_id = :city_id
            AND id.date >= :now
        ORDER BY id.date ASC
        LIMIT 1
        """,
        ("city_id", "now"),
    )

    result = await session.execute(query, {"city_id": city_id, "now": datetime.now(timezone.utc)})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No upcoming intro day found for this city",
        )

    intro_day_id, city_id, city_name, date, address, contact_name, contact_phone, available_slots = row

    return IntroDayInfo(
        intro_day_id=intro_day_id,
        city_id=city_id,
        city_name=city_name,
        date=date,
        address=address,
        contact_name=contact_name,
        contact_phone=contact_phone,
        available_slots=available_slots or 0,
    )


__all__ = ["router"]
