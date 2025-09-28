from __future__ import annotations
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from backend.core.settings import get_settings
from backend.migrations import upgrade_to_head

_settings = get_settings()

async_engine: AsyncEngine = create_async_engine(
    _settings.database_url_async,
    echo=_settings.sql_echo,
    future=True,
)
_async_session_factory = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

sync_engine = create_engine(
    _settings.database_url_sync,
    echo=_settings.sql_echo,
    future=True,
)
_sync_session_factory = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
    class_=Session,
)


async def init_models() -> None:
    """Initialise the database by applying all migrations."""

    await asyncio.to_thread(upgrade_to_head, sync_engine)


def new_async_session() -> AsyncSession:
    """Return a raw AsyncSession instance."""
    return _async_session_factory()


@asynccontextmanager
async def async_session() -> AsyncIterator[AsyncSession]:
    session = new_async_session()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def new_sync_session() -> Session:
    """Return a raw synchronous Session instance."""
    return _sync_session_factory()


@contextmanager
def sync_session() -> Iterator[Session]:
    session = new_sync_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "async_session",
    "new_async_session",
    "sync_session",
    "new_sync_session",
    "init_models",
    "async_engine",
    "sync_engine",
]
