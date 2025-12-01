"""Tests for SlotRepository (Phase 1 & 2 optimized repository)."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.db import async_session
from backend.core.result import Success
from backend.core.uow import UnitOfWork
from backend.domain.models import City, Recruiter, Slot, SlotStatus


@pytest.mark.asyncio
async def test_get_upcoming_for_candidate_uses_correct_field():
    """
    Regression test for bug fix: get_upcoming_for_candidate should use
    Slot.candidate_tg_id (not Slot.telegram_id) to filter by candidate.
    """
    # Arrange: Create test data
    async with async_session() as session:
        city = City(name="Test City", tz="UTC", active=True)
        recruiter = Recruiter(name="Test Recruiter", tz="UTC", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        # Create slots with candidate_tg_id
        candidate_tg_id = 123456789
        now = datetime.now(timezone.utc)

        # Slot 1: For our candidate, in the future
        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=1),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate_tg_id,  # This field should be used
        )

        # Slot 2: For our candidate, in the past (should not be returned)
        slot2 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now - timedelta(hours=2),
            duration_min=60,
            status=SlotStatus.CANCELED,
            candidate_tg_id=candidate_tg_id,
        )

        # Slot 3: For different candidate, in the future (should not be returned)
        slot3 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=3),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=999999999,  # Different candidate
        )

        # Slot 4: For our candidate, in the future (should be returned)
        slot4 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=5),
            duration_min=60,
            status=SlotStatus.BOOKED,
            purpose="intro_day",  # different purpose to satisfy unique constraint
            candidate_tg_id=candidate_tg_id,
        )

        session.add_all([slot1, slot2, slot3, slot4])
        await session.commit()
        await session.refresh(slot1)
        await session.refresh(slot4)

    # Act: Query using UnitOfWork and SlotRepository
    async with UnitOfWork() as uow:
        result = await uow.slots.get_upcoming_for_candidate(
            telegram_id=candidate_tg_id,
            after=now,
        )

    # Assert: Check that result is Success and contains correct slots
    assert isinstance(result, Success), f"Expected Success, got {result}"

    slots = result.value
    assert len(slots) == 2, f"Expected 2 slots, got {len(slots)}"

    # Check that returned slots are the correct ones
    slot_ids = {slot.id for slot in slots}
    assert slot1.id in slot_ids, "Slot 1 should be returned"
    assert slot4.id in slot_ids, "Slot 4 should be returned"
    assert slot2.id not in slot_ids, "Slot 2 (past) should not be returned"
    assert slot3.id not in slot_ids, "Slot 3 (different candidate) should not be returned"

    # Check that slots are ordered by start_utc
    assert slots[0].start_utc < slots[1].start_utc, "Slots should be ordered by start_utc"

    # Check that relationships are eager loaded (Phase 2 optimization)
    for slot in slots:
        # Accessing relationships should not trigger additional queries
        assert slot.recruiter is not None, "Recruiter should be eager loaded"
        assert slot.recruiter.name == "Test Recruiter"
        assert slot.city is not None, "City should be eager loaded"
        assert slot.city.name == "Test City"


@pytest.mark.asyncio
async def test_get_upcoming_for_candidate_empty_result():
    """Test that get_upcoming_for_candidate returns empty list when no slots found."""
    async with UnitOfWork() as uow:
        result = await uow.slots.get_upcoming_for_candidate(
            telegram_id=999999999,  # Non-existent candidate
            after=datetime.now(timezone.utc),
        )

    assert isinstance(result, Success)
    assert len(result.value) == 0, "Should return empty list when no slots found"


@pytest.mark.asyncio
async def test_get_free_for_recruiter():
    """Test get_free_for_recruiter method with caching."""
    # Arrange: Create test data
    async with async_session() as session:
        city = City(name="Test City", tz="UTC", active=True)
        recruiter = Recruiter(name="Test Recruiter", tz="UTC", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        now = datetime.now(timezone.utc)

        # Create free slot in the future
        free_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=1),
            duration_min=60,
            status=SlotStatus.FREE,
        )

        # Create booked slot (should not be returned)
        booked_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=3),
            duration_min=60,
            status=SlotStatus.BOOKED,
        )

        session.add_all([free_slot, booked_slot])
        await session.commit()
        await session.refresh(free_slot)

    # Act: Query using UnitOfWork
    async with UnitOfWork() as uow:
        result = await uow.slots.get_free_for_recruiter(
            recruiter_id=recruiter.id,
            after=now,
        )

    # Assert
    assert isinstance(result, Success)
    slots = result.value
    assert len(slots) == 1, f"Expected 1 free slot, got {len(slots)}"
    assert slots[0].id == free_slot.id
    assert slots[0].status == SlotStatus.FREE
