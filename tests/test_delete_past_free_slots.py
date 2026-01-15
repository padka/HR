"""Cleanup of past free interview slots."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import Recruiter, City, Slot, SlotStatus
from backend.apps.admin_ui.services.slots import delete_past_free_slots


@pytest.mark.asyncio
async def test_delete_past_free_slots_removes_only_stale_free_interview():
    async with async_session() as session:
        recruiter = Recruiter(name="Cleaner", tz="Europe/Moscow", active=True)
        city = City(name="Clean City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        past_free = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) - timedelta(hours=2),
            duration_min=20,
            status=SlotStatus.FREE,
            purpose="interview",
        )
        future_free = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            duration_min=20,
            status=SlotStatus.FREE,
            purpose="interview",
        )
        past_booked = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) - timedelta(hours=3),
            duration_min=20,
            status=SlotStatus.BOOKED,
            purpose="interview",
        )
        session.add_all([past_free, future_free, past_booked])
        await session.commit()

    deleted, total = await delete_past_free_slots()
    assert deleted == 1
    assert total == 1

    async with async_session() as session:
        rows = await session.execute(select(Slot.id))
        ids = {row[0] for row in rows}
        assert past_free.id not in ids
        assert future_free.id in ids
        assert past_booked.id in ids
