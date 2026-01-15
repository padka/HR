"""Ensure slots cannot be created or booked in the past."""

from datetime import datetime, timedelta, timezone, date

import pytest

from backend.apps.admin_ui.services.slots import create_slot
from backend.domain.models import Recruiter, City, Slot, SlotStatus
from backend.core.db import async_session
from backend.domain.repositories import reserve_slot
from sqlalchemy import select, func


@pytest.mark.asyncio
async def test_create_slot_rejects_past_time():
    async with async_session() as session:
        recruiter = Recruiter(name="Past Check", tz="Europe/Moscow", active=True)
        city = City(name="Past City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        yesterday = date.today() - timedelta(days=1)
        ok = await create_slot(
            recruiter_id=recruiter.id,
            date=yesterday.isoformat(),
            time="10:00",
            city_id=city.id,
        )
        assert ok is False

        slots_count = await session.scalar(select(func.count()).select_from(Slot)) or 0
        assert slots_count == 0


@pytest.mark.asyncio
async def test_reserve_slot_rejects_past_start():
    async with async_session() as session:
        recruiter = Recruiter(name="Past Booker", tz="Europe/Moscow", active=True)
        city = City(name="Reserve City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        past_start = datetime.now(timezone.utc) - timedelta(hours=2)
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=past_start,
            duration_min=20,
            status=SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        result = await reserve_slot(
            slot_id=slot.id,
            candidate_tg_id=999,
            candidate_fio="Test Candidate",
            candidate_tz="Europe/Moscow",
        )
        assert result.status == "slot_taken"
