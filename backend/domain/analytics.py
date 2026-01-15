"""Analytics events logging system.

This module provides structured event logging for tracking user actions
and system events. Events are stored in the database for later analysis.

Example events:
- slot_viewed: User viewed available slots
- slot_booked: User booked a slot
- reminder_sent_6h: Reminder sent 6 hours before meeting
- no_show_call: User didn't show up for call
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_async_session

logger = logging.getLogger(__name__)


class FunnelEvent(str, Enum):
    BOT_ENTERED = "BOT_ENTERED"
    BOT_START = "BOT_START"
    TEST1_STARTED = "TEST1_STARTED"
    TEST1_COMPLETED = "TEST1_COMPLETED"
    TEST2_STARTED = "TEST2_STARTED"
    TEST2_COMPLETED = "TEST2_COMPLETED"
    SLOT_BOOKED = "SLOT_BOOKED"
    SLOT_CONFIRMED = "SLOT_CONFIRMED"
    SHOW_UP = "SHOW_UP"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"


async def log_event(
    event_name: str,
    *,
    user_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
    city_id: Optional[int] = None,
    slot_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session: Optional[AsyncSession] = None,
) -> None:
    """Log an analytics event to the database.

    Args:
        event_name: Name of the event (e.g., 'slot_viewed', 'slot_booked')
        user_id: Telegram user ID (if applicable)
        candidate_id: Candidate ID (if applicable)
        city_id: City ID (if applicable)
        slot_id: Slot ID (if applicable)
        booking_id: Booking ID (if applicable)
        metadata: Additional event metadata (stored as JSON)
        session: Optional SQLAlchemy session (if None, creates new one)

    Example:
        await log_event(
            'slot_booked',
            user_id=12345,
            candidate_id=100,
            slot_id=500,
            metadata={'source': 'webapp', 'device': 'mobile'}
        )
    """
    if not event_name:
        logger.warning("Attempted to log event with empty event_name")
        return

    # Convert metadata to JSON string
    import json

    metadata_json = json.dumps(metadata) if metadata else None

    # Prepare SQL query
    query = text(
        """
        INSERT INTO analytics_events
            (event_name, user_id, candidate_id, city_id, slot_id, booking_id, metadata, created_at)
        VALUES
            (:event_name, :user_id, :candidate_id, :city_id, :slot_id, :booking_id, :metadata, :created_at)
        """
    )

    params = {
        "event_name": event_name,
        "user_id": user_id,
        "candidate_id": candidate_id,
        "city_id": city_id,
        "slot_id": slot_id,
        "booking_id": booking_id,
        "metadata": metadata_json,
        "created_at": datetime.now(timezone.utc),
    }

    # Use provided session or create a new one
    if session:
        await session.execute(query, params)
    else:
        async for db_session in get_async_session():
            try:
                await db_session.execute(query, params)
                await db_session.commit()
            except Exception:
                await db_session.rollback()
                logger.exception(
                    "Failed to log event %s (user_id=%s, candidate_id=%s)",
                    event_name,
                    user_id,
                    candidate_id,
                )
                raise
            finally:
                break  # Exit after first iteration


async def log_funnel_event(
    event: FunnelEvent | str,
    *,
    user_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
    city_id: Optional[int] = None,
    slot_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session: Optional[AsyncSession] = None,
) -> None:
    """Log a funnel analytics event with standardized naming."""
    event_name = event.value if isinstance(event, FunnelEvent) else str(event)
    await log_event(
        event_name,
        user_id=user_id,
        candidate_id=candidate_id,
        city_id=city_id,
        slot_id=slot_id,
        booking_id=booking_id,
        metadata=metadata,
        session=session,
    )


# Convenience functions for common events


async def log_slot_viewed(
    user_id: int,
    candidate_id: Optional[int] = None,
    city_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when user views available slots."""
    await log_event(
        "slot_viewed",
        user_id=user_id,
        candidate_id=candidate_id,
        city_id=city_id,
        metadata=metadata,
    )


