from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import NotificationLog, OutboxNotification
from backend.domain.repositories import reset_outbox_entry, update_outbox_entry

__all__ = [
    "list_outbox_notifications",
    "list_notification_logs",
    "retry_outbox_notification",
    "cancel_outbox_notification",
]


def _normalize_filter(value: Optional[str]) -> Optional[str]:
    cleaned = (value or "").strip()
    if not cleaned or cleaned.lower() in {"all", "any", "*"}:
        return None
    return cleaned


async def list_outbox_notifications(
    *,
    after_id: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    type: Optional[str] = None,
) -> Dict[str, object]:
    status_filter = _normalize_filter(status)
    type_filter = _normalize_filter(type)
    limit_value = max(1, min(int(limit or 50), 200))
    after_value = max(int(after_id or 0), 0)

    async with async_session() as session:
        stmt = select(OutboxNotification)
        if status_filter is not None:
            stmt = stmt.where(OutboxNotification.status == status_filter)
        if type_filter is not None:
            stmt = stmt.where(OutboxNotification.type == type_filter)

        # "Tail" mode: after_id=0 returns the most recent items, which is what ops UI
        # expects on initial load. Polling uses after_id=<latest_id>.
        if after_value > 0:
            stmt = (
                stmt.where(OutboxNotification.id > after_value)
                .order_by(OutboxNotification.id.asc())
                .limit(limit_value)
            )
        else:
            stmt = stmt.order_by(OutboxNotification.id.desc()).limit(limit_value)

        rows = (await session.scalars(stmt)).all()

    if after_value == 0:
        rows = list(reversed(rows))

    items: List[Dict[str, object]] = []
    latest_id = after_value
    for row in rows:
        latest_id = max(latest_id, int(row.id))
        items.append(
            {
                "id": int(row.id),
                "type": str(row.type),
                "status": str(row.status),
                "attempts": int(row.attempts or 0),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "locked_at": row.locked_at.isoformat() if row.locked_at else None,
                "next_retry_at": row.next_retry_at.isoformat() if row.next_retry_at else None,
                "last_error": row.last_error,
                "booking_id": row.booking_id,
                "candidate_tg_id": row.candidate_tg_id,
                "recruiter_tg_id": row.recruiter_tg_id,
                "correlation_id": row.correlation_id,
            }
        )

    return {"items": items, "latest_id": latest_id}


async def list_notification_logs(
    *,
    after_id: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    type: Optional[str] = None,
    candidate_tg_id: Optional[int] = None,
    booking_id: Optional[int] = None,
) -> Dict[str, object]:
    status_filter = _normalize_filter(status)
    type_filter = _normalize_filter(type)
    limit_value = max(1, min(int(limit or 50), 200))
    after_value = max(int(after_id or 0), 0)

    async with async_session() as session:
        stmt = select(NotificationLog)
        if status_filter is not None:
            stmt = stmt.where(NotificationLog.delivery_status == status_filter)
        if type_filter is not None:
            stmt = stmt.where(NotificationLog.type == type_filter)
        if candidate_tg_id is not None:
            stmt = stmt.where(NotificationLog.candidate_tg_id == int(candidate_tg_id))
        if booking_id is not None:
            stmt = stmt.where(NotificationLog.booking_id == int(booking_id))

        if after_value > 0:
            stmt = (
                stmt.where(NotificationLog.id > after_value)
                .order_by(NotificationLog.id.asc())
                .limit(limit_value)
            )
        else:
            stmt = stmt.order_by(NotificationLog.id.desc()).limit(limit_value)

        rows = (await session.scalars(stmt)).all()

    if after_value == 0:
        rows = list(reversed(rows))

    items: List[Dict[str, object]] = []
    latest_id = after_value
    for row in rows:
        latest_id = max(latest_id, int(row.id))
        items.append(
            {
                "id": int(row.id),
                "type": str(row.type),
                "status": str(row.delivery_status),
                "attempts": int(row.attempts or 0),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "next_retry_at": row.next_retry_at.isoformat() if row.next_retry_at else None,
                "last_error": row.last_error,
                "booking_id": int(row.booking_id),
                "candidate_tg_id": row.candidate_tg_id,
                "template_key": row.template_key,
                "template_version": row.template_version,
            }
        )

    return {"items": items, "latest_id": latest_id}


async def retry_outbox_notification(outbox_id: int) -> Tuple[bool, Optional[str]]:
    async with async_session() as session:
        entry = await session.get(OutboxNotification, outbox_id)
        if entry is None:
            return False, "not_found"
        if (entry.status or "").lower() == "sent":
            return False, "already_sent"

    await reset_outbox_entry(outbox_id)
    return True, None


async def cancel_outbox_notification(outbox_id: int, *, reason: str = "cancelled_by_operator") -> Tuple[bool, Optional[str]]:
    async with async_session() as session:
        entry = await session.get(OutboxNotification, outbox_id)
        if entry is None:
            return False, "not_found"
        if (entry.status or "").lower() == "sent":
            return False, "already_sent"

    await update_outbox_entry(
        outbox_id,
        status="failed",
        next_retry_at=None,
        last_error=str(reason or "cancelled_by_operator"),
        # Preserve attempts (do not reset) so operators can see history.
        attempts=None,
        correlation_id=None,
    )
    return True, None
