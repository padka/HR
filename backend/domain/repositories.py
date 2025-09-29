from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select

from backend.core.db import async_session
from .models import Recruiter, City, Template, Slot, SlotStatus


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def get_active_recruiters() -> List[Recruiter]:
    async with async_session() as session:
        res = await session.scalars(
            select(Recruiter).where(Recruiter.active.is_(True)).order_by(Recruiter.name.asc())
        )
        return list(res)


async def get_active_recruiters_for_city(city_id: int) -> List[Recruiter]:
    """Return recruiters that can process candidates from the given city.

    A recruiter may be linked to the city explicitly (as the responsible
    recruiter configured in the admin UI) or implicitly by owning free slots
    for the city. The second case is important because slot management lives in
    the admin interface: recruiters can be scheduled for specific cities
    without being marked as the responsible contact. The bot must therefore be
    aware of both kinds of relationships to present an accurate choice to the
    candidate after Test 1.
    """

    now = datetime.now(timezone.utc)

    async with async_session() as session:
        res = await session.scalars(
            select(Recruiter)
            .outerjoin(
                City,
                and_(
                    City.responsible_recruiter_id == Recruiter.id,
                    City.id == city_id,
                    City.active.is_(True),
                ),
            )
            .outerjoin(
                Slot,
                and_(
                    Slot.recruiter_id == Recruiter.id,
                    Slot.city_id == city_id,
                    func.lower(Slot.status) == SlotStatus.FREE,
                    Slot.start_utc > now,
                ),
            )
            .where(
                Recruiter.active.is_(True),
                or_(City.id == city_id, Slot.id.is_not(None)),
            )
            .group_by(Recruiter.id)
            .order_by(Recruiter.name.asc())
        )
        return list(res)


async def get_recruiter(recruiter_id: int) -> Optional[Recruiter]:
    async with async_session() as session:
        return await session.get(Recruiter, recruiter_id)


async def get_city_by_name(name: str) -> Optional[City]:
    async with async_session() as session:
        res = await session.scalars(select(City).where(City.name.ilike(name.strip())))
        return res.first()


async def get_city(city_id: int) -> Optional[City]:
    async with async_session() as session:
        return await session.get(City, city_id)


async def get_free_slots_by_recruiter(
    recruiter_id: int,
    now_utc: Optional[datetime] = None,
    *,
    city_id: Optional[int] = None,
) -> List[Slot]:
    now_utc = now_utc or datetime.now(timezone.utc)
    async with async_session() as session:
        query = (
            select(Slot)
            .where(
                Slot.recruiter_id == recruiter_id,
                func.lower(Slot.status) == SlotStatus.FREE,
                Slot.start_utc > now_utc,
            )
            .order_by(Slot.start_utc.asc())
        )
        if city_id is not None:
            query = query.where(Slot.city_id == city_id)

        res = await session.scalars(query)
        out = list(res)
        for slot in out:
            slot.start_utc = _to_aware_utc(slot.start_utc)
        return out


async def get_recruiters_free_slots_summary(
    recruiter_ids: Iterable[int],
    now_utc: Optional[datetime] = None,
    *,
    city_id: Optional[int] = None,
) -> Dict[int, Tuple[datetime, int]]:
    ids = {int(rid) for rid in recruiter_ids if rid is not None}
    if not ids:
        return {}

    now_utc = now_utc or datetime.now(timezone.utc)

    async with async_session() as session:
        rows = (
            await session.execute(
                select(
                    Slot.recruiter_id,
                    func.min(Slot.start_utc).label("next_start"),
                    func.count(Slot.id).label("total_slots"),
                )
                .where(
                    Slot.recruiter_id.in_(ids),
                    func.lower(Slot.status) == SlotStatus.FREE,
                    Slot.start_utc > now_utc,
                    *(
                        [Slot.city_id == city_id]
                        if city_id is not None
                        else []
                    ),
                )
                .group_by(Slot.recruiter_id)
            )
        ).all()

    summary: Dict[int, Tuple[datetime, int]] = {}
    for recruiter_id, next_start, total in rows:
        if next_start is None:
            continue
        summary[int(recruiter_id)] = (_to_aware_utc(next_start), int(total))
    return summary


async def get_slot(slot_id: int) -> Optional[Slot]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot:
            slot.start_utc = _to_aware_utc(slot.start_utc)
        return slot


async def get_template(city_id: Optional[int], key: str) -> Optional[Template]:
    async with async_session() as session:
        base = select(Template).where(Template.key == key)
        if city_id is None:
            res = await session.scalars(base.where(Template.city_id.is_(None)))
            return res.first()

        res = await session.scalars(base.where(Template.city_id == city_id))
        tmpl = res.first()
        if tmpl:
            return tmpl
        fallback = await session.scalars(base.where(Template.city_id.is_(None)))
        return fallback.first()


async def reserve_slot(
    slot_id: int,
    candidate_tg_id: int,
    candidate_fio: str,
    candidate_tz: str,
    *,
    candidate_city_id: Optional[int] = None,
    purpose: str = "interview",
    expected_recruiter_id: Optional[int] = None,
    expected_city_id: Optional[int] = None,
) -> Optional[Slot]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id, with_for_update=True)
        if not slot or slot.status != SlotStatus.FREE:
            return None
        if expected_recruiter_id is not None and slot.recruiter_id != expected_recruiter_id:
            return None
        if expected_city_id is not None and slot.city_id != expected_city_id:
            return None
        slot.status = SlotStatus.PENDING
        slot.candidate_tg_id = candidate_tg_id
        slot.candidate_fio = candidate_fio
        slot.candidate_tz = candidate_tz
        slot.candidate_city_id = candidate_city_id
        slot.purpose = purpose or "interview"
        await session.commit()
        await session.refresh(slot)
        slot.start_utc = _to_aware_utc(slot.start_utc)
        return slot


async def approve_slot(slot_id: int) -> Optional[Slot]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id, with_for_update=True)
        if not slot or slot.status not in (SlotStatus.PENDING, SlotStatus.BOOKED):
            return None
        slot.status = SlotStatus.BOOKED
        await session.commit()
        await session.refresh(slot)
        slot.start_utc = _to_aware_utc(slot.start_utc)
        return slot


async def reject_slot(slot_id: int) -> Optional[Slot]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id, with_for_update=True)
        if not slot:
            return None
        slot.status = SlotStatus.FREE
        slot.candidate_tg_id = None
        slot.candidate_fio = None
        slot.candidate_tz = None
        await session.commit()
        await session.refresh(slot)
        slot.start_utc = _to_aware_utc(slot.start_utc)
        return slot


async def set_recruiter_chat_id_by_command(name_hint: str, chat_id: int) -> Optional[Recruiter]:
    async with async_session() as session:
        rec = await session.scalar(select(Recruiter).where(Recruiter.name.ilike(name_hint)))
        if not rec:
            return None
        rec.tg_chat_id = chat_id
        await session.commit()
        return rec
