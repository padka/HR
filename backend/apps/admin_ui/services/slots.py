from __future__ import annotations

from datetime import date as date_type, datetime, time as time_type, timedelta
from typing import Dict, List, Optional, Tuple

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
    "bulk_create_slots",
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


async def bulk_create_slots(
    recruiter_id: int,
    start_date: str,
    end_date: str,
    start_time: str,
    end_time: str,
    break_start: str,
    break_end: str,
    step_min: int,
    include_weekends: bool,
    use_break: bool,
) -> Tuple[int, Optional[str]]:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return 0, "Рекрутёр не найден"

        try:
            start = date_type.fromisoformat(start_date)
            end = date_type.fromisoformat(end_date)
        except ValueError:
            return 0, "Некорректные даты"
        if end < start:
            return 0, "Дата окончания раньше даты начала"

        try:
            window_start = time_type.fromisoformat(start_time)
            window_end = time_type.fromisoformat(end_time)
            pause_start = time_type.fromisoformat(break_start)
            pause_end = time_type.fromisoformat(break_end)
        except ValueError:
            return 0, "Некорректное время"

        if window_end <= window_start:
            return 0, "Время окончания должно быть позже времени начала"
        if step_min <= 0:
            return 0, "Шаг должен быть положительным"

        if use_break and pause_end <= pause_start:
            return 0, "Время окончания перерыва должно быть позже его начала"

        start_minutes = window_start.hour * 60 + window_start.minute
        end_minutes = window_end.hour * 60 + window_end.minute
        break_start_minutes = pause_start.hour * 60 + pause_start.minute
        break_end_minutes = pause_end.hour * 60 + pause_end.minute

        tz = getattr(recruiter, "tz", None)

        planned: List[datetime] = []
        planned_set = set()
        current_date = start
        while current_date <= end:
            if include_weekends or current_date.weekday() < 5:
                current_minutes = start_minutes
                while current_minutes < end_minutes:
                    if (
                        use_break
                        and break_start_minutes < break_end_minutes
                        and break_start_minutes <= current_minutes < break_end_minutes
                    ):
                        current_minutes += step_min
                        continue

                    hours, minutes = divmod(current_minutes, 60)
                    time_str = f"{hours:02d}:{minutes:02d}"
                    dt_utc = recruiter_time_to_utc(current_date.isoformat(), time_str, tz)
                    if not dt_utc:
                        return 0, "Не удалось преобразовать время в UTC"
                    if dt_utc not in planned_set:
                        planned_set.add(dt_utc)
                        planned.append(dt_utc)
                    current_minutes += step_min
            current_date += timedelta(days=1)

        if not planned:
            return 0, "Нет доступных слотов для создания"

        existing = set(
            await session.scalars(
                select(Slot.start_utc)
                .where(Slot.recruiter_id == recruiter_id)
                .where(Slot.start_utc.in_(planned))
            )
        )

        to_insert = [dt for dt in planned if dt not in existing]
        if not to_insert:
            return 0, None

        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value

        session.add_all(
            [
                Slot(recruiter_id=recruiter_id, start_utc=dt, status=status_free)
                for dt in to_insert
            ]
        )
        await session.commit()
        return len(to_insert), None


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
