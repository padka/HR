import asyncio
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.core import settings as settings_module


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


async def _fake_setup_bot_state(app):
    app.state.bot = None
    app.state.state_manager = None
    app.state.bot_service = None
    app.state.bot_integration_switch = None
    app.state.reminder_service = None
    app.state.notification_service = None
    app.state.notification_broker_available = False
    return _DummyIntegration()


def _configure_env(monkeypatch) -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="staff-chat-updates-"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("BOT_CALLBACK_SECRET", "test-bot-callback-secret-0123456789abcdef012")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_dir/'app.db'}")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", "")
    monkeypatch.setenv("NOTIFICATION_BROKER", "memory")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_AUTOSTART", "0")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")


def test_staff_threads_updates_handles_naive_latest_event_at(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()

    from backend.apps.admin_ui import app as app_module
    from backend.core.db import init_models

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)

    async def _fake_list_threads(_principal):
        # Historically sqlite could return naive datetimes, so list_threads()
        # might emit latest_event_at without timezone info.
        return {"threads": [], "latest_event_at": "2026-02-13T12:00:00"}

    from backend.apps.admin_ui.services import staff_chat as staff_chat_module

    monkeypatch.setattr(staff_chat_module, "list_threads", _fake_list_threads)

    app = app_module.create_app()
    asyncio.run(init_models())

    with TestClient(app) as client:
        resp = client.get(
            "/api/staff/threads/updates",
            params={"since": "2026-02-13T11:00:00+00:00", "timeout": 5},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["updated"] is True

