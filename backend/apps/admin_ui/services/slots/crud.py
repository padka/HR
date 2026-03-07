from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, or_, literal
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
from backend.domain.models import (
    City,
    Recruiter,
    Slot,
    SlotAssignment,
    SlotAssignmentStatus,
    SlotStatus,
    recruiter_city_association,
)
from backend.domain.candidates.models import User

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
        if not city:
            return False, None
        # Check M2M recruiter_cities association (not just responsible_recruiter_id)
        m2m = await session.scalar(
            select(recruiter_city_association.c.city_id).where(
                recruiter_city_association.c.recruiter_id == recruiter_id,
                recruiter_city_association.c.city_id == city_id,
            ).limit(1)
        )
        if m2m is None and city.responsible_recruiter_id != recruiter_id:
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


def _slot_local_time(slot: Slot, tz_override: Optional[str] = None) -> str:
    """Return ISO datetime string in provided timezone (fallback to slot/default TZ)."""
    start = _ensure_utc(slot.start_utc)
    tz_label = (
        tz_override
        or getattr(slot, "tz_name", None)
        or (slot.city.tz if getattr(slot, "city", None) else DEFAULT_TZ)
    )
    try:
        zone = ZoneInfo(tz_label)
    except Exception:
        zone = ZoneInfo(DEFAULT_TZ)
    return start.astimezone(zone).isoformat()


