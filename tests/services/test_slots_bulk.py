import pytest
from datetime import date, datetime, timezone

from sqlalchemy import select

from backend.apps.admin_ui.services.slots.core import bulk_create_slots
from backend.apps.admin_ui.utils import local_naive_to_utc
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_bulk_create_slots_creates_unique_series():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Bulk", tz="Europe/Moscow", active=True)
        city = models.City(
            name="Bulk City",
            tz="Europe/Moscow",
            active=True,
            responsible_recruiter_id=None,
        )
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)

    start = date(2024, 1, 8)

    created, error = await bulk_create_slots(
        recruiter_id=recruiter.id,
        city_id=city.id,
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
        city_id=city.id,
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
        city_id=city.id,
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
        stored_slots = list(
            await session.scalars(
                select(models.Slot).where(models.Slot.recruiter_id == recruiter.id)
            )
        )
        stored = {slot.start_utc for slot in stored_slots}

    expected = {
        local_naive_to_utc(datetime.fromisoformat(f"{start.isoformat()}T10:00"), city.tz),
        local_naive_to_utc(datetime.fromisoformat(f"{start.isoformat()}T10:30"), city.tz),
        local_naive_to_utc(datetime.fromisoformat(f"{start.isoformat()}T11:00"), city.tz),
    }

    def _as_utc(dt):
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

    assert {_as_utc(dt) for dt in stored} == {_as_utc(dt) for dt in expected}

    for slot in stored_slots:
        assert slot.duration_min == 30

    async with async_session() as session:
        city_ids = set(
            await session.scalars(
                select(models.Slot.city_id).where(models.Slot.recruiter_id == recruiter.id)
            )
        )
    assert city_ids == {city.id}
