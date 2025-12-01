import asyncio
import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core import settings as settings_module
from backend.domain.candidates import services as candidate_services


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
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


async def _async_get(app, path: str):
    def _call():
        with TestClient(app) as client:
            client.auth = ("admin", "admin")
            return client.get(path)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_candidate_detail_contains_chat_widget(admin_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=101010,
        fio="Chat Candidate",
        city="Москва",
    )

    response = await _async_get(admin_app, f"/candidates/{candidate.id}")
    assert response.status_code == 200
    assert 'data-chat-root' in response.text
