from fastapi.testclient import TestClient
import pytest

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

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass-123")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


def test_form_login_accepts_env_admin_credentials(admin_app):
    with TestClient(admin_app) as client:
        response = client.post(
            "/auth/login",
            data={
                "username": "admin",
                "password": "admin-pass-123",
                "redirect_to": "/app",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/app"

        profile = client.get("/api/profile")
        assert profile.status_code == 200
        payload = profile.json()
        assert payload["principal"]["type"] == "admin"
        assert payload["principal"]["id"] == -1

