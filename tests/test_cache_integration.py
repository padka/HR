"""Integration tests for Phase 2 Performance Cache."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

from backend.core.cache import CacheConfig, init_cache, connect_cache, get_cache
from backend.core.uow import UnitOfWork
from backend.domain.models import Slot, SlotStatus, Recruiter, City


@pytest.mark.asyncio
async def test_cache_initialization():
    """Test that cache can be initialized and connected."""
    config = CacheConfig(
        host="localhost",
        port=6379,
        max_connections=10,
    )

    # Mock Redis to avoid actual connection
    with patch("backend.core.cache.Redis") as MockRedis:
        mock_client = AsyncMock()
        MockRedis.return_value = mock_client

        init_cache(config)
        cache = get_cache()

        await cache.connect()

        assert cache is not None
        assert cache._client is not None


@pytest.mark.asyncio
async def test_slot_repository_uses_cache():
    """
    Test that SlotRepository.get() uses cache decorator.

    This verifies Phase 2 performance optimization is actually working.
    """
    from backend.repositories.slot import SlotRepository
    from backend.core.db import async_session

    # Check that get method has cached decorator
    assert hasattr(SlotRepository.get, "__wrapped__"), (
        "SlotRepository.get should be decorated with @cached"
    )

    # Create test data
    async with async_session() as session:
        city = City(name="Test City", tz="UTC", active=True)
        recruiter = Recruiter(name="Test Recruiter", tz="UTC", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    # Mock cache to verify it's being called
    with patch("backend.core.cache_decorators.get_cache") as mock_get_cache:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=AsyncMock(is_success=lambda: True, unwrap=lambda: None))
        mock_cache.set = AsyncMock(return_value=AsyncMock(is_success=lambda: True))
        mock_get_cache.return_value = mock_cache

        # Query slot through UnitOfWork
        async with UnitOfWork() as uow:
            result = await uow.slots.get(slot_id)

        # Verify cache was attempted
        assert mock_cache.get.called or mock_cache.set.called, (
            "Cache should be accessed when querying slots"
        )


@pytest.mark.asyncio
async def test_cache_health_check():
    """Test that cache health check works."""
    # Mock cache
    with patch("backend.core.cache.get_cache") as mock_get_cache:
        mock_cache = AsyncMock()
        mock_cache.exists = AsyncMock(return_value=AsyncMock(is_success=lambda: True))
        mock_get_cache.return_value = mock_cache

        from backend.apps.admin_ui.routers.system import health_check
        from fastapi import Request

        # Create mock request
        request = Mock(spec=Request)
        request.app = Mock()
        request.app.state = Mock()
        request.app.state.state_manager = Mock()
        request.app.state.bot_service = None
        request.app.state.bot_integration_switch = None

        # Mock database
        with patch("backend.apps.admin_ui.routers.system.async_session"):
            response = await health_check(request)

        # Verify cache check was included
        data = response.body.decode()
        assert "cache" in data, "Health check should include cache status"


@pytest.mark.asyncio
async def test_cache_disabled_gracefully():
    """Test that application works when cache is disabled."""
    from backend.core.uow import UnitOfWork
    from backend.core.db import async_session

    # Create test data without cache
    async with async_session() as session:
        city = City(name="Test City 2", tz="UTC", active=True)
        recruiter = Recruiter(name="Test Recruiter 2", tz="UTC", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    # Mock cache.get to raise RuntimeError (not initialized)
    with patch("backend.core.cache_decorators.get_cache", side_effect=RuntimeError("Cache not initialized")):
        # Should still work without cache
        async with UnitOfWork() as uow:
            result = await uow.slots.get(slot_id)

        # Should return result even without cache
        assert result.is_success(), "Should work without cache (graceful degradation)"


def test_cache_keys_pattern():
    """Test that cache key builders follow consistent pattern."""
    from backend.core.cache import CacheKeys

    # Test recruiter keys
    assert CacheKeys.recruiter(1) == "recruiter:1"
    assert CacheKeys.recruiters_active() == "recruiters:active"
    assert CacheKeys.recruiters_for_city(5) == "recruiters:city:5"

    # Test slot keys
    assert CacheKeys.slot(10) == "slot:10"
    assert CacheKeys.slots_free_for_recruiter(3) == "slots:free:recruiter:3"

    # Test city keys
    assert CacheKeys.city(2) == "city:2"
    assert CacheKeys.cities_active() == "cities:active"


def test_cache_ttl_values():
    """Test that cache TTL values are reasonable."""
    from backend.core.cache import CacheTTL

    # Verify TTL values are in expected ranges
    assert CacheTTL.SHORT.total_seconds() == 300  # 5 minutes
    assert CacheTTL.MEDIUM.total_seconds() == 1800  # 30 minutes
    assert CacheTTL.LONG.total_seconds() == 7200  # 2 hours
    assert CacheTTL.VERY_LONG.total_seconds() == 86400  # 24 hours

    # Verify SHORT < MEDIUM < LONG < VERY_LONG
    assert CacheTTL.SHORT < CacheTTL.MEDIUM < CacheTTL.LONG < CacheTTL.VERY_LONG
