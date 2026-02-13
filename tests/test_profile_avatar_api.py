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


def _login_admin(client: TestClient) -> None:
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


def test_profile_avatar_upload_and_delete(admin_app):
    with TestClient(admin_app) as client:
        _login_admin(client)

        csrf = client.get("/api/csrf")
        assert csrf.status_code == 200
        token = csrf.json()["token"]

        upload = client.post(
            "/api/profile/avatar",
            files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "image/png")},
            headers={"x-csrf-token": token},
        )
        assert upload.status_code == 200
        assert upload.json()["ok"] is True

        profile = client.get("/api/profile")
        assert profile.status_code == 200
        assert profile.json()["avatar_url"]

        fetch_avatar = client.get("/api/profile/avatar")
        assert fetch_avatar.status_code == 200

        deleted = client.delete("/api/profile/avatar", headers={"x-csrf-token": token})
        assert deleted.status_code == 200
        assert deleted.json()["ok"] is True

        profile_after = client.get("/api/profile")
        assert profile_after.status_code == 200
        assert profile_after.json()["avatar_url"] is None

        missing = client.get("/api/profile/avatar")
        assert missing.status_code == 404

