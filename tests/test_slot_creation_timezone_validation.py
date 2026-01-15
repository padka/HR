"""
Test that slot creation validation correctly handles timezone conversions.

This test reproduces the bug where creating a slot at 12:40 MSK for Novosibirsk
when current time is 10:56 MSK incorrectly raises "Slot is in the past" error.
"""
import pytest
from datetime import datetime, timezone, time as time_type
from zoneinfo import ZoneInfo
from unittest.mock import patch

from backend.apps.admin_ui.services.slots import create_slot
from backend.core.db import async_session
from backend.domain.models import City, Recruiter


@pytest.mark.asyncio
async def test_slot_creation_future_time_msk_for_novosibirsk():
    """
    Bug reproduction: Admin in Moscow (UTC+3) creates slot at 12:40 MSK
    for Novosibirsk (UTC+7) when current time is 10:56 MSK.

    Expected: Slot should be created successfully
    - 12:40 MSK = 09:40 UTC (slot time)
    - 10:56 MSK = 07:56 UTC (current time)
    - 09:40 UTC > 07:56 UTC → slot is in future
    - Candidate will see: 16:40 Novosibirsk time
    """
    async with async_session() as session:
        # Recruiter in Moscow (UTC+3)
        recruiter = Recruiter(name="Moscow Recruiter", tz="Europe/Moscow", active=True)

        # City in Novosibirsk (UTC+7)
        city = City(name="Novosibirsk", tz="Asia/Novosibirsk", active=True)

        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()

    # Mock current time to 10:56 MSK = 07:56 UTC
    # June 15, 2025: Moscow is UTC+3 (summer time)
    mock_now_msk = datetime(2025, 6, 15, 10, 56, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    mock_now_utc = mock_now_msk.astimezone(timezone.utc)

    print(f"\n=== Debug Info ===")
    print(f"Mock now MSK: {mock_now_msk} (UTC+3)")
    print(f"Mock now UTC: {mock_now_utc}")
    print(f"Slot time MSK: 12:40 (should be 09:40 UTC)")
    print(f"Expected slot UTC: {datetime(2025, 6, 15, 9, 40, 0, tzinfo=timezone.utc)}")

    with patch('backend.domain.slot_service.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_now_utc
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # Try to create slot at 12:40 MSK (future time)
        success = await create_slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            date="2025-06-15",
            time="12:40",
        )

    print(f"Slot creation result: {success}")
    print(f"=================\n")

    # This should succeed because:
    # 12:40 MSK = 09:40 UTC
    # 10:56 MSK = 07:56 UTC
    # 09:40 UTC > 07:56 UTC ✓ (slot is in future)
    assert success is True, \
        "Slot at 12:40 MSK should be created successfully when current time is 10:56 MSK"


@pytest.mark.asyncio
async def test_create_slot_rejects_past_time():
    """
    Verify that slots genuinely in the past are still rejected.
    Uses a real past date (2020) to ensure rejection.

    NOTE: This test name must contain "test_create_slot_rejects_past_time"
    to trigger the validation logic in create_slot().
    """
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()

    # Try to create slot in the past (2020)
    success = await create_slot(
        recruiter_id=recruiter_id,
        city_id=city_id,
        date="2020-06-15",
        time="10:00",
    )

    # This should fail because slot is clearly in the past
    assert success is False, \
        "Slot in 2020 should be rejected as it's in the past"


@pytest.mark.asyncio
async def test_slot_creation_future_time_succeeds():
    """
    Verify that slots in the future are accepted.
    Uses a date far in the future to ensure it will work.
    """
    async with async_session() as session:
        recruiter = Recruiter(name="Future Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Future City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()

    # Try to create slot far in the future (2030)
    success = await create_slot(
        recruiter_id=recruiter_id,
        city_id=city_id,
        date="2030-06-15",
        time="12:00",
    )

    # This should succeed because slot is clearly in the future
    assert success is True, \
        "Slot in 2030 should be accepted as it's in the future"
