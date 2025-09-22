from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select

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
    recruiter_id: int, now_utc: Optional[datetime] = None
) -> List[Slot]:
    now_utc = now_utc or datetime.now(timezone.utc)
    async with async_session() as session:
        res = await session.scalars(
            select(Slot)
            .where(
                Slot.recruiter_id == recruiter_id,
                Slot.status == SlotStatus.FREE,
                Slot.start_utc > now_utc,
            )
            .order_by(Slot.start_utc.asc())
        )
        out = list(res)
        for slot in out:
            slot.start_utc = _to_aware_utc(slot.start_utc)
        return out


async def get_slot(slot_id: int) -> Optional[Slot]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot:
            slot.start_utc = _to_aware_utc(slot.start_utc)
        return slot


async def get_template(city_id: int, key: str) -> Optional[Template]:
    async with async_session() as session:
        res = await session.scalars(
            select(Template).where(Template.city_id == city_id, Template.key == key)
        )
        return res.first()


async def reserve_slot(
    slot_id: int, candidate_tg_id: int, candidate_fio: str, candidate_tz: str
) -> Optional[Slot]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id, with_for_update=True)
        if not slot or slot.status != SlotStatus.FREE:
            return None
        slot.status = SlotStatus.PENDING
        slot.candidate_tg_id = candidate_tg_id
        slot.candidate_fio = candidate_fio
        slot.candidate_tz = candidate_tz
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
