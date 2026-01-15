from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.domain.models import Recruiter, City, Slot, SlotStatus


def _dt(hour: int, minute: int) -> datetime:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    base = now + timedelta(days=1)
    return base.replace(hour=hour, minute=minute)


@pytest.mark.asyncio
async def test_slots_30_minutes_apart_do_not_conflict():
    async with async_session() as session:
        recruiter = Recruiter(name="Overlap Free", tz="Europe/Moscow", active=True)
        city = City(name="Overlap City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=_dt(16, 30),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=_dt(17, 0),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot2)
        await session.commit()  # Should not conflict


@pytest.mark.asyncio
async def test_slots_5_minutes_apart_conflict():
    async with async_session() as session:
        recruiter = Recruiter(name="Overlap Clash", tz="Europe/Moscow", active=True)
        city = City(name="Overlap City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        first = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=_dt(16, 30),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(first)
        await session.commit()

        conflict = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=_dt(16, 35),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(conflict)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_slots_exactly_10_minutes_apart_do_not_conflict():
    async with async_session() as session:
        recruiter = Recruiter(name="Overlap Gap", tz="Europe/Moscow", active=True)
        city = City(name="Overlap City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=_dt(16, 30),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=_dt(16, 40),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot2)
        await session.commit()  # No conflict at 10-minute boundary


@pytest.mark.asyncio
async def test_slots_9_minutes_apart_conflict():
    async with async_session() as session:
        recruiter = Recruiter(name="Overlap Tight", tz="Europe/Moscow", active=True)
        city = City(name="Overlap City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=_dt(16, 30),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=_dt(16, 39),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot2)
        with pytest.raises(IntegrityError):
            await session.commit()
