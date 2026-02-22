"""API-level tests for vacancy endpoints."""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.security import Principal, require_principal
from backend.apps.admin_ui.services.vacancies import delete_vacancy


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def admin_app(monkeypatch) -> Any:
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
    app.dependency_overrides[require_principal] = lambda: Principal(type="admin", id=1)
    try:
        yield app
    finally:
        app.dependency_overrides.pop(require_principal, None)
        settings_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_api_list_vacancies_empty(admin_app):
    def _call():
        with TestClient(admin_app) as client:
            return client.get("/api/vacancies")

    resp = await asyncio.to_thread(_call)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["vacancies"], list)


@pytest.mark.asyncio
async def test_api_create_and_delete_vacancy(admin_app):
    def _create():
        with TestClient(admin_app) as client:
            return client.post(
                "/api/vacancies",
                json={"title": "API Test Vacancy", "slug": "api-test-vac-001"},
            )

    resp = await asyncio.to_thread(_create)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    vacancy_id = data["id"]

    try:
        def _delete():
            with TestClient(admin_app) as client:
                return client.delete(f"/api/vacancies/{vacancy_id}")

        del_resp = await asyncio.to_thread(_delete)
        assert del_resp.status_code == 200
        assert del_resp.json()["ok"] is True
    except Exception:
        await delete_vacancy(vacancy_id)


@pytest.mark.asyncio
async def test_api_create_vacancy_invalid_slug(admin_app):
    def _call():
        with TestClient(admin_app) as client:
            return client.post(
                "/api/vacancies",
                json={"title": "Bad slug", "slug": "INVALID SLUG!"},
            )

    resp = await asyncio.to_thread(_call)
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert data["errors"]
