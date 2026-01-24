from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.utils import (
    DEFAULT_TZ,
    local_naive_to_utc,
    norm_status,
    paginate,
    status_to_db,
    validate_timezone_name,
)
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus

try:  # pragma: no cover - optional dependency during tests
    from backend.apps.bot.reminders import get_reminder_service
except Exception:  # pragma: no cover - safe fallback when bot package unavailable
    get_reminder_service = None  # type: ignore[assignment]


async def list_slots(
    recruiter_id: Optional[int],
    status: Optional[str],
    page: int,
    per_page: int,
    *,
    city_id: Optional[int] = None,
) -> Dict[str, object]:
    async with async_session() as session:
        filtered = select(Slot)
        if recruiter_id is not None:
            filtered = filtered.where(Slot.recruiter_id == recruiter_id)
        if status:
            filtered = filtered.where(Slot.status == status_to_db(status))
        if city_id is not None:
            filtered = filtered.where(Slot.city_id == city_id)

        subquery = filtered.subquery()
        total = await session.scalar(select(func.count()).select_from(subquery)) or 0

        status_rows = (
            await session.execute(
                select(subquery.c.status, func.count())
                .select_from(subquery)
                .group_by(subquery.c.status)
            )
        ).all()

        aggregated: Dict[str, int] = {}
        for raw_status, count in status_rows:
            aggregated[norm_status(raw_status)] = int(count or 0)
        aggregated.setdefault("CONFIRMED_BY_CANDIDATE", 0)

        pages_total, page, offset = paginate(total, page, per_page)

        query = (
            filtered.options(selectinload(Slot.recruiter), selectinload(Slot.city))
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
        "status_counts": aggregated,
    }


async def recruiters_for_slot_form() -> List[Dict[str, object]]:
    inspector = sa_inspect(Recruiter)
    has_active = "active" in getattr(inspector, "columns", {})
    query = select(Recruiter).order_by(Recruiter.name.asc())
    if has_active:
        query = query.where(getattr(Recruiter, "active") == True)  # noqa: E712
    async with async_session() as session:
        recs = (await session.scalars(query)).all()
        if not recs:
            return []

        rec_ids = [rec.id for rec in recs]
        city_rows = (
            await session.scalars(
                select(City)
                .where(City.responsible_recruiter_id.in_(rec_ids))
                .order_by(City.name.asc())
            )
        ).all()

        city_map: Dict[int, List[City]] = {}
        for city in city_rows:
            if city.responsible_recruiter_id is None:
                continue
            city_map.setdefault(city.responsible_recruiter_id, []).append(city)

    return [{"rec": rec, "cities": city_map.get(rec.id, [])} for rec in recs]


async def create_slot(
    recruiter_id: int,
    date: str,
    time: str,
    *,
    city_id: int,
) -> Tuple[bool, Optional[Slot]]:
    try:
        local_dt = datetime.fromisoformat(f"{date}T{time}")
    except ValueError:
        return False, None

    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return False, None
        city = await session.get(City, city_id)
        if not city or city.responsible_recruiter_id != recruiter_id:
            return False, None
        try:
            tz_name = validate_timezone_name(city.tz)
        except ValueError:
            return False, None

        dt_utc = local_naive_to_utc(local_dt, tz_name)
        slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            start_utc=dt_utc,
            status=SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        return True, slot


async def delete_slot(
    slot_id: int, *, force: bool = False, principal=None
) -> Tuple[bool, Optional[str]]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if not slot:
            return False, "Слот не найден"
        if principal and getattr(principal, "type", None) == "recruiter":
            if slot.recruiter_id != getattr(principal, "id", None):
                return False, "Слот не найден"

        status = norm_status(slot.status)
        if not force and status not in {"FREE", "PENDING"}:
            return False, f"Нельзя удалить слот со статусом {status or 'UNKNOWN'}"

        await session.delete(slot)
        await session.commit()

    if callable(get_reminder_service):
        try:
            await get_reminder_service().cancel_for_slot(slot_id)
        except RuntimeError:
            pass

    return True, None


async def delete_all_slots(*, force: bool = False, principal=None) -> Tuple[int, int]:
    principal_id = getattr(principal, "id", None)
    principal_type = getattr(principal, "type", None)
    async with async_session() as session:
        base_query = select(Slot.id)
        if principal_type == "recruiter":
            base_query = base_query.where(Slot.recruiter_id == principal_id)

        total_before = await session.scalar(select(func.count()).select_from(base_query.subquery())) or 0
        if total_before == 0:
            return 0, 0

        slot_ids: List[int] = []

        if force:
            result = await session.execute(base_query)
            slot_ids = [row[0] for row in result]
            if slot_ids:
                await session.execute(delete(Slot).where(Slot.id.in_(slot_ids)))
                await session.commit()
            remaining_after = 0
        else:
            allowed_statuses = {
                status_to_db("FREE"),
                status_to_db("PENDING"),
            }
            result = await session.execute(
                base_query.where(Slot.status.in_(allowed_statuses))
            )
            slot_ids = [row[0] for row in result]
            if not slot_ids:
                return 0, total_before
            await session.execute(delete(Slot).where(Slot.id.in_(slot_ids)))
            await session.commit()
            remaining_after = (
                await session.scalar(select(func.count()).select_from(base_query.subquery())) or 0
            )

    if callable(get_reminder_service):
        for sid in slot_ids:
            try:
                await get_reminder_service().cancel_for_slot(sid)
            except RuntimeError:
                break

    deleted = total_before - remaining_after
    return deleted, remaining_after


def _ensure_utc(dt: datetime) -> datetime:
    """Attach UTC tzinfo when database returns naive datetimes (SQLite)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _slot_local_time(slot: Slot) -> str:
    """Return ISO datetime string in slot timezone (fallback to default TZ)."""
    start = _ensure_utc(slot.start_utc)
    tz_label = getattr(slot, "tz_name", None) or (slot.city.tz if getattr(slot, "city", None) else DEFAULT_TZ)
    try:
        zone = ZoneInfo(tz_label)
    except Exception:
        zone = ZoneInfo(DEFAULT_TZ)
    return start.astimezone(zone).isoformat()


async def api_slots_payload(
    recruiter_id: Optional[int],
    status: Optional[str],
    limit: int,
) -> List[Dict[str, object]]:
    async with async_session() as session:
        query = (
            select(Slot)
            .options(selectinload(Slot.recruiter))
            .order_by(Slot.start_utc.asc())
        )
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
            "start_utc": _ensure_utc(sl.start_utc).isoformat(),
            "status": norm_status(sl.status),
            "candidate_fio": getattr(sl, "candidate_fio", None),
            "candidate_tg_id": getattr(sl, "candidate_tg_id", None),
            "tz_name": getattr(sl, "tz_name", None) or (sl.city.tz if getattr(sl, "city", None) else None),
            "local_time": _slot_local_time(sl),
        }
        for sl in slots
    ]
