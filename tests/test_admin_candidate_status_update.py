import pytest

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


async def _async_post(app, path: str, data: dict):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        return await client.post(path, data=data, follow_redirects=False)


@pytest.mark.asyncio
async def test_invalid_status_redirects_back(monkeypatch, admin_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=1234567,
        fio="Invalid Status",
        city="Москва",
    )

    response = await _async_post(
        admin_app,
        f"/candidates/{candidate.id}/status",
        {"status": "bad_status", "csrf_token": "token"},
    )

    assert response.status_code == 303
    assert f"/candidates/{candidate.id}?error=invalid_status" in response.headers["Location"]


@pytest.mark.asyncio
async def test_interview_declined_uses_status_service(monkeypatch, admin_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=2233445,
        fio="Decline Me",
        city="Москва",
    )

    called = {}

    async def fake_decline(tg_id):
        called["tg"] = tg_id
        return True

    monkeypatch.setattr(
        "backend.apps.admin_ui.routers.candidates.set_status_interview_declined",
        fake_decline,
    )

    response = await _async_post(
        admin_app,
        f"/candidates/{candidate.id}/status",
        {"status": "interview_declined", "csrf_token": "token"},
    )

    assert response.status_code == 303
    assert f"/candidates/{candidate.id}?ok=1" in response.headers["Location"]
    assert called.get("tg") == candidate.telegram_id
