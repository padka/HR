import pytest
from datetime import date

from sqlalchemy import select

from backend.apps.admin_ui.services.slots import bulk_create_slots
from backend.apps.admin_ui.utils import recruiter_time_to_utc
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_bulk_create_slots_creates_unique_series():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Bulk", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)

    start = date(2024, 1, 8)

    created, error = await bulk_create_slots(
        recruiter_id=recruiter.id,
        start_date=start.isoformat(),
        end_date=start.isoformat(),
        start_time="10:00",
        end_time="11:30",
        break_start="10:30",
        break_end="11:00",
        step_min=30,
        include_weekends=False,
        use_break=True,
    )
    assert error is None
    assert created == 2

    created_second, error_second = await bulk_create_slots(
        recruiter_id=recruiter.id,
        start_date=start.isoformat(),
        end_date=start.isoformat(),
        start_time="10:00",
        end_time="11:30",
        break_start="10:30",
        break_end="11:00",
        step_min=30,
        include_weekends=False,
        use_break=False,
    )
    assert error_second is None
    assert created_second == 1

    created_third, error_third = await bulk_create_slots(
        recruiter_id=recruiter.id,
        start_date=start.isoformat(),
        end_date=start.isoformat(),
        start_time="10:00",
        end_time="11:30",
        break_start="10:30",
        break_end="11:00",
        step_min=30,
        include_weekends=False,
        use_break=False,
    )
    assert error_third is None
    assert created_third == 0

    async with async_session() as session:
        stored = set(
            await session.scalars(
                select(models.Slot.start_utc).where(models.Slot.recruiter_id == recruiter.id)
            )
        )

    expected = {
        recruiter_time_to_utc(start.isoformat(), "10:00", recruiter.tz),
        recruiter_time_to_utc(start.isoformat(), "10:30", recruiter.tz),
        recruiter_time_to_utc(start.isoformat(), "11:00", recruiter.tz),
    }
    assert stored == expected
