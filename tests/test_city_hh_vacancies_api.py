from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from backend.apps.admin_ui.security import Principal, require_admin
from backend.core.db import async_session
from backend.domain.hh_integration.client import HHApiError
from backend.domain.hh_integration.crypto import HHSecretCipher
from backend.domain.hh_integration.models import ExternalVacancyBinding, HHConnection
from backend.domain.models import City, Vacancy
from fastapi.testclient import TestClient


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def hh_env(monkeypatch):
    monkeypatch.setenv("HH_INTEGRATION_ENABLED", "1")
    monkeypatch.setenv("HH_CLIENT_ID", "hh-client")
    monkeypatch.setenv("HH_CLIENT_SECRET", "hh-secret")
    monkeypatch.setenv("HH_REDIRECT_URI", "https://crm.example.com/api/integrations/hh/oauth/callback")
    monkeypatch.setenv("HH_WEBHOOK_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("HH_USER_AGENT", "RecruitSmartTest/1.0 (qa@example.com)")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest.fixture
def admin_app(monkeypatch, hh_env):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from backend.apps.admin_ui.app import create_app
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    app.dependency_overrides[require_admin] = lambda: Principal(type="admin", id=1)
    try:
        yield app
    finally:
        app.dependency_overrides.pop(require_admin, None)
        settings_module.get_settings.cache_clear()


async def _seed_city_hh_binding(*, archived: bool = False) -> int:
    cipher = HHSecretCipher()
    async with async_session() as session:
        city = City(name="Астрахань", tz="Europe/Moscow")
        session.add(city)
        await session.flush()

        vacancy = Vacancy(title="Стажер в компанию", slug="astrakhan-intern", city_id=city.id, is_active=True)
        session.add(vacancy)
        await session.flush()

        connection = HHConnection(
            principal_type="admin",
            principal_id=1,
            employer_id="emp-1",
            manager_account_id="acc-42",
            manager_id="mgr-1",
            access_token_encrypted=cipher.encrypt("access-123"),
            refresh_token_encrypted=cipher.encrypt("refresh-456"),
            webhook_url_key="city-hh-key",
            profile_payload={},
        )
        session.add(connection)
        await session.flush()

        session.add(
            ExternalVacancyBinding(
                vacancy_id=vacancy.id,
                connection_id=connection.id,
                source="hh",
                external_vacancy_id="131018950",
                external_url="https://hh.ru/vacancy/131018950",
                title_snapshot="Стажер в компанию (Услуги Яндекс)",
                payload_snapshot={"id": "131018950", "name": "Стажер в компанию (Услуги Яндекс)", "archived": archived},
            )
        )
        await session.commit()
        return city.id


async def _seed_city_with_unbound_hh_vacancy() -> int:
    cipher = HHSecretCipher()
    async with async_session() as session:
        city = City(name="Алматы", tz="Asia/Almaty")
        session.add(city)
        await session.flush()

        connection = HHConnection(
            principal_type="admin",
            principal_id=1,
            employer_id="emp-1",
            manager_account_id="acc-42",
            manager_id="mgr-1",
            access_token_encrypted=cipher.encrypt("access-123"),
            refresh_token_encrypted=cipher.encrypt("refresh-456"),
            webhook_url_key="city-hh-almaty-key",
            profile_payload={},
        )
        session.add(connection)
        await session.flush()

        session.add(
            ExternalVacancyBinding(
                vacancy_id=None,
                connection_id=connection.id,
                source="hh",
                external_vacancy_id="130662409",
                external_url="https://hh.ru/vacancy/130662409",
                title_snapshot="Стажер в компанию (Услуги Google)",
                payload_snapshot={
                    "id": "130662409",
                    "name": "Стажер в компанию (Услуги Google)",
                    "area": {"name": "Алматы"},
                },
            )
        )
        await session.commit()
        return city.id


async def _seed_city_without_hh_binding() -> int:
    cipher = HHSecretCipher()
    async with async_session() as session:
        city = City(name="Алматы", tz="Asia/Almaty")
        session.add(city)
        await session.flush()

        connection = HHConnection(
            principal_type="admin",
            principal_id=1,
            employer_id="emp-1",
            manager_account_id="acc-42",
            manager_id="mgr-1",
            access_token_encrypted=cipher.encrypt("access-123"),
            refresh_token_encrypted=cipher.encrypt("refresh-456"),
            webhook_url_key="city-hh-almaty-live-key",
            profile_payload={},
        )
        session.add(connection)
        await session.commit()
        return city.id


class TestCityHHVacanciesApi:
    @pytest.mark.asyncio
    async def test_city_hh_vacancies_returns_live_status(self, admin_app):
        city_id = await _seed_city_hh_binding()

        def _call():
            with patch("backend.apps.admin_ui.services.cities_hh.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_vacancies.side_effect = [
                    {
                        "items": [
                            {
                                "id": "131018950",
                                "name": "Стажер в компанию (Услуги Яндекс)",
                                "url": "https://hh.ru/vacancy/131018950",
                            }
                        ],
                        "pages": 1,
                    }
                ]
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    return client.get(f"/api/cities/{city_id}/hh-vacancies")

        response = await asyncio.to_thread(_call)
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["items"][0]["status"] == "published"
        assert body["items"][0]["status_source"] == "live_api"
        assert body["items"][0]["external_vacancy_id"] == "131018950"

    @pytest.mark.asyncio
    async def test_city_hh_vacancies_falls_back_to_snapshot(self, admin_app):
        city_id = await _seed_city_hh_binding(archived=True)

        def _call():
            with patch("backend.apps.admin_ui.services.cities_hh.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_vacancies.side_effect = HHApiError("HH API 502", status_code=502)
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    return client.get(f"/api/cities/{city_id}/hh-vacancies")

        response = await asyncio.to_thread(_call)
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["api_error"] == "HH API 502"
        assert body["items"][0]["status"] == "archived"
        assert body["items"][0]["status_source"] == "snapshot"

    @pytest.mark.asyncio
    async def test_city_hh_vacancies_includes_unbound_hh_city_match(self, admin_app):
        city_id = await _seed_city_with_unbound_hh_vacancy()

        def _call():
            with patch("backend.apps.admin_ui.services.cities_hh.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_vacancies.side_effect = [
                    {
                        "items": [
                            {
                                "id": "130662409",
                                "name": "Стажер в компанию (Услуги Google)",
                                "url": "https://hh.ru/vacancy/130662409",
                            }
                        ],
                        "pages": 1,
                    }
                ]
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    return client.get(f"/api/cities/{city_id}/hh-vacancies")

        response = await asyncio.to_thread(_call)
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert len(body["items"]) == 1
        assert body["items"][0]["external_vacancy_id"] == "130662409"
        assert body["items"][0]["status"] == "published"
        assert body["items"][0]["status_source"] == "live_api"
        assert body["items"][0]["local_vacancy_linked"] is False
        assert "без привязки к CRM" in body["items"][0]["status_label"]

    @pytest.mark.asyncio
    async def test_city_hh_vacancies_discovers_live_city_vacancy_without_binding(self, admin_app):
        city_id = await _seed_city_without_hh_binding()

        def _call():
            with patch("backend.apps.admin_ui.services.cities_hh.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_vacancies.side_effect = [
                    {
                        "items": [
                            {
                                "id": "130662409",
                                "name": "Стажер в компанию (Услуги Google)",
                                "url": "https://hh.ru/vacancy/130662409",
                                "area": {"name": "Алматы"},
                            }
                        ],
                        "pages": 1,
                    }
                ]
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    return client.get(f"/api/cities/{city_id}/hh-vacancies")

        response = await asyncio.to_thread(_call)
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert len(body["items"]) == 1
        assert body["items"][0]["external_vacancy_id"] == "130662409"
        assert body["items"][0]["status"] == "published"
        assert body["items"][0]["status_source"] == "live_api"
        assert body["items"][0]["local_vacancy_linked"] is False
        assert "без привязки к CRM" in body["items"][0]["status_label"]
