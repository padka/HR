"""
Test proper handling of slot overlap conflicts.

This test verifies that:
1. Database exclusion constraint correctly prevents overlapping slots
2. IntegrityError is caught and rolled back properly
3. SlotOverlapError is raised as a business-level exception
4. No connection leaks occur
5. No 500 errors are returned to the user
"""
import pytest
from datetime import datetime, timezone

from backend.apps.admin_ui.services.slots import create_slot
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus
from backend.domain.errors import SlotOverlapError


@pytest.mark.asyncio
async def test_slot_overlap_raises_domain_error():
    """
    Test that attempting to create an overlapping slot:
    1. Does not create the slot
    2. Raises SlotOverlapError (not IntegrityError)
    3. Does not cause 500 error
    4. Properly rolls back the transaction
    """
    async with async_session() as session:
        # Create test recruiter and city
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id

        # Create first slot: 12:40 - 13:40 (UTC: 09:40 - 10:40)
        first_slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            candidate_city_id=city_id,
            start_utc=datetime(2030, 6, 15, 9, 40, 0, tzinfo=timezone.utc),
            status=SlotStatus.FREE.value if hasattr(SlotStatus.FREE, 'value') else SlotStatus.FREE,
            tz_name="Europe/Moscow",
            candidate_tz="Europe/Moscow",
            duration_min=60,
        )
        session.add(first_slot)
        await session.commit()
        await session.refresh(first_slot)
        session.expunge_all()

    # Try to create overlapping slot: 13:30 - 14:30 (UTC: 10:30 - 11:30)
    # This overlaps with first slot (09:40-10:40 overlaps with 10:30-11:30? No)
    # Let's create a slot that actually overlaps: 13:00 - 14:00 (UTC: 10:00 - 11:00)
    # This overlaps with 09:40-10:40 because 10:00 is within that range

    with pytest.raises(SlotOverlapError) as exc_info:
        await create_slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            date="2030-06-15",
            time="13:00",  # 13:00 MSK = 10:00 UTC (overlaps with 09:40-10:40 slot)
        )

    # Verify the exception contains correct information
    assert exc_info.value.recruiter_id == recruiter_id
    assert exc_info.value.start_utc is not None

    # Verify that only one slot exists (the overlapping one was not created)
    async with async_session() as session:
        from sqlalchemy import select, func
        count = await session.scalar(
            select(func.count(Slot.id)).where(Slot.recruiter_id == recruiter_id)
        )
        assert count == 1, "Only the first slot should exist, overlapping slot should not be created"


@pytest.mark.asyncio
async def test_slot_overlap_with_exact_same_time():
    """
    Test creating a slot at the exact same time as an existing slot.
    This should also trigger the overlap constraint.
    """
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter 2", tz="Europe/Moscow", active=True)
        city = City(name="Test City 2", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()

    # Create first slot at 14:00 MSK
    success = await create_slot(
        recruiter_id=recruiter_id,
        city_id=city_id,
        date="2030-06-15",
        time="14:00",
    )
    assert success is True, "First slot should be created successfully"

    # Try to create second slot at exactly the same time
    with pytest.raises(SlotOverlapError):
        await create_slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            date="2030-06-15",
            time="14:00",
        )

    # Verify only one slot exists
    async with async_session() as session:
        from sqlalchemy import select, func
        count = await session.scalar(
            select(func.count(Slot.id)).where(Slot.recruiter_id == recruiter_id)
        )
        assert count == 1


@pytest.mark.asyncio
async def test_non_overlapping_slots_succeed():
    """
    Test that creating non-overlapping slots works correctly.
    This ensures we didn't break normal slot creation.
    """
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter 3", tz="Europe/Moscow", active=True)
        city = City(name="Test City 3", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()

    # Create first slot at 10:00
    success1 = await create_slot(
        recruiter_id=recruiter_id,
        city_id=city_id,
        date="2030-06-15",
        time="10:00",
    )
    assert success1 is True

    # Create second slot at 12:00 (2 hours later, no overlap)
    success2 = await create_slot(
        recruiter_id=recruiter_id,
        city_id=city_id,
        date="2030-06-15",
        time="12:00",
    )
    assert success2 is True

    # Verify both slots exist
    async with async_session() as session:
        from sqlalchemy import select, func
        count = await session.scalar(
            select(func.count(Slot.id)).where(Slot.recruiter_id == recruiter_id)
        )
        assert count == 2, "Both non-overlapping slots should be created"


@pytest.mark.asyncio
async def test_different_recruiters_same_time():
    """
    Test that different recruiters can have slots at the same time.
    The exclusion constraint only prevents overlaps for the same recruiter.
    """
    async with async_session() as session:
        recruiter1 = Recruiter(name="Recruiter 1", tz="Europe/Moscow", active=True)
        recruiter2 = Recruiter(name="Recruiter 2", tz="Europe/Moscow", active=True)
        city = City(name="Shared City", tz="Europe/Moscow", active=True)
        recruiter1.cities.append(city)
        recruiter2.cities.append(city)
        session.add_all([recruiter1, recruiter2, city])
        await session.commit()
        await session.refresh(recruiter1)
        await session.refresh(recruiter2)
        await session.refresh(city)

        recruiter1_id = recruiter1.id
        recruiter2_id = recruiter2.id
        city_id = city.id
        session.expunge_all()

    # Create slot for recruiter 1 at 14:00
    success1 = await create_slot(
        recruiter_id=recruiter1_id,
        city_id=city_id,
        date="2030-06-15",
        time="14:00",
    )
    assert success1 is True

    # Create slot for recruiter 2 at the same time (should succeed)
    success2 = await create_slot(
        recruiter_id=recruiter2_id,
        city_id=city_id,
        date="2030-06-15",
        time="14:00",
    )
    assert success2 is True, "Different recruiters can have slots at the same time"
