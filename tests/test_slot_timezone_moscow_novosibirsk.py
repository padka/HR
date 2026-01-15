"""
Test for timezone bug: Moscow recruiter creating slot for Novosibirsk.

CRITICAL BUG REPRODUCTION:
- Recruiter in Moscow (UTC+3) creates slot at 10:00 MSK for Novosibirsk city (UTC+7)
- Expected: slot at 10:00 MSK = 07:00 UTC → candidate sees 14:00 NSK
- CURRENT BUG: slot saves at 05:00 MSK (4 hours earlier)

This test will verify the correct behavior.
"""
import pytest
from datetime import datetime, timezone

from backend.apps.admin_ui.services.slots import create_slot
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot
from sqlalchemy import select


@pytest.mark.asyncio
async def test_moscow_recruiter_slot_for_novosibirsk():
    """
    CRITICAL: Recruiter in Moscow creates slot at 10:00 for Novosibirsk candidate.

    Timeline:
    - Recruiter is in Moscow (Europe/Moscow, UTC+3)
    - City is Novosibirsk (Asia/Novosibirsk, UTC+7)
    - Recruiter inputs: 10:00 (their local time)

    Expected behavior:
    - System interprets 10:00 as Moscow time
    - Converts to UTC: 10:00 MSK → 07:00 UTC
    - Candidate sees: 07:00 UTC → 14:00 NSK (Novosibirsk time)

    CURRENT BUG (if exists):
    - System interprets 10:00 as Novosibirsk time (WRONG!)
    - Converts to UTC: 10:00 NSK → 03:00 UTC
    - Recruiter sees slot at: 03:00 UTC → 06:00 MSK (4 hours earlier!)
    """
    async with async_session() as session:
        # Create Moscow recruiter
        recruiter = Recruiter(
            name="Moscow Recruiter",
            tz="Europe/Moscow",  # UTC+3
            active=True
        )

        # Create Novosibirsk city
        city = City(
            name="Novosibirsk",
            tz="Asia/Novosibirsk",  # UTC+7
            active=True
        )

        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()

    # Recruiter creates slot at 10:00 (their local Moscow time)
    success = await create_slot(
        recruiter_id=recruiter_id,
        city_id=city_id,
        date="2030-06-15",  # Summer time: Moscow is UTC+3
        time="10:00",
    )

    assert success is True, "Slot creation should succeed"

    # Verify the slot was saved with correct UTC time
    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .where(Slot.recruiter_id == recruiter_id)
            .where(Slot.city_id == city_id)
        )

        assert slot is not None, "Slot should exist"

        # Expected: 10:00 MSK = 07:00 UTC (June 15, Moscow is UTC+3 in summer)
        expected_utc = datetime(2030, 6, 15, 7, 0, 0, tzinfo=timezone.utc)

        print(f"\n=== Timezone Debug ===")
        print(f"Recruiter input: 10:00 MSK")
        print(f"Expected UTC: {expected_utc.isoformat()}")
        print(f"Actual UTC: {slot.start_utc.isoformat()}")
        print(f"Recruiter tz: {recruiter.tz}")
        print(f"City tz: {city.tz}")
        print(f"Slot tz_name: {slot.tz_name}")
        print(f"Slot candidate_tz: {slot.candidate_tz}")

        # Convert back to verify what recruiter and candidate see
        from zoneinfo import ZoneInfo
        recruiter_local = slot.start_utc.astimezone(ZoneInfo("Europe/Moscow"))
        candidate_local = slot.start_utc.astimezone(ZoneInfo("Asia/Novosibirsk"))

        print(f"\nRecruiter sees: {recruiter_local.strftime('%H:%M')} MSK")
        print(f"Candidate sees: {candidate_local.strftime('%H:%M')} NSK")
        print(f"=====================\n")

        # CRITICAL ASSERTION
        assert slot.start_utc == expected_utc, (
            f"TIMEZONE BUG DETECTED!\n"
            f"Recruiter created slot at 10:00 MSK\n"
            f"Expected UTC: {expected_utc.isoformat()} (07:00 UTC)\n"
            f"Actual UTC: {slot.start_utc.isoformat()}\n"
            f"Recruiter would see: {recruiter_local.strftime('%H:%M')} MSK (expected 10:00)\n"
            f"Candidate would see: {candidate_local.strftime('%H:%M')} NSK (expected 14:00)"
        )

        # Verify what recruiter sees
        assert recruiter_local.hour == 10, (
            f"Recruiter should see 10:00 MSK, but sees {recruiter_local.strftime('%H:%M')}"
        )

        # Verify what candidate sees
        assert candidate_local.hour == 14, (
            f"Candidate should see 14:00 NSK, but sees {candidate_local.strftime('%H:%M')}"
        )


@pytest.mark.asyncio
async def test_moscow_recruiter_slot_at_9am():
    """
    Test the specific case mentioned: 9:00 MSK slot.

    User reported: "при создании слота на 9:00 по мск, система считает это местным
    временем по новосибирску и откатывает время слоты для рекрутера на 5:00 утра"
    """
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Novosibirsk", tz="Asia/Novosibirsk", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()

    # Create slot at 9:00 MSK
    success = await create_slot(
        recruiter_id=recruiter_id,
        city_id=city_id,
        date="2030-06-15",
        time="09:00",
    )

    assert success is True

    async with async_session() as session:
        slot = await session.scalar(
            select(Slot).where(Slot.recruiter_id == recruiter_id)
        )

        # Expected: 09:00 MSK = 06:00 UTC
        expected_utc = datetime(2030, 6, 15, 6, 0, 0, tzinfo=timezone.utc)

        from zoneinfo import ZoneInfo
        recruiter_local = slot.start_utc.astimezone(ZoneInfo("Europe/Moscow"))

        # BUG CHECK: User reports it rolls back to 05:00 MSK
        # If bug exists, slot.start_utc would be 02:00 UTC (05:00 MSK)
        # That would happen if system treated 09:00 as Novosibirsk time:
        #   09:00 NSK → 02:00 UTC → 05:00 MSK (BUG!)

        bug_utc = datetime(2030, 6, 15, 2, 0, 0, tzinfo=timezone.utc)

        if slot.start_utc == bug_utc:
            pytest.fail(
                f"TIMEZONE BUG CONFIRMED!\n"
                f"Recruiter input: 09:00 MSK\n"
                f"System saved: 02:00 UTC (interpreted as Novosibirsk time!)\n"
                f"Recruiter sees: 05:00 MSK (rolled back 4 hours)\n"
                f"Expected: 06:00 UTC (09:00 MSK)"
            )

        assert slot.start_utc == expected_utc, (
            f"Slot should be at {expected_utc.isoformat()}, "
            f"but got {slot.start_utc.isoformat()}"
        )

        assert recruiter_local.hour == 9, (
            f"Recruiter should see 09:00 MSK, not {recruiter_local.strftime('%H:%M')}"
        )
