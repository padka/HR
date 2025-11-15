from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import NotificationLog


async def notification_feed(after_id: Optional[int], limit: int = 20) -> List[dict]:
    """Return chronological notification log entries after the specified ID."""

    limit = max(1, min(limit, 200))
    stmt = (
        select(NotificationLog)
        .order_by(NotificationLog.id.desc())
        .limit(limit)
    )
    if after_id:
        stmt = stmt.where(NotificationLog.id > after_id)

    async with async_session() as session:
        rows = (await session.execute(stmt)).scalars().all()

    items: List[dict] = []
    for row in reversed(rows):
        items.append(
            {
                "id": row.id,
                "type": row.type,
                "status": row.delivery_status,
                "attempts": row.attempts,
                "last_error": row.last_error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return items


__all__ = ["notification_feed"]
