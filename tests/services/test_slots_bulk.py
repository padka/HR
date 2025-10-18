import pytest
from datetime import date, datetime, timezone

from sqlalchemy import select

from backend.apps.admin_ui.services.slots.core import (
    bulk_assign_slots,
    bulk_create_slots,
    bulk_delete_slots,
    bulk_schedule_reminders,
)
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


@pytest.mark.asyncio
async def test_bulk_assign_slots_updates_recruiter():
    async with async_session() as session:
        original = models.Recruiter(name="Origin", tz="Europe/Moscow", active=True)
        target = models.Recruiter(name="Target", tz="Europe/Moscow", active=True)
        city = models.City(name="City", tz="Europe/Moscow", active=True)
        session.add_all([original, target, city])
        await session.commit()
        await session.refresh(original)
        await session.refresh(target)
        slot = models.Slot(
            recruiter_id=original.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    updated, missing = await bulk_assign_slots([slot.id], target.id)
    assert updated == 1
    assert missing == []

    async with async_session() as session:
        refreshed = await session.get(models.Slot, slot.id)
        assert refreshed is not None
        assert refreshed.recruiter_id == target.id


@pytest.mark.asyncio
async def test_bulk_schedule_reminders_uses_service(monkeypatch):
    calls: list[int] = []

    class StubReminder:
        async def schedule_for_slot(self, slot_id: int) -> None:
            calls.append(slot_id)

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.slots.core.get_reminder_service",
        lambda: StubReminder(),
    )

    async with async_session() as session:
        recruiter = models.Recruiter(name="Remind", tz="Europe/Moscow", active=True)
        city = models.City(name="Remind City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=123,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    scheduled, missing = await bulk_schedule_reminders([slot.id])
    assert scheduled == 1
    assert missing == []
    assert calls == [slot.id]


@pytest.mark.asyncio
async def test_bulk_delete_slots_respects_force():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Del", tz="Europe/Moscow", active=True)
        city = models.City(name="Del City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        free_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.FREE,
        )
        booked_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.BOOKED,
        )
        session.add_all([free_slot, booked_slot])
        await session.commit()
        await session.refresh(free_slot)
        await session.refresh(booked_slot)

    deleted, failed = await bulk_delete_slots([free_slot.id, booked_slot.id], force=False)
    assert deleted == 1
    assert failed == [booked_slot.id]

    deleted_force, failed_force = await bulk_delete_slots(
        [booked_slot.id], force=True
    )
    assert deleted_force == 1
    assert failed_force == []
