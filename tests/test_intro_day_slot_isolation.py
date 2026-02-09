"""Intro day slots must not affect interview slot availability and bookings."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.db import async_session
from backend.domain.models import Recruiter, City, Slot, SlotStatus
from backend.domain.repositories import city_has_available_slots, reserve_slot


@pytest.mark.asyncio
async def test_intro_day_not_counted_as_available_slot():
    async with async_session() as session:
        recruiter = Recruiter(name="Intro Rec", tz="Europe/Moscow", active=True)
        city = City(name="Intro City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        intro_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=20,
            status=SlotStatus.FREE,
            purpose="intro_day",
        )
        session.add(intro_slot)
        await session.commit()

        available = await city_has_available_slots(city.id)
        assert available is False


@pytest.mark.asyncio
async def test_intro_day_slot_cannot_be_booked_as_interview():
    async with async_session() as session:
        recruiter = Recruiter(name="Intro Rec2", tz="Europe/Moscow", active=True)
        city = City(name="Intro City2", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        intro_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=4),
            duration_min=20,
            status=SlotStatus.FREE,
            purpose="intro_day",
        )
        session.add(intro_slot)
        await session.commit()
        await session.refresh(intro_slot)

    result = await reserve_slot(
        slot_id=intro_slot.id,
        candidate_tg_id=12345,
        candidate_fio="Intro Candidate",
        candidate_tz="Europe/Moscow",
    )
    assert result.status == "slot_taken"


@pytest.mark.asyncio
async def test_intro_day_slot_can_be_reserved_with_matching_purpose():
    async with async_session() as session:
        recruiter = Recruiter(name="Intro Rec3", tz="Europe/Moscow", active=True)
        city = City(name="Intro City3", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        intro_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=5),
            duration_min=20,
            status=SlotStatus.FREE,
            purpose="intro_day",
        )
        session.add(intro_slot)
        await session.commit()
        await session.refresh(intro_slot)

    result = await reserve_slot(
        slot_id=intro_slot.id,
        candidate_tg_id=67890,
        candidate_fio="Intro Candidate 2",
        candidate_tz="Europe/Moscow",
        purpose="intro_day",
    )
    assert result.status == "reserved"
    assert result.slot is not None
    assert (result.slot.purpose or "").lower() == "intro_day"


@pytest.mark.asyncio
async def test_intro_day_booking_does_not_block_interview_booking():
    """Candidate can hold intro_day + interview for same recruiter (different purpose)."""
    async with async_session() as session:
        recruiter = Recruiter(name="Intro Rec4", tz="Europe/Moscow", active=True)
        city = City(name="Intro City4", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        intro_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=20,
            status=SlotStatus.FREE,
            purpose="intro_day",
        )
        interview_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=30,
            status=SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([intro_slot, interview_slot])
        await session.commit()
        await session.refresh(intro_slot)
        await session.refresh(interview_slot)

    candidate_tg_id = 98765
    intro_reservation = await reserve_slot(
        slot_id=intro_slot.id,
        candidate_tg_id=candidate_tg_id,
        candidate_fio="Intro Candidate 3",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
        purpose="intro_day",
    )
    assert intro_reservation.status == "reserved"

    interview_reservation = await reserve_slot(
        slot_id=interview_slot.id,
        candidate_tg_id=candidate_tg_id,
        candidate_fio="Intro Candidate 3",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
        purpose="interview",
    )
    assert interview_reservation.status == "reserved"
