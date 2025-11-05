"""FastAPI dependency injection for database access.

Provides per-request AsyncSession and UnitOfWork instances with automatic
cleanup and transaction management.
"""

from typing import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import new_async_session
from backend.core.uow import UnitOfWork


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency to provide AsyncSession per request.

    Usage:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()

    Features:
    - Creates new session per request
    - Automatic rollback on exceptions
    - Automatic cleanup after request

    Yields:
        AsyncSession instance for this request
    """
    session = new_async_session()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_uow(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncIterator[UnitOfWork]:
    """
    FastAPI dependency to provide UnitOfWork per request.

    Usage:
        @router.post("/items")
        async def create_item(
            data: ItemCreate,
            uow: UnitOfWork = Depends(get_uow)
        ):
            item = Item(**data.dict())
            result = await uow.items.add(item)
            await uow.commit()
            return result.unwrap()

    Features:
    - Uses shared session from get_async_session dependency
    - Automatic rollback on exceptions (via session dependency)
    - Access to all repositories via uow.repos
    - Explicit commit required (no auto-commit)

    Yields:
        UnitOfWork instance for this request
    """
    # Create UnitOfWork with the request's session
    uow = UnitOfWork(session=session)

    # Initialize repositories (enters context manager)
    async with uow:
        yield uow
        # Note: No auto-commit here - services must call uow.commit() explicitly


# Type aliases for dependency injection
AsyncSessionDep = Depends(get_async_session)
UnitOfWorkDep = Depends(get_uow)
