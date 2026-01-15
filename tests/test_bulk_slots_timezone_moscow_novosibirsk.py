"""
Test bulk slot creation with Moscow-Novosibirsk timezone scenario.
"""
import pytest
from datetime import date as date_type

from backend.apps.admin_ui.services.slots import bulk_create_slots
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot
from sqlalchemy import select


@pytest.mark.asyncio
async def test_bulk_create_moscow_to_novosibirsk():
    """
    Test bulk slot creation: Moscow recruiter creating slots for Novosibirsk.

    Scenario:
    - Recruiter in Moscow (UTC+3)
    - City is Novosibirsk (UTC+7)
    - Recruiter creates slots from 10:00 to 12:00 with 60 min steps

    Expected:
    - 10:00 MSK → 07:00 UTC
    - 11:00 MSK → 08:00 UTC
    """
    async with async_session() as session:
        recruiter = Recruiter(name="Moscow Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Novosibirsk", tz="Asia/Novosibirsk", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()

    # Bulk create slots from 10:00 to 12:00 (2 slots: 10:00, 11:00)
    created, error = await bulk_create_slots(
        recruiter_id=recruiter_id,
        city_id=city_id,
        start_date="2030-06-15",
        end_date="2030-06-15",
        start_time="10:00",
        end_time="12:00",
        break_start="13:00",
        break_end="14:00",
        step_min=60,
        include_weekends=True,
        use_break=False,
    )

    assert error is None, f"Bulk create failed: {error}"
    assert created == 2, f"Expected 2 slots, got {created}"

    # Verify slots have correct UTC times
    async with async_session() as session:
        slots = (await session.scalars(
            select(Slot)
            .where(Slot.recruiter_id == recruiter_id)
            .order_by(Slot.start_utc)
        )).all()

        assert len(slots) == 2

        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo

        # First slot: 10:00 MSK = 07:00 UTC
        slot1 = slots[0]
        expected_utc_1 = datetime(2030, 6, 15, 7, 0, 0, tzinfo=timezone.utc)

        print(f"\n=== Bulk Create Debug ===")
        print(f"Slot 1 UTC: {slot1.start_utc.isoformat()}")
        print(f"Expected: {expected_utc_1.isoformat()}")

        recruiter_time_1 = slot1.start_utc.astimezone(ZoneInfo("Europe/Moscow"))
        print(f"Recruiter sees: {recruiter_time_1.strftime('%H:%M')} MSK")

        assert slot1.start_utc == expected_utc_1, (
            f"First slot wrong UTC: {slot1.start_utc.isoformat()}, "
            f"expected {expected_utc_1.isoformat()}"
        )

        assert recruiter_time_1.hour == 10, (
            f"Recruiter should see 10:00, got {recruiter_time_1.strftime('%H:%M')}"
        )

        # Second slot: 11:00 MSK = 08:00 UTC
        slot2 = slots[1]
        expected_utc_2 = datetime(2030, 6, 15, 8, 0, 0, tzinfo=timezone.utc)

        recruiter_time_2 = slot2.start_utc.astimezone(ZoneInfo("Europe/Moscow"))
        print(f"Slot 2 UTC: {slot2.start_utc.isoformat()}")
        print(f"Expected: {expected_utc_2.isoformat()}")
        print(f"Recruiter sees: {recruiter_time_2.strftime('%H:%M')} MSK")
        print(f"========================\n")

        assert slot2.start_utc == expected_utc_2
        assert recruiter_time_2.hour == 11


@pytest.mark.asyncio
async def test_bulk_create_at_9am():
    """
    Specific test for the 9:00 AM case mentioned by user.
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

    # Create single slot at 9:00
    created, error = await bulk_create_slots(
        recruiter_id=recruiter_id,
        city_id=city_id,
        start_date="2030-06-15",
        end_date="2030-06-15",
        start_time="09:00",
        end_time="10:00",
        break_start="12:00",
        break_end="13:00",
        step_min=60,
        include_weekends=True,
        use_break=False,
    )

    assert error is None
    assert created == 1

    async with async_session() as session:
        slot = await session.scalar(
            select(Slot).where(Slot.recruiter_id == recruiter_id)
        )

        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo

        # Expected: 09:00 MSK = 06:00 UTC
        expected_utc = datetime(2030, 6, 15, 6, 0, 0, tzinfo=timezone.utc)

        # BUG would be: 09:00 interpreted as NSK → 02:00 UTC
        bug_utc = datetime(2030, 6, 15, 2, 0, 0, tzinfo=timezone.utc)

        if slot.start_utc == bug_utc:
            pytest.fail(
                f"BUG in bulk_create_slots!\n"
                f"09:00 MSK was interpreted as Novosibirsk time\n"
                f"Saved as: 02:00 UTC instead of 06:00 UTC"
            )

        recruiter_time = slot.start_utc.astimezone(ZoneInfo("Europe/Moscow"))

        assert slot.start_utc == expected_utc, (
            f"Slot UTC wrong: {slot.start_utc.isoformat()}, "
            f"expected {expected_utc.isoformat()}"
        )

        assert recruiter_time.hour == 9, (
            f"Recruiter should see 09:00, got {recruiter_time.strftime('%H:%M')}"
        )
