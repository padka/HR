import asyncio
import importlib
import os
import sys
import time

import pytest
import pytest_asyncio
from sqlalchemy.exc import OperationalError


@pytest_asyncio.fixture(scope="session")
def event_loop_policy():
    """
    Provide pytest-asyncio with a predictable loop policy without overriding the
    built-in ``event_loop`` fixture (now deprecated in pytest-asyncio 0.23+).

    Returning the default policy keeps the plugin happy and removes the warning
    about redefining the loop fixture, while still letting us control loop scope
    when tests request ``pytest.mark.asyncio(scope="session")`` if needed.
    """
    return asyncio.DefaultEventLoopPolicy()


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
    loop.run_until_complete(db_module.init_models())
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

    for attempt in range(5):
        try:
            Base.metadata.drop_all(bind=sync_engine)
            Base.metadata.create_all(bind=sync_engine)
            break
        except OperationalError as exc:
            message = str(exc).lower()
            if "database is locked" in message and attempt < 4:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
    yield
