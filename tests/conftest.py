import os
from pathlib import Path

import pytest
try:
    from fakeredis import aioredis as fakeredis_aioredis
except Exception:  # pragma: no cover - optional dependency
    fakeredis_aioredis = None
import asyncio
from sqlalchemy import text

TEST_ENV = {
    "ENVIRONMENT": "test",
    "DATABASE_URL": "sqlite+aiosqlite:///./data/test.db",
    "REDIS_URL": "",
    "REDIS_NOTIFICATIONS_URL": "",
    "NOTIFICATION_BROKER": "memory",
    "BOT_ENABLED": "0",
    "BOT_INTEGRATION_ENABLED": "0",
    "BOT_AUTOSTART": "0",
    "BOT_FAILFAST": "0",
    "ADMIN_USER": "admin",
    "ADMIN_PASSWORD": "admin",
    "SESSION_SECRET": "test-session-secret-0123456789abcdef0123456789abcd",
}

for key, value in TEST_ENV.items():
    os.environ[key] = value

from backend.domain.base import Base
from backend.core.db import async_session


@pytest.fixture(scope="session", autouse=True)
def _set_test_env():
    """Force deterministic env for tests and reset cached settings."""

    env = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "sqlite+aiosqlite:///./data/test.db",
        "REDIS_URL": "",
        "REDIS_NOTIFICATIONS_URL": "",
        "NOTIFICATION_BROKER": "memory",
        "BOT_ENABLED": "0",
        "BOT_INTEGRATION_ENABLED": "0",
        "BOT_AUTOSTART": "0",
        "BOT_FAILFAST": "0",
        "ADMIN_USER": "admin",
        "ADMIN_PASSWORD": "admin",
        "SESSION_SECRET": "test-session-secret-0123456789abcdef0123456789abcd",
    }
    for key, value in env.items():
        os.environ[key] = value

    from backend.core import settings as settings_module
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db(_set_test_env):
    """Create test DB file and apply migrations once per session."""
    Path("data").mkdir(exist_ok=True)
    db_path = Path("data/test.db")
    if db_path.exists():
        db_path.unlink()

    from backend.migrations.runner import upgrade_to_head

    upgrade_to_head("sqlite:///./data/test.db")
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
    async with async_session() as session:
        await session.execute(text("PRAGMA foreign_keys=OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()
        await session.execute(text("PRAGMA foreign_keys=ON"))


@pytest.fixture(autouse=True)
def _clean_database_between_tests(event_loop):
    """Wipe all tables before each test to avoid cross-test pollution."""
    event_loop.run_until_complete(_wipe_db())
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
