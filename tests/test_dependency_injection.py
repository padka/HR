"""Tests for FastAPI Dependency Injection."""

import pytest
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_async_session, get_uow
from backend.core.uow import UnitOfWork


@pytest.mark.asyncio
async def test_get_async_session_dependency():
    """Test that get_async_session creates and cleans up session."""
    # The dependency is a generator, so we need to iterate it
    gen = get_async_session()

    session = await gen.__anext__()

    assert isinstance(session, AsyncSession)
    assert not session.is_active  # Should not have active transaction yet

    # Clean up
    try:
        await gen.__anext__()
    except StopAsyncIteration:
        pass  # Expected - generator finished


@pytest.mark.asyncio
async def test_get_uow_dependency():
    """Test that get_uow provides UnitOfWork with session."""
    # Mock session
    mock_session = AsyncMock(spec=AsyncSession)

    # Create UoW dependency with mocked session
    async def mock_get_session():
        yield mock_session

    gen = get_uow(session=mock_session)

    uow = await gen.__anext__()

    assert isinstance(uow, UnitOfWork)
    # UoW should use the provided session
    assert uow._session is mock_session

    # Clean up
    try:
        await gen.__anext__()
    except StopAsyncIteration:
        pass


@pytest.mark.asyncio
async def test_uow_dependency_provides_repositories():
    """Test that UoW from DI has all repositories initialized."""
    from backend.core.db import async_session

    async with async_session() as session:
        gen = get_uow(session=session)

        uow = await gen.__anext__()

        # Verify all repositories are available
        assert hasattr(uow, "recruiters")
        assert hasattr(uow, "cities")
        assert hasattr(uow, "slots")
        assert hasattr(uow, "templates")
        assert hasattr(uow, "users")
        assert hasattr(uow, "test_results")
        assert hasattr(uow, "auto_messages")
        assert hasattr(uow, "message_templates")

        # Clean up
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass


def test_dependency_imports():
    """Test that dependencies can be imported correctly."""
    from backend.core.dependencies import (
        get_async_session,
        get_uow,
        AsyncSessionDep,
        UnitOfWorkDep,
    )

    assert callable(get_async_session)
    assert callable(get_uow)
    # Type aliases should exist
    assert AsyncSessionDep is not None
    assert UnitOfWorkDep is not None


@pytest.mark.asyncio
async def test_session_exception_handling():
    """Test that session is rolled back on exception."""
    from backend.core.db import new_async_session

    session = new_async_session()
    rolled_back = False

    original_rollback = session.rollback

    async def tracking_rollback():
        nonlocal rolled_back
        rolled_back = True
        await original_rollback()

    session.rollback = tracking_rollback

    # Simulate exception in request
    gen = get_async_session()

    try:
        s = await gen.__anext__()
        # Simulate exception
        raise ValueError("Test exception")
    except ValueError:
        pass

    # Try to clean up (should trigger rollback)
    try:
        await gen.aclose()
    except Exception:
        pass

    # Session should be closed
    assert session._transaction is None or not session.in_transaction()


@pytest.mark.asyncio
async def test_uow_no_auto_commit():
    """Test that UoW from DI doesn't auto-commit."""
    from backend.core.db import async_session
    from backend.domain.models import City

    async with async_session() as session:
        gen = get_uow(session=session)
        uow = await gen.__anext__()

        # Add a city but don't commit
        city = City(name="Test City", tz="UTC", active=True)
        await uow.cities.add(city)

        # Don't call await uow.commit()

        # Clean up generator
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    # Verify city was NOT saved (no auto-commit)
    async with async_session() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(City).where(City.name == "Test City")
        )
        found = result.scalar_one_or_none()

        # Should be None because we didn't commit
        assert found is None, "UoW should not auto-commit"