async def log_slot_booked(
    user_id: int,
    candidate_id: int,
    slot_id: int,
    booking_id: int,
    city_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when user books a slot."""
    await log_funnel_event(
        FunnelEvent.SLOT_BOOKED,
        user_id=user_id,
        candidate_id=candidate_id,
        slot_id=slot_id,
        booking_id=booking_id,
        city_id=city_id,
        metadata=metadata,
    )


async def log_slot_rescheduled(
    user_id: int,
    candidate_id: int,
    old_booking_id: int,
    new_booking_id: int,
    new_slot_id: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when user reschedules a booking."""
    meta = metadata or {}
    meta["old_booking_id"] = old_booking_id
    meta["new_slot_id"] = new_slot_id

    await log_event(
        "slot_rescheduled",
        user_id=user_id,
        candidate_id=candidate_id,
        booking_id=new_booking_id,
        metadata=meta,
    )


async def log_slot_canceled(
    user_id: int,
    candidate_id: int,
    booking_id: int,
    slot_id: Optional[int] = None,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when user cancels a booking."""
    meta = metadata or {}
    if reason:
        meta["reason"] = reason

    await log_event(
        "slot_canceled",
        user_id=user_id,
        candidate_id=candidate_id,
        booking_id=booking_id,
        slot_id=slot_id,
        metadata=meta,
    )


async def log_reminder_sent(
    reminder_type: str,  # '6h', '3h', '2h'
    candidate_id: int,
    slot_id: int,
    booking_id: Optional[int] = None,
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when reminder is sent."""
    meta = metadata or {}
    meta["success"] = success

    await log_event(
        f"reminder_sent_{reminder_type}",
        candidate_id=candidate_id,
        slot_id=slot_id,
        booking_id=booking_id,
        metadata=meta,
    )


async def log_reminder_clicked(
    user_id: int,
    candidate_id: int,
    action: str,  # 'confirm', 'cancel', 'reschedule'
    booking_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when user clicks button in reminder."""
    meta = metadata or {}
    meta["action"] = action

    await log_event(
        "reminder_clicked",
        user_id=user_id,
        candidate_id=candidate_id,
        booking_id=booking_id,
        metadata=meta,
    )


async def log_no_show(
    event_type: str,  # 'call' or 'introday'
    candidate_id: int,
    slot_id: int,
    booking_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when candidate doesn't show up."""
    await log_event(
        f"no_show_{event_type}",
        candidate_id=candidate_id,
        slot_id=slot_id,
        booking_id=booking_id,
        metadata=metadata,
    )


async def log_arrived_confirmed(
    candidate_id: int,
    slot_id: int,
    booking_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when candidate arrival is confirmed."""
    await log_event(
        "arrived_confirmed",
        candidate_id=candidate_id,
        slot_id=slot_id,
        booking_id=booking_id,
        metadata=metadata,
    )


async def log_calendar_downloaded(
    user_id: int,
    candidate_id: int,
    booking_id: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when user downloads calendar .ics file."""
    await log_event(
        "calendar_downloaded",
        user_id=user_id,
        candidate_id=candidate_id,
        booking_id=booking_id,
        metadata=metadata,
    )


async def log_map_opened(
    user_id: int,
    candidate_id: int,
    city_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log when user opens map/address."""
    await log_event(
        "map_opened",
        user_id=user_id,
        candidate_id=candidate_id,
        city_id=city_id,
        metadata=metadata,
    )


__all__ = [
    "FunnelEvent",
    "log_funnel_event",
    "log_event",
    "log_slot_viewed",
    "log_slot_booked",
    "log_slot_rescheduled",
    "log_slot_canceled",
    "log_reminder_sent",
    "log_reminder_clicked",
    "log_no_show",
    "log_arrived_confirmed",
    "log_calendar_downloaded",
    "log_map_opened",
]
