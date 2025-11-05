import pytest
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from backend.apps.admin_ui.services.slots import delete_slot, delete_all_slots, create_slot
from backend.core.db import async_session
from backend.domain import models


async def _setup_recruiter_with_city():
    async with async_session() as session:
        unique_suffix = uuid.uuid4().hex[:6]
        recruiter = models.Recruiter(name=f"DeleteCase {unique_suffix}", tz="Europe/Moscow", active=True)
        city = models.City(name=f"Delete City {unique_suffix}", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        return recruiter.id, city.id


@pytest.mark.asyncio
async def test_delete_slot_allows_free_and_pending_blocks_booked():
    recruiter_id, city_id = await _setup_recruiter_with_city()

    # FREE slot via public API helper
    created = await create_slot(recruiter_id, datetime.now().date().isoformat(), "09:00", city_id=city_id)
    assert created is True

    async with async_session() as session:
        free_slot = await session.scalar(select(models.Slot).where(models.Slot.recruiter_id == recruiter_id).limit(1))
        pending_slot = models.Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.PENDING,
        )
        booked_slot = models.Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=1),
            status=models.SlotStatus.BOOKED,
        )
        session.add_all([pending_slot, booked_slot])
        await session.commit()
        await session.refresh(pending_slot)
        await session.refresh(booked_slot)
        assert free_slot is not None
        assert free_slot.tz_name == "Europe/Moscow"

    ok_free, err_free = await delete_slot(free_slot.id)
    assert ok_free is True
    assert err_free is None

    ok_pending, err_pending = await delete_slot(pending_slot.id)
    assert ok_pending is True
    assert err_pending is None

    ok_booked, err_booked = await delete_slot(booked_slot.id)
    assert ok_booked is False
    assert isinstance(err_booked, str)
    assert "статусом" in err_booked

    async with async_session() as session:
        remaining_ids = set(await session.scalars(select(models.Slot.id).where(models.Slot.recruiter_id == recruiter_id)))
    assert booked_slot.id in remaining_ids
    assert free_slot.id not in remaining_ids
    assert pending_slot.id not in remaining_ids

    ok_forced, err_forced = await delete_slot(booked_slot.id, force=True)
    assert ok_forced is True
    assert err_forced is None

    async with async_session() as session:
        remaining_after_force = set(await session.scalars(select(models.Slot.id).where(models.Slot.recruiter_id == recruiter_id)))
    assert booked_slot.id not in remaining_after_force


@pytest.mark.asyncio
async def test_delete_slot_missing_returns_error():
    ok, err = await delete_slot(999999)
    assert ok is False
    assert err == "Слот не найден"


@pytest.mark.asyncio
async def test_delete_all_slots_handles_force():
    recruiter_id, city_id = await _setup_recruiter_with_city()

    async with async_session() as session:
        now = datetime.now(timezone.utc)
        session.add_all(
            [
                models.Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=now,
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.PENDING,
                ),
                models.Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=now + timedelta(hours=2),
                    status=models.SlotStatus.BOOKED,
                ),
            ]
        )
        await session.commit()

    deleted, remaining = await delete_all_slots(force=False)
    assert deleted == 2
    assert remaining == 1

    deleted_force, remaining_force = await delete_all_slots(force=True)
    assert deleted_force == 1
    assert remaining_force == 0
