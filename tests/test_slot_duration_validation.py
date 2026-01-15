"""Tests for slot duration validation."""

from datetime import datetime, timezone
import pytest

from backend.core.db import async_session
from backend.domain.models import (
    Recruiter,
    City,
    Slot,
    SlotStatus,
    SLOT_MIN_DURATION_MIN,
    SLOT_MAX_DURATION_MIN,
)


@pytest.mark.asyncio
async def test_slot_valid_duration():
    """Test that valid slot durations are accepted."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Test various valid durations
        from datetime import timedelta

        valid_durations = [
            SLOT_MIN_DURATION_MIN,  # Minimum (10 min)
            30,  # Half hour
            60,  # 1 hour
            90,  # 1.5 hours
            120,  # 2 hours
            SLOT_MAX_DURATION_MIN,  # Maximum (4 hours)
        ]

        base_time = datetime.now(timezone.utc)
        offset_hours = 0

        for duration in valid_durations:
            # Ensure each slot starts at different time to avoid overlapping
            start_time = base_time + timedelta(hours=offset_hours)
            offset_hours += 5  # 5 hours gap between slots

            slot = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name="Europe/Moscow",
                start_utc=start_time,
                duration_min=duration,
                status=SlotStatus.FREE,
            )
            session.add(slot)
            await session.commit()

            await session.refresh(slot)
            assert slot.duration_min == duration


@pytest.mark.asyncio
async def test_slot_duration_too_short():
    """Test that slot duration below minimum is rejected."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Try durations below minimum
        invalid_durations = [1, 5, 9]

        for duration in invalid_durations:
            with pytest.raises(ValueError, match="duration too short"):
                slot = Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    tz_name="Europe/Moscow",
                    start_utc=datetime.now(timezone.utc),
                    duration_min=duration,
                    status=SlotStatus.FREE,
                )


@pytest.mark.asyncio
async def test_slot_duration_too_long():
    """Test that slot duration above maximum is rejected."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Try durations above maximum
        invalid_durations = [241, 300, 480, 1000]

        for duration in invalid_durations:
            with pytest.raises(ValueError, match="duration too long"):
                slot = Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    tz_name="Europe/Moscow",
                    start_utc=datetime.now(timezone.utc),
                    duration_min=duration,
                    status=SlotStatus.FREE,
                )


@pytest.mark.asyncio
async def test_slot_duration_zero_or_negative():
    """Test that zero or negative durations are rejected."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Try zero and negative durations
        invalid_durations = [0, -1, -10, -60]

        for duration in invalid_durations:
            with pytest.raises(ValueError, match="positive integer"):
                slot = Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    tz_name="Europe/Moscow",
                    start_utc=datetime.now(timezone.utc),
                    duration_min=duration,
                    status=SlotStatus.FREE,
                )


@pytest.mark.asyncio
async def test_slot_duration_none():
    """Test that None duration is rejected."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Try None duration
        with pytest.raises(ValueError, match="Duration cannot be None"):
            slot = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name="Europe/Moscow",
                start_utc=datetime.now(timezone.utc),
                duration_min=None,  # type: ignore
                status=SlotStatus.FREE,
            )


@pytest.mark.asyncio
async def test_slot_duration_boundary_values():
    """Test boundary values for slot duration."""
    from datetime import timedelta

    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        base_time = datetime.now(timezone.utc)

        # Test minimum boundary (should succeed)
        slot_min = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=base_time,
            duration_min=SLOT_MIN_DURATION_MIN,
            status=SlotStatus.FREE,
        )
        session.add(slot_min)
        await session.commit()
        await session.refresh(slot_min)
        assert slot_min.duration_min == SLOT_MIN_DURATION_MIN

        # Test just below minimum (should fail)
        with pytest.raises(ValueError, match="duration too short"):
            slot_below_min = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name="Europe/Moscow",
                start_utc=base_time + timedelta(hours=1),
                duration_min=SLOT_MIN_DURATION_MIN - 1,
                status=SlotStatus.FREE,
            )

        # Test maximum boundary (should succeed) - use different time to avoid overlap
        slot_max = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=base_time + timedelta(hours=10),  # Far from first slot
            duration_min=SLOT_MAX_DURATION_MIN,
            status=SlotStatus.FREE,
        )
        session.add(slot_max)
        await session.commit()
        await session.refresh(slot_max)
        assert slot_max.duration_min == SLOT_MAX_DURATION_MIN

        # Test just above maximum (should fail)
        with pytest.raises(ValueError, match="duration too long"):
            slot_above_max = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name="Europe/Moscow",
                start_utc=base_time + timedelta(hours=20),
                duration_min=SLOT_MAX_DURATION_MIN + 1,
                status=SlotStatus.FREE,
            )