async def api_slots_payload(
    recruiter_id: Optional[int],
    status: Optional[str],
    limit: int,
    *,
    sort_dir: str = "desc",
) -> List[Dict[str, object]]:
    async with async_session() as session:
        direction = str(sort_dir or "desc").strip().lower()
        if direction not in {"asc", "desc"}:
            direction = "desc"
        order_clause = (
            Slot.start_utc.asc()
            if direction == "asc"
            else Slot.start_utc.desc()
        )
        query = (
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .order_by(order_clause, Slot.id.desc())
        )
        if recruiter_id is not None:
            query = query.where(Slot.recruiter_id == recruiter_id)
        if status:
            query = query.where(Slot.status == status_to_db(status))
        if limit:
            query = query.limit(max(1, min(500, limit)))
        slots = (await session.scalars(query)).all()

        slot_ids = [int(sl.id) for sl in slots if getattr(sl, "id", None) is not None]
        assignment_statuses = (
            SlotAssignmentStatus.OFFERED,
            SlotAssignmentStatus.CONFIRMED,
            SlotAssignmentStatus.RESCHEDULE_REQUESTED,
            SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
        )
        assignment_fallback: Dict[int, Dict[str, object]] = {}
        if slot_ids:
            assignment_rows = (
                await session.execute(
                    select(
                        SlotAssignment.slot_id,
                        SlotAssignment.status,
                        SlotAssignment.candidate_id,
                        SlotAssignment.candidate_tg_id,
                        SlotAssignment.candidate_tz,
                        User.id,
                        User.fio,
                        User.telegram_id,
                        User.telegram_user_id,
                    )
                    .outerjoin(User, User.candidate_id == SlotAssignment.candidate_id)
                    .where(
                        SlotAssignment.slot_id.in_(slot_ids),
                        SlotAssignment.status.in_(assignment_statuses),
                    )
                    .order_by(SlotAssignment.updated_at.desc(), SlotAssignment.id.desc())
                )
            ).all()
            for (
                slot_id,
                assignment_status,
                assignment_candidate_id,
                assignment_candidate_tg_id,
                assignment_candidate_tz,
                user_id,
                user_fio,
                telegram_id,
                telegram_user_id,
            ) in assignment_rows:
                key = int(slot_id)
                if key in assignment_fallback:
                    continue
                assignment_fallback[key] = {
                    "status": assignment_status,
                    "candidate_id": assignment_candidate_id,
                    "candidate_tg_id": assignment_candidate_tg_id,
                    "candidate_tz": assignment_candidate_tz,
                    "candidate_user_id": int(user_id) if user_id is not None else None,
                    "candidate_fio": user_fio,
                    "telegram_id": telegram_id,
                    "telegram_user_id": telegram_user_id,
                }

        candidate_ids = {str(sl.candidate_id) for sl in slots if getattr(sl, "candidate_id", None)}
        candidate_tg_ids = {int(sl.candidate_tg_id) for sl in slots if getattr(sl, "candidate_tg_id", None)}
        for fallback in assignment_fallback.values():
            candidate_id = fallback.get("candidate_id")
            candidate_tg_id = fallback.get("candidate_tg_id")
            telegram_id = fallback.get("telegram_id")
            telegram_user_id = fallback.get("telegram_user_id")
            if candidate_id:
                candidate_ids.add(str(candidate_id))
            if candidate_tg_id is not None:
                candidate_tg_ids.add(int(candidate_tg_id))
            if telegram_id is not None:
                candidate_tg_ids.add(int(telegram_id))
            if telegram_user_id is not None:
                candidate_tg_ids.add(int(telegram_user_id))

        candidate_id_map: Dict[str, int] = {}
        candidate_tg_map: Dict[int, int] = {}
        candidate_name_map: Dict[str, str] = {}
        candidate_tg_name_map: Dict[int, str] = {}

        if candidate_ids or candidate_tg_ids:
            users_query = select(User.id, User.candidate_id, User.telegram_id, User.telegram_user_id, User.fio).where(
                or_(
                    User.candidate_id.in_(candidate_ids) if candidate_ids else literal(False),
                    User.telegram_id.in_(candidate_tg_ids) if candidate_tg_ids else literal(False),
                    User.telegram_user_id.in_(candidate_tg_ids) if candidate_tg_ids else literal(False),
                )
            )
            for user_id, candidate_uuid, telegram_id, telegram_user_id, fio in (await session.execute(users_query)).all():
                if candidate_uuid:
                    candidate_id_map[str(candidate_uuid)] = int(user_id)
                    if fio:
                        candidate_name_map[str(candidate_uuid)] = str(fio)
                if telegram_id:
                    candidate_tg_map[int(telegram_id)] = int(user_id)
                    if fio:
                        candidate_tg_name_map[int(telegram_id)] = str(fio)
                if telegram_user_id:
                    candidate_tg_map[int(telegram_user_id)] = int(user_id)
                    if fio:
                        candidate_tg_name_map[int(telegram_user_id)] = str(fio)
    payload: List[Dict[str, object]] = []
    candidate_row_keys: Dict[int, Optional[str]] = {}
    for sl in slots:
        fallback = assignment_fallback.get(int(sl.id), {})

        recruiter_tz = (
            getattr(getattr(sl, "recruiter", None), "tz", None)
            or DEFAULT_TZ
        )
        candidate_tz = (
            getattr(sl, "candidate_tz", None)
            or fallback.get("candidate_tz")
            or getattr(sl, "tz_name", None)
            or (sl.city.tz if getattr(sl, "city", None) else None)
        )

        computed_status = (
            "PENDING"
            if (
                norm_status(sl.status) == "FREE"
                and fallback.get("status")
                in {
                    SlotAssignmentStatus.OFFERED,
                    SlotAssignmentStatus.RESCHEDULE_REQUESTED,
                }
            )
            else (
                "BOOKED"
                if (
                    norm_status(sl.status) == "FREE"
                    and fallback.get("status")
                    in {
                        SlotAssignmentStatus.CONFIRMED,
                        SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
                    }
                )
                else norm_status(sl.status)
            )
        )
        candidate_tg_id = (
            getattr(sl, "candidate_tg_id", None)
            or fallback.get("candidate_tg_id")
        )
        candidate_user_id = (
            candidate_id_map.get(str(sl.candidate_id))
            if getattr(sl, "candidate_id", None)
            else None
        ) or (
            candidate_tg_map.get(int(sl.candidate_tg_id))
            if getattr(sl, "candidate_tg_id", None)
            else None
        ) or (
            candidate_id_map.get(str(fallback.get("candidate_id")))
            if fallback.get("candidate_id")
            else None
        ) or (
            candidate_tg_map.get(int(fallback.get("candidate_tg_id")))
            if fallback.get("candidate_tg_id") is not None
            else None
        )
        candidate_key: Optional[str] = None
        if candidate_user_id is not None:
            candidate_key = f"cid:{int(candidate_user_id)}"
        elif candidate_tg_id is not None:
            candidate_key = f"tg:{int(candidate_tg_id)}"

        candidate_row_keys[int(sl.id)] = candidate_key
        payload.append(
            {
                "id": sl.id,
                "recruiter_id": sl.recruiter_id,
                "recruiter_name": sl.recruiter.name if sl.recruiter else None,
                "start_utc": _ensure_utc(sl.start_utc).isoformat(),
                "status": computed_status,
                "candidate_fio": (
                    getattr(sl, "candidate_fio", None)
                    or fallback.get("candidate_fio")
                    or (
                        candidate_name_map.get(str(sl.candidate_id))
                        if getattr(sl, "candidate_id", None)
                        else None
                    )
                    or (
                        candidate_tg_name_map.get(int(sl.candidate_tg_id))
                        if getattr(sl, "candidate_tg_id", None)
                        else None
                    )
                    or (
                        candidate_name_map.get(str(fallback.get("candidate_id")))
                        if fallback.get("candidate_id")
                        else None
                    )
                    or (
                        candidate_tg_name_map.get(int(fallback.get("candidate_tg_id")))
                        if fallback.get("candidate_tg_id") is not None
                        else None
                    )
                ),
                "candidate_tg_id": candidate_tg_id,
                "candidate_id": candidate_user_id,
                "tz_name": getattr(sl, "tz_name", None)
                or (sl.city.tz if getattr(sl, "city", None) else None),
                "local_time": _slot_local_time(sl),
                "recruiter_tz": recruiter_tz,
                "recruiter_local_time": _slot_local_time(sl, recruiter_tz),
                "candidate_tz": candidate_tz,
                "candidate_local_time": (
                    _slot_local_time(sl, str(candidate_tz)) if candidate_tz else None
                ),
                "city_name": sl.city.name if sl.city else None,
                "purpose": getattr(sl, "purpose", None) or "interview",
            }
        )

    # Candidate should not appear in interview and intro_day active rows simultaneously.
    active_intro_keys = {
        candidate_row_keys.get(int(row.get("id") or 0))
        for row in payload
        if (row.get("purpose") or "interview") == "intro_day"
        and str(row.get("status") or "").upper() in {"PENDING", "BOOKED", "CONFIRMED", "CONFIRMED_BY_CANDIDATE"}
    }
    active_intro_keys.discard(None)

    if not active_intro_keys:
        return payload

    filtered_payload: List[Dict[str, object]] = []
    for row in payload:
        row_key = candidate_row_keys.get(int(row.get("id") or 0))
        if (
            row_key in active_intro_keys
            and (row.get("purpose") or "interview") == "interview"
            and str(row.get("status") or "").upper() in {"PENDING", "BOOKED", "CONFIRMED", "CONFIRMED_BY_CANDIDATE"}
        ):
            continue
        filtered_payload.append(row)
    return filtered_payload
