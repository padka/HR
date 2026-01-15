"""Test exclusion constraint preventing overlapping slots for the same recruiter."""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.domain.models import Recruiter, City, Slot, SlotStatus


@pytest.mark.asyncio
async def test_slot_overlap_constraint_prevents_exact_overlap():
    """Test that constraint prevents creating slots with exact time overlap."""
    async with async_session() as session:
        # Create test data
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)

        # Create first slot
        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time,
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        # Try to create overlapping slot with exact same start time
        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time,  # Same start time
            duration_min=30,
            status=SlotStatus.FREE,
        )
        session.add(slot2)

        # Should raise IntegrityError due to exclusion constraint
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()

        assert "slots_no_recruiter_time_overlap_excl" in str(exc_info.value)


@pytest.mark.asyncio
async def test_slot_overlap_constraint_prevents_partial_overlap():
    """Test that constraint prevents creating slots with partial time overlap."""
    async with async_session() as session:
        # Create test data
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)

        # Create first slot: 10:00-10:10 (10 minutes window)
        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time,
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        # Try to create overlapping slot: 10:05-10:15 (starts within 10 minute window)
        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time + timedelta(minutes=5),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot2)

        # Should raise IntegrityError
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()

        assert "slots_no_recruiter_time_overlap_excl" in str(exc_info.value)


@pytest.mark.asyncio
async def test_slot_overlap_constraint_prevents_contained_slot():
    """Test that constraint prevents creating a slot fully contained within another."""
    async with async_session() as session:
        # Create test data
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=3)

        # Create first slot: 10:00-10:20 (20 minutes window, but overlap uses 10 minutes)
        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time,
            duration_min=20,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        # Try to create slot contained within window: 10:05-10:15 (10 minutes)
        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time + timedelta(minutes=5),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot2)

        # Should raise IntegrityError
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()

        assert "slots_no_recruiter_time_overlap_excl" in str(exc_info.value)


@pytest.mark.asyncio
async def test_slot_overlap_constraint_allows_adjacent_slots():
    """Test that constraint allows adjacent slots (no gap, no overlap)."""
    async with async_session() as session:
        # Create test data
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=4)

        # Create first slot: 10:00-10:10 (10 minutes)
        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time,
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        # Create adjacent slot: 10:10-10:20 (starts exactly when first ends)
        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time + timedelta(minutes=10),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(slot2)
        await session.commit()  # Should succeed

        # Verify both slots exist
        slots = (
            await session.execute(
                select(Slot)
                .where(Slot.recruiter_id == recruiter.id)
                .where(Slot.start_utc >= start_time)
                .order_by(Slot.start_utc)
            )
        ).scalars().all()

        assert len(slots) == 2
        assert slots[0].start_utc == start_time
        assert slots[1].start_utc == start_time + timedelta(minutes=10)


@pytest.mark.asyncio
async def test_slot_overlap_allows_touching_10_minute_slots():
    """Ensure half-open intervals allow back-to-back 10 minute interviews."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot_start = datetime.now(timezone.utc).replace(microsecond=0, second=0, minute=50) + timedelta(days=6)

        first_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=slot_start,
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(first_slot)
        await session.commit()

        touching_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=slot_start + timedelta(minutes=10),
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(touching_slot)
        await session.commit()

        saved_slots = (
            await session.execute(
                select(Slot)
                .where(Slot.recruiter_id == recruiter.id)
                .where(Slot.start_utc >= slot_start)
                .order_by(Slot.start_utc)
            )
        ).scalars().all()
        assert [slot.start_utc for slot in saved_slots] == [
            slot_start,
            slot_start + timedelta(minutes=10),
        ]


@pytest.mark.asyncio
async def test_slot_overlap_detects_overlap_for_10_minute_slots():
    """Slots overlapping within the 10 minute window should be blocked."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot_start = datetime.now(timezone.utc).replace(microsecond=0, second=0, minute=50) + timedelta(days=7)
        first_start = slot_start + timedelta(minutes=5)  # :55

        leading_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=first_start,
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(leading_slot)
        await session.commit()

        overlapping_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=first_start + timedelta(minutes=5),  # Starts 5 minutes after first, overlaps
            duration_min=10,
            status=SlotStatus.FREE,
        )
        session.add(overlapping_slot)

        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()

        assert "slots_no_recruiter_time_overlap_excl" in str(exc_info.value)


@pytest.mark.asyncio
async def test_slot_overlap_constraint_allows_different_recruiters():
    """Test that constraint allows overlapping slots for different recruiters."""
    async with async_session() as session:
        # Create test data
        recruiter1 = Recruiter(name="Test Recruiter 1", tz="Europe/Moscow", active=True)
        recruiter2 = Recruiter(name="Test Recruiter 2", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter1)
        session.add(recruiter2)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter1)
        await session.refresh(recruiter2)
        await session.refresh(city)

        recruiters = [recruiter1, recruiter2]
        start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=5)

        # Create slot for first recruiter
        slot1 = Slot(
            recruiter_id=recruiters[0].id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time,
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        # Create overlapping slot for second recruiter (should be allowed)
        slot2 = Slot(
            recruiter_id=recruiters[1].id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time,  # Same time, different recruiter
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot2)
        await session.commit()  # Should succeed

        # Verify both slots exist
        slots = (
            await session.execute(
                select(Slot)
                .where(Slot.start_utc == start_time)
                .order_by(Slot.recruiter_id)
            )
        ).scalars().all()

        assert len(slots) == 2
        assert slots[0].recruiter_id == recruiters[0].id
        assert slots[1].recruiter_id == recruiters[1].id


@pytest.mark.asyncio
async def test_slot_overlap_constraint_allows_separated_slots():
    """Test that constraint allows slots with time gap between them."""
    async with async_session() as session:
        # Create test data
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=6)

        # Create first slot: 10:00-11:00
        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time,
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot1)
        await session.commit()

        # Create second slot: 12:00-13:00 (1 hour gap)
        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=start_time + timedelta(minutes=120),
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot2)
        await session.commit()  # Should succeed

        # Verify both slots exist
        slots = (
            await session.execute(
                select(Slot)
                .where(Slot.recruiter_id == recruiter.id)
                .where(Slot.start_utc >= start_time)
                .order_by(Slot.start_utc)
            )
        ).scalars().all()

        assert len(slots) == 2
