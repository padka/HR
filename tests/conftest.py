import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa

try:
    import uvloop  # type: ignore
except Exception:  # pragma: no cover - uvloop optional in CI images
    uvloop = None  # type: ignore

# Ensure test-safe defaults before any project modules import settings/db
if "DATABASE_URL" not in os.environ:
    _tmp = Path(tempfile.mkdtemp(prefix="rs-test-db-"))
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp/'bot.db'}"
    os.environ["DATA_DIR"] = str(_tmp)
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("RATE_LIMIT_REDIS_URL", "")


def _choose_event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    if uvloop is not None:  # type: ignore[truthy-function]
        try:
            return uvloop.EventLoopPolicy()  # type: ignore[attr-defined]
        except Exception:
            pass
    return asyncio.DefaultEventLoopPolicy()


def pytest_configure(config):  # type: ignore[override]
    config._original_event_loop_policy = asyncio.get_event_loop_policy()  # type: ignore[attr-defined]
    asyncio.set_event_loop_policy(_choose_event_loop_policy())


def pytest_unconfigure(config):  # type: ignore[override]
    original = getattr(config, "_original_event_loop_policy", None)
    if isinstance(original, asyncio.AbstractEventLoopPolicy):
        asyncio.set_event_loop_policy(original)
    else:  # pragma: no cover - defensive fallback
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def configure_backend(tmp_path_factory):
    # Stable defaults for tests: default to isolated SQLite, but allow an explicit
    # PostgreSQL-backed proof run for critical stateful scenarios.
    os.environ["ENVIRONMENT"] = "test"
    use_postgres = str(os.getenv("TEST_USE_POSTGRES", "")).strip().lower() in {"1", "true", "yes"}
    if use_postgres:
        database_url = (
            str(os.getenv("TEST_DATABASE_URL", "")).strip()
            or str(os.getenv("DATABASE_URL", "")).strip()
        )
        if not database_url.startswith("postgresql+asyncpg://"):
            raise RuntimeError(
                "TEST_USE_POSTGRES=1 requires TEST_DATABASE_URL or DATABASE_URL "
                "to use postgresql+asyncpg://"
            )
        os.environ["DATABASE_URL"] = database_url
        os.environ["TEST_DATABASE_URL"] = database_url
        os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("pg-data"))
    else:
        # Force sqlite per test session to avoid asyncpg/uvloop issues
        db_dir = tmp_path_factory.mktemp("data")
        db_path = db_dir / "bot.db"
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
        os.environ["DATA_DIR"] = str(db_dir)
        # Force integration tests to use the same SQLite URL; this skips Postgres-only
        # migration checks when a local Postgres instance is unavailable.
        os.environ["TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
    os.environ.pop("SQL_ECHO", None)
    # Allow legacy Basic auth and auto-admin in test runs for compatibility
    os.environ["ALLOW_LEGACY_BASIC"] = "1"
    os.environ["ALLOW_DEV_AUTOADMIN"] = "1"
    os.environ.setdefault("ADMIN_USER", "admin")
    os.environ.setdefault("ADMIN_PASSWORD", "admin")
    os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
    # Keep one event loop for async tests to avoid asyncpg/uvloop loop-close issues
    os.environ.setdefault("PYTEST_ASYNCIO_LOOP_SCOPE", "session")
    # Force in-memory state stores for tests to avoid external Redis flakiness
    os.environ["REDIS_URL"] = ""
    os.environ["RATE_LIMIT_REDIS_URL"] = ""

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    db_module = importlib.import_module("backend.core.db")
    importlib.reload(db_module)
    bootstrap_module = importlib.import_module("backend.core.bootstrap")
    importlib.reload(bootstrap_module)

    modules_to_reload = [
        "backend.domain.repositories",
        "backend.domain.candidates.services",
        "backend.apps.admin_ui.services",
    ]
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        else:
            importlib.import_module(module_name)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(bootstrap_module.ensure_database_ready())
    loop.close()

    yield

    loop = asyncio.new_event_loop()
    loop.run_until_complete(db_module.async_engine.dispose())
    loop.close()
    db_module.sync_engine.dispose()


@pytest.fixture(autouse=True)
def reset_settings_cache():
    from backend.core import settings as settings_module

    # Tests frequently mutate env vars before create_app(); clear the cached
    # settings object around every test so app/session/CSRF config cannot leak.
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clean_database(request):
    if request.node.get_closest_marker("no_db_cleanup") is not None:
        yield
        return

    from backend.domain.base import Base
    from backend.core.db import async_engine, sync_engine

    backend_name = sync_engine.url.get_backend_name()
    if backend_name == "postgresql":
        with sync_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            inspector = sa.inspect(conn)
            tables = [t for t in inspector.get_table_names(schema="public") if t != "alembic_version"]
            if tables:
                joined = ", ".join(f'"public"."{t}"' for t in tables)
                conn.execute(sa.text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
        Base.metadata.create_all(bind=sync_engine)
    else:
        import time
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(async_engine.dispose())
        except Exception:
            pass
        sync_engine.dispose()

        # Give background tasks a moment to release SQLite file locks
        time.sleep(0.1)

        for attempt in range(15):
            try:
                Base.metadata.drop_all(bind=sync_engine)
                break
            except sa.exc.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < 14:
                    sync_engine.dispose()
                    time.sleep(0.3 * (attempt + 1))
                    continue
                raise
        Base.metadata.create_all(bind=sync_engine)
    yield
