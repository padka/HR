import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core import settings as settings_module


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def admin_app(monkeypatch):
    async def fake_setup(app):
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ALLOW_DEV_AUTOADMIN", "0")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass-123")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-0123456789abcdef0123456789abcd")
    monkeypatch.setenv("BOT_CALLBACK_SECRET", "test-bot-callback-secret-0123456789abcdef012")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


def test_api_401_does_not_advertise_basic_challenge(admin_app):
    with TestClient(admin_app) as client:
        response = client.get("/api/profile", headers={"accept": "application/json"})

    assert response.status_code == 401
    challenges = response.headers.get_list("www-authenticate")
    # No Basic challenge allowed: it triggers the browser's native auth modal.
    assert challenges, "Expected WWW-Authenticate header on 401"
    assert all(ch.lower() == "bearer" for ch in challenges), challenges
