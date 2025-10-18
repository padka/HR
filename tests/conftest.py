import asyncio
import importlib
import os
import sys

import pytest

try:  # pragma: no cover - exercised implicitly during test collection
    import uvloop  # type: ignore
except Exception:  # pragma: no cover - falls back when uvloop is absent
    uvloop = None  # type: ignore[assignment]
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
else:  # pragma: no cover - executed when uvloop is available
    uvloop.install()


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    if uvloop is not None:  # type: ignore[name-defined]
        return uvloop.EventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session", autouse=True)
def configure_event_loop_policy(event_loop_policy: asyncio.AbstractEventLoopPolicy):
    asyncio.set_event_loop_policy(event_loop_policy)
    loop = event_loop_policy.new_event_loop()
    event_loop_policy.set_event_loop(loop)
    try:
        yield event_loop_policy
    finally:
        if not loop.is_closed():
            loop.close()
        asyncio.set_event_loop(None)
        asyncio.set_event_loop_policy(None)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def configure_backend(tmp_path_factory):
    db_dir = tmp_path_factory.mktemp("data")
    db_path = db_dir / "bot.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["DATA_DIR"] = str(db_dir)
    os.environ.pop("SQL_ECHO", None)

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
def clean_database():
    from backend.domain.base import Base
    from backend.core.db import sync_engine

    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)
    yield
