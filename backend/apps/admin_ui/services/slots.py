from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.utils import paginate, recruiter_time_to_utc, norm_status, status_to_db
from backend.core.db import async_session
from backend.domain.models import Recruiter, Slot, SlotStatus

__all__ = [
    "list_slots",
    "recruiters_for_slot_form",
    "create_slot",
    "api_slots_payload",
]


async def list_slots(
    recruiter_id: Optional[int],
    status: Optional[str],
    page: int,
    per_page: int,
) -> Dict[str, object]:
    async with async_session() as session:
        base = select(Slot)
        if recruiter_id is not None:
            base = base.where(Slot.recruiter_id == recruiter_id)
        if status:
            base = base.where(Slot.status == status_to_db(status))

        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        pages_total, page, offset = paginate(total, page, per_page)

        query = (
            base.options(selectinload(Slot.recruiter))
            .order_by(Slot.start_utc.desc())
            .offset(offset)
            .limit(per_page)
        )
        items = (await session.scalars(query)).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "pages_total": pages_total,
    }


async def recruiters_for_slot_form() -> List[Recruiter]:
    inspector = sa_inspect(Recruiter)
    has_active = "active" in getattr(inspector, "columns", {})
    query = select(Recruiter).order_by(Recruiter.name.asc())
    if has_active:
        query = query.where(getattr(Recruiter, "active") == True)  # noqa: E712
    async with async_session() as session:
        return (await session.scalars(query)).all()


async def create_slot(recruiter_id: int, date: str, time: str) -> bool:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return False
        dt_utc = recruiter_time_to_utc(date, time, getattr(recruiter, "tz", None))
        if not dt_utc:
            return False
        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value
        session.add(Slot(recruiter_id=recruiter_id, start_utc=dt_utc, status=status_free))
        await session.commit()
        return True


async def api_slots_payload(
    recruiter_id: Optional[int],
    status: Optional[str],
    limit: int,
) -> List[Dict[str, object]]:
    async with async_session() as session:
        query = select(Slot).options(selectinload(Slot.recruiter)).order_by(Slot.start_utc.asc())
        if recruiter_id is not None:
            query = query.where(Slot.recruiter_id == recruiter_id)
        if status:
            query = query.where(Slot.status == status_to_db(status))
        if limit:
            query = query.limit(max(1, min(500, limit)))
        slots = (await session.scalars(query)).all()
    return [
        {
            "id": sl.id,
            "recruiter_id": sl.recruiter_id,
            "recruiter_name": sl.recruiter.name if sl.recruiter else None,
            "start_utc": sl.start_utc.isoformat(),
            "status": norm_status(sl.status),
            "candidate_fio": getattr(sl, "candidate_fio", None),
            "candidate_tg_id": getattr(sl, "candidate_tg_id", None),
        }
        for sl in slots
    ]
