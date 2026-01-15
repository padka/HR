import asyncio
import importlib
import os
import sys

import pytest

try:
    import uvloop  # type: ignore
except Exception:  # pragma: no cover - uvloop optional in CI images
    uvloop = None  # type: ignore


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
