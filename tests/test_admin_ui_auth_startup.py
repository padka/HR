import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.core import settings as settings_module


def _configure_env(monkeypatch) -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="auth-startup-"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_dir/'app.db'}")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", "")
    monkeypatch.setenv("NOTIFICATION_BROKER", "memory")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_AUTOSTART", "0")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")


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


def test_create_app_registers_auth_token_route(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/auth/token" in paths


def test_auth_token_endpoint_smoke(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    with TestClient(app) as client:
        response = client.post(
            "/auth/token",
            data={"username": "admin", "password": "admin"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
