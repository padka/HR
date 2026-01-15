import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def notifications_feed_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


def test_notifications_feed_returns_degraded_payload_when_db_unavailable(
    notifications_feed_app,
):
    with TestClient(notifications_feed_app) as client:
        notifications_feed_app.state.db_available = False
        response = client.get(
            "/api/notifications/feed?after_id=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["latest_id"] == 10
    assert payload["degraded"] is True
