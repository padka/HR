"""Test timezone handling for slots."""
import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.apps.admin_ui.services.slots import create_slot, bulk_create_slots
from backend.apps.admin_ui.utils import recruiter_time_to_utc
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_single_slot_uses_city_timezone():
    """Test that create_slot uses city timezone, not recruiter timezone."""
    async with async_session() as session:
        # Recruiter in Moscow (UTC+3)
        recruiter = models.Recruiter(name="Moscow Recruiter", tz="Europe/Moscow", active=True)

        # City in Yekaterinburg (UTC+5)
        city = models.City(
            name="Yekaterinburg",
            tz="Asia/Yekaterinburg",
            active=True,
        )
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

    # Create slot for 14:00 local time in Yekaterinburg
    success = await create_slot(
        recruiter_id=recruiter.id,
        city_id=city.id,
        date="2024-06-15",
        time="14:00",
    )
    assert success is True

    # Verify the slot was created with correct timezone
    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot).where(
                models.Slot.recruiter_id == recruiter.id,
                models.Slot.city_id == city.id,
            )
        )
        assert slot is not None
        assert slot.tz_name == "Asia/Yekaterinburg"

        # 14:00 YEKT = 09:00 UTC (Yekaterinburg is UTC+5)
        expected_utc = datetime(2024, 6, 15, 9, 0, tzinfo=timezone.utc)

        # Ensure slot.start_utc is timezone-aware
        start_utc = slot.start_utc
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)

        assert start_utc == expected_utc, \
            f"Expected {expected_utc}, got {start_utc}. " \
            f"14:00 in Yekaterinburg (UTC+5) should be 09:00 UTC, not 11:00 UTC (which would be Moscow time)."


@pytest.mark.asyncio
async def test_bulk_slots_use_city_timezone():
    """Test that bulk_create_slots uses city timezone, not recruiter timezone."""
    async with async_session() as session:
        # Recruiter in Moscow (UTC+3)
        recruiter = models.Recruiter(name="Moscow Recruiter 2", tz="Europe/Moscow", active=True)

        # City in Yekaterinburg (UTC+5)
        city = models.City(
            name="Yekaterinburg 2",
            tz="Asia/Yekaterinburg",
            active=True,
        )
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

    # Create slots for 14:00 and 15:00 local time in Yekaterinburg
    created, error = await bulk_create_slots(
        recruiter_id=recruiter.id,
        city_id=city.id,
        start_date="2024-06-15",
        end_date="2024-06-15",
        start_time="14:00",
        end_time="16:00",
        break_start="10:00",
        break_end="10:00",  # No break
        step_min=60,
        include_weekends=True,
        use_break=False,
    )
    assert error is None
    assert created == 2

    # Verify slots were created with correct timezone
    async with async_session() as session:
        slots = list(
            await session.scalars(
                select(models.Slot)
                .where(models.Slot.recruiter_id == recruiter.id)
                .order_by(models.Slot.start_utc)
            )
        )
        assert len(slots) == 2

        # Both slots should have Yekaterinburg timezone
        for slot in slots:
            assert slot.tz_name == "Asia/Yekaterinburg"

        # 14:00 YEKT = 09:00 UTC
        expected_start_utc = datetime(2024, 6, 15, 9, 0, tzinfo=timezone.utc)
        # 15:00 YEKT = 10:00 UTC
        expected_second_utc = datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)

        start_utc_first = slots[0].start_utc
        if start_utc_first.tzinfo is None:
            start_utc_first = start_utc_first.replace(tzinfo=timezone.utc)

        start_utc_second = slots[1].start_utc
        if start_utc_second.tzinfo is None:
            start_utc_second = start_utc_second.replace(tzinfo=timezone.utc)

        assert start_utc_first == expected_start_utc, \
            f"First slot: Expected {expected_start_utc}, got {start_utc_first}"
        assert start_utc_second == expected_second_utc, \
            f"Second slot: Expected {expected_second_utc}, got {start_utc_second}"


@pytest.mark.asyncio
async def test_slot_fallback_to_recruiter_timezone_if_city_has_none():
    """Test that if city has no timezone, it falls back to recruiter timezone."""
    async with async_session() as session:
        # Recruiter in Moscow (UTC+3)
        recruiter = models.Recruiter(name="Moscow Recruiter 3", tz="Europe/Moscow", active=True)

        # City with no timezone (should fallback to recruiter timezone)
        city = models.City(
            name="City Without TZ",
            tz=None,  # No timezone
            active=True,
        )
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

    # Create slot for 14:00 - should use recruiter's timezone (Moscow)
    success = await create_slot(
        recruiter_id=recruiter.id,
        city_id=city.id,
        date="2024-06-15",
        time="14:00",
    )
    assert success is True

    # Verify the slot uses recruiter's timezone as fallback
    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot).where(
                models.Slot.recruiter_id == recruiter.id,
                models.Slot.city_id == city.id,
            )
        )
        assert slot is not None
        assert slot.tz_name == "Europe/Moscow"  # Fallback to recruiter timezone

        # 14:00 MSK = 11:00 UTC (Moscow is UTC+3)
        expected_utc = datetime(2024, 6, 15, 11, 0, tzinfo=timezone.utc)

        start_utc = slot.start_utc
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)

        assert start_utc == expected_utc
