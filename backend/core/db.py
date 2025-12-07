from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
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
logger = logging.getLogger(__name__)


def _preflight_database_backend(url: str) -> None:
    try:
        parsed = make_url(url)
    except ArgumentError as exc:  # pragma: no cover - configuration guard
        raise RuntimeError(f"Invalid DATABASE_URL: {exc}") from exc

    driver = (parsed.drivername or "").lower()
    masked_url = parsed.render_as_string(hide_password=True)
    logger.info("Database dialect: %s (%s)", driver or "unknown", masked_url)

    # Only PostgreSQL with asyncpg is supported
    if not driver.startswith("postgresql+asyncpg"):
        raise RuntimeError(
            f"Only PostgreSQL with asyncpg driver is supported. "
            f"Got: {driver}. "
            f"Set DATABASE_URL to postgresql+asyncpg://user:pass@host:port/db"
        )

    try:
        import asyncpg  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on local env
        raise RuntimeError(
            "DATABASE_URL uses postgresql+asyncpg but asyncpg is not installed. "
            "Install asyncpg: pip install asyncpg"
        ) from exc


_preflight_database_backend(_settings.database_url_async)

# Build engine kwargs with PostgreSQL pool settings
_async_engine_kwargs = {
    "echo": _settings.sql_echo,
    "future": True,
    "pool_size": _settings.db_pool_size,
    "max_overflow": _settings.db_max_overflow,
    "pool_timeout": _settings.db_pool_timeout,
    "pool_pre_ping": True,
    "pool_recycle": _settings.db_pool_recycle,
}

async_engine: AsyncEngine = create_async_engine(
    _settings.database_url_async,
    **_async_engine_kwargs,
)
_async_session_factory = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

_sync_engine_kwargs = {
    "echo": _settings.sql_echo,
    "future": True,
    "pool_size": _settings.db_pool_size,
    "max_overflow": _settings.db_max_overflow,
    "pool_timeout": _settings.db_pool_timeout,
    "pool_pre_ping": True,
    "pool_recycle": _settings.db_pool_recycle,
}

sync_engine = create_engine(
    _settings.database_url_sync,
    **_sync_engine_kwargs,
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
