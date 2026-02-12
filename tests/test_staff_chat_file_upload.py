import asyncio
import tempfile
from pathlib import Path

import pytest
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
    tmp_dir = Path(tempfile.mkdtemp(prefix="staff-chat-"))
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


def test_staff_chat_allows_file_only_message(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()

    from backend.apps.admin_ui import app as app_module
    from backend.core.db import init_models

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    # Ensure sqlite schema is created for staff chat models.
    asyncio.run(init_models())

    with TestClient(app) as client:
        threads = client.get("/api/staff/threads").json().get("threads") or []
        assert threads, "Expected at least one default staff thread"
        thread_id = threads[0]["id"]

        resp = client.post(
            f"/api/staff/threads/{thread_id}/messages",
            files={"files": ("hello.txt", b"hello", "text/plain")},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["thread_id"] == thread_id
    assert payload["text"] in (None, "")
    assert isinstance(payload.get("attachments"), list)
    assert len(payload["attachments"]) == 1

