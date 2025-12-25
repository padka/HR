import os
from pathlib import Path

import pytest
try:
    from fakeredis import aioredis as fakeredis_aioredis
except Exception:  # pragma: no cover - optional dependency
    fakeredis_aioredis = None
import asyncio
from sqlalchemy import text

# PostgreSQL test database configuration
# Override with TEST_DATABASE_URL environment variable if needed
DEFAULT_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://rs:pass@localhost:5432/rs_test"
)

TEST_ENV = {
    "ENVIRONMENT": "test",
    "DATABASE_URL": DEFAULT_TEST_DB_URL,
    "REDIS_URL": "",
    "REDIS_NOTIFICATIONS_URL": "",
    "NOTIFICATION_BROKER": "memory",
    "RATE_LIMIT_ENABLED": "false",
    "BOT_ENABLED": "0",
    "BOT_INTEGRATION_ENABLED": "0",
    "BOT_AUTOSTART": "0",
    "BOT_FAILFAST": "0",
    "ADMIN_USER": "admin",
    "ADMIN_PASSWORD": "admin",
    "SESSION_SECRET": "test-session-secret-0123456789abcdef0123456789abcd",
    # Reduce DB pool size for tests to prevent "too many open files"
    "DB_POOL_SIZE": "5",
    "DB_MAX_OVERFLOW": "2",
    "DB_POOL_TIMEOUT": "10",
    "DB_POOL_RECYCLE": "300",
}

for key, value in TEST_ENV.items():
    os.environ[key] = value

from backend.domain.base import Base
from backend.core.db import async_session


@pytest.fixture(scope="session", autouse=True)
def _set_test_env():
    """Force deterministic env for tests and reset cached settings."""

    # Use same TEST_ENV dict to avoid duplication
    for key, value in TEST_ENV.items():
        os.environ[key] = value

    from backend.core import settings as settings_module
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db(_set_test_env):
    """Apply migrations once per session to test database."""
    from backend.migrations.runner import upgrade_to_head

    # Convert asyncpg URL to psycopg2 for sync migrations
    sync_db_url = DEFAULT_TEST_DB_URL.replace("+asyncpg", "")
    upgrade_to_head(sync_db_url)
    yield


@pytest.fixture(scope="session", autouse=True)
def _force_test_settings(_set_test_env):
    """Reset settings cache and bot state to avoid accidental Redis usage."""
    from backend.core import settings as settings_module
    settings_module.get_settings.cache_clear()
    settings = settings_module.get_settings()

    try:
        from backend.apps.bot import services as bot_services
        from backend.apps.bot.state_store import build_state_manager
        from backend.apps.admin_ui.config import register_template_globals

        bot_services._bot = None
        bot_services._state_manager = build_state_manager(
            redis_url=None,
            ttl_seconds=getattr(settings, "state_ttl_seconds", 604800),
        )
        register_template_globals()
    except Exception:
        pass
    yield
    settings_module.get_settings.cache_clear()


async def _wipe_db():
    """Wipe all tables using DELETE for PostgreSQL compatibility."""
    async with async_session() as session:
        # Delete data from all tables in reverse order (respecting foreign keys)
        for table in reversed(Base.metadata.sorted_tables):
            try:
                await session.execute(table.delete())
            except Exception:
                # If table doesn't exist yet, ignore
                pass
        await session.commit()


@pytest.fixture(autouse=True)
async def _clean_database_between_tests(request):
    """Wipe all tables before each test to avoid cross-test pollution."""
    # Skip database cleanup for tests that don't use the database
    if "no_db_cleanup" in request.keywords:
        return

    # Run cleanup as async to stay in the same event loop
    await _wipe_db()
    try:
        from backend.apps.bot.services import reset_template_provider
        reset_template_provider()
    except Exception:
        pass


@pytest.fixture(scope="session")
def fake_redis():
    """Provide a fake Redis client for tests that need it."""
    if fakeredis_aioredis is None:
        pytest.skip("fakeredis is not available")
    return fakeredis_aioredis.FakeRedis()


@pytest.fixture(scope="session")
def redis_url():
    """Provide Redis URL for integration tests."""
    return os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")
