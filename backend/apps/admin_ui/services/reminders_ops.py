from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import Slot, SlotReminderJob

__all__ = ["list_reminder_jobs"]


def _normalize_filter(value: Optional[str]) -> Optional[str]:
    cleaned = (value or "").strip()
    if not cleaned or cleaned.lower() in {"all", "any", "*"}:
        return None
    return cleaned


async def list_reminder_jobs(
    *,
    limit: int = 50,
    kind: Optional[str] = None,
    slot_id: Optional[int] = None,
    candidate_tg_id: Optional[int] = None,
) -> Dict[str, object]:
    limit_value = max(1, min(int(limit or 50), 200))
    kind_filter = _normalize_filter(kind)
    now_utc = datetime.now(timezone.utc)

    async with async_session() as session:
        stmt = (
            select(SlotReminderJob, Slot)
            .join(Slot, Slot.id == SlotReminderJob.slot_id)
            .where(SlotReminderJob.scheduled_at >= now_utc)
        )
        if kind_filter is not None:
            stmt = stmt.where(SlotReminderJob.kind == kind_filter)
        if slot_id is not None:
            stmt = stmt.where(SlotReminderJob.slot_id == int(slot_id))
        if candidate_tg_id is not None:
            stmt = stmt.where(Slot.candidate_tg_id == int(candidate_tg_id))

        stmt = stmt.order_by(SlotReminderJob.scheduled_at.asc(), SlotReminderJob.id.asc()).limit(limit_value)
        rows = (await session.execute(stmt)).all()

    items: List[Dict[str, object]] = []
    for job, slot in rows:
        items.append(
            {
                "id": int(job.id),
                "slot_id": int(job.slot_id),
                "kind": str(job.kind),
                "job_id": str(job.job_id),
                "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
                "slot_start_utc": slot.start_utc.isoformat() if slot.start_utc else None,
                "slot_status": str(slot.status),
                "purpose": str(getattr(slot, "purpose", "") or "interview"),
                "candidate_tg_id": slot.candidate_tg_id,
                "candidate_fio": slot.candidate_fio,
            }
        )

    return {"items": items, "now_utc": now_utc.isoformat()}

