"""Tests for slot timezone validation."""

from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import StatementError

from backend.core.db import async_session
from backend.domain.models import Recruiter, City, Slot, SlotStatus


@pytest.mark.asyncio
async def test_slot_valid_timezone():
    """Test that valid IANA timezones are accepted for slots."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/London", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Create slot with valid timezone
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="America/New_York",  # Valid IANA timezone
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()  # Should succeed

        await session.refresh(slot)
        assert slot.tz_name == "America/New_York"


@pytest.mark.asyncio
async def test_slot_invalid_timezone():
    """Test that invalid timezones are rejected for slots."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Try to create slot with invalid timezone
        # Should raise error at object creation
        with pytest.raises(ValueError, match="Invalid timezone"):
            slot = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name="Invalid/Timezone",  # Invalid timezone
                start_utc=datetime.now(timezone.utc),
                duration_min=60,
                status=SlotStatus.FREE,
            )


@pytest.mark.asyncio
async def test_slot_empty_timezone():
    """Test that empty timezone is rejected."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Try to create slot with empty timezone
        with pytest.raises(ValueError, match="Timezone cannot be empty"):
            slot = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name="",  # Empty string
                start_utc=datetime.now(timezone.utc),
                duration_min=60,
                status=SlotStatus.FREE,
            )


@pytest.mark.asyncio
async def test_candidate_timezone_valid():
    """Test that valid candidate timezone is accepted."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=SlotStatus.FREE,
            candidate_tz="Asia/Tokyo",  # Valid timezone
        )
        session.add(slot)
        await session.commit()

        await session.refresh(slot)
        assert slot.candidate_tz == "Asia/Tokyo"


@pytest.mark.asyncio
async def test_candidate_timezone_invalid():
    """Test that invalid candidate timezone is rejected."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        # Try to set invalid candidate timezone - should raise at object creation
        with pytest.raises(ValueError, match="Invalid timezone"):
            slot = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name="Europe/Moscow",
                start_utc=datetime.now(timezone.utc),
                duration_min=60,
                status=SlotStatus.FREE,
                candidate_tz="BadTimezone",  # Invalid
            )


@pytest.mark.asyncio
async def test_candidate_timezone_none():
    """Test that None candidate timezone is allowed."""
    async with async_session() as session:
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        city = City(name="Test City", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        session.add(city)
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name="Europe/Moscow",
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=SlotStatus.FREE,
            candidate_tz=None,  # None is allowed
        )
        session.add(slot)
        await session.commit()

        await session.refresh(slot)
        assert slot.candidate_tz is None


@pytest.mark.asyncio
async def test_recruiter_timezone_validation():
    """Test that recruiter timezone is validated."""
    async with async_session() as session:
        # Valid timezone
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()

        await session.refresh(recruiter)
        assert recruiter.tz == "Europe/Moscow"


@pytest.mark.asyncio
async def test_recruiter_invalid_timezone():
    """Test that invalid recruiter timezone is rejected."""
    async with async_session() as session:
        # Invalid timezone - should raise at object creation
        with pytest.raises(ValueError, match="Invalid timezone"):
            recruiter = Recruiter(name="Test Recruiter", tz="BadTimeZone", active=True)


@pytest.mark.asyncio
async def test_city_timezone_validation():
    """Test that city timezone is validated."""
    async with async_session() as session:
        # Valid timezone
        city = City(name="Test City", tz="America/Chicago", active=True)
        session.add(city)
        await session.commit()

        await session.refresh(city)
        assert city.tz == "America/Chicago"


@pytest.mark.asyncio
async def test_city_invalid_timezone():
    """Test that invalid city timezone is rejected."""
    async with async_session() as session:
        # Invalid timezone - should raise at object creation
        with pytest.raises(ValueError, match="Invalid timezone"):
            city = City(name="Test City", tz="InvalidTimezone", active=True)
