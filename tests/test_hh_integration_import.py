from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from backend.apps.admin_ui.security import Principal, require_admin
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.hh_integration.crypto import HHSecretCipher
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    ExternalVacancyBinding,
    HHConnection,
    HHNegotiation,
    HHResumeSnapshot,
)
from fastapi.testclient import TestClient


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


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


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


class TestHHImportRoutes:
    @pytest.mark.asyncio
    async def test_import_vacancies_creates_unbound_bindings(self, admin_app):
        cipher = HHSecretCipher()
        async with async_session() as session:
            session.add(
                HHConnection(
                    principal_type="admin",
                    principal_id=1,
                    employer_id="emp-1",
                    manager_account_id="acc-42",
                    access_token_encrypted=cipher.encrypt("access-123"),
                    refresh_token_encrypted=cipher.encrypt("refresh-456"),
                    webhook_url_key="vacancies-key",
                    profile_payload={},
                )
            )
            await session.commit()

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_vacancies.side_effect = [
                    {
                        "items": [
                            {
                                "id": "vac-1",
                                "name": "Менеджер по продажам",
                                "alternate_url": "https://hh.ru/vacancy/vac-1",
                            }
                        ],
                        "page": 0,
                        "pages": 1,
                    }
                ]
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    return client.post("/api/integrations/hh/import/vacancies")

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == {"total_seen": 1, "created": 1, "updated": 0}

        async with async_session() as session:
            from sqlalchemy import select

            binding = (await session.execute(select(ExternalVacancyBinding))).scalar_one()
            assert binding.vacancy_id is None
            assert binding.external_vacancy_id == "vac-1"
            assert binding.title_snapshot == "Менеджер по продажам"

    @pytest.mark.asyncio
    async def test_import_negotiations_creates_candidate_identity_and_resume_snapshot(self, admin_app):
        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                manager_account_id="acc-42",
                manager_id="mgr-1",
                access_token_encrypted=cipher.encrypt("access-123"),
                refresh_token_encrypted=cipher.encrypt("refresh-456"),
                webhook_url_key="negotiations-key",
                profile_payload={},
            )
            session.add(connection)
            await session.flush()
            session.add(
                ExternalVacancyBinding(
                    vacancy_id=None,
                    connection_id=connection.id,
                    source="hh",
                    external_vacancy_id="12345",
                    title_snapshot="Менеджер по продажам",
                    payload_snapshot={},
                )
            )
            await session.commit()

        negotiation_payload = {
            "id": "neg-1",
            "state": {"id": "response", "name": "Отклик"},
            "resume": {
                "id": "res-1",
                "url": "https://api.hh.ru/resumes/res-1?topic_id=neg-1",
                "alternate_url": "https://hh.ru/resume/res-1",
                "first_name": "Иван",
                "last_name": "Петров",
                "title": "Менеджер по продажам",
                "area": {"name": "Москва"},
            },
            "vacancy": {"id": "vac-1", "name": "Менеджер по продажам"},
            "actions": [
                {"id": "invite", "url": "https://api.hh.ru/negotiations/interview/neg-1"}
            ],
        }
        resume_payload = {
            "id": "res-1",
            "first_name": "Иван",
            "last_name": "Петров",
            "title": "Менеджер по продажам",
            "updated_at": "2026-03-01T10:00:00+0300",
            "area": {"name": "Москва"},
            "phone": "+7 (999) 555-11-22",
            "alternate_url": "https://hh.ru/resume/res-1",
        }

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_negotiation_collections.return_value = {
                    "collections": [
                        {"id": "response", "url": "https://api.hh.ru/negotiations/response?vacancy_id=12345"}
                    ]
                }
                mock_client.list_negotiations_collection.return_value = {
                    "items": [negotiation_payload],
                    "page": 0,
                    "pages": 1,
                }
                mock_client.get_resume.return_value = resume_payload
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    return client.post("/api/integrations/hh/import/negotiations")

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()["result"]
        assert body["collections_seen"] == 1
        assert body["negotiations_seen"] == 1
        assert body["negotiations_created"] == 1
        assert body["candidates_created"] == 1
        assert body["resumes_upserted"] == 1

        async with async_session() as session:
            from sqlalchemy import select

            user = (await session.execute(select(User))).scalar_one()
            assert user.source == "hh"
            assert user.hh_resume_id == "res-1"
            assert user.hh_negotiation_id == "neg-1"
            assert user.hh_vacancy_id == "vac-1"
            assert user.phone == "79995551122"

            identity = (await session.execute(select(CandidateExternalIdentity))).scalar_one()
            assert identity.candidate_id == user.id
            assert identity.external_resume_id == "res-1"
            assert identity.external_negotiation_id == "neg-1"

            negotiation = (await session.execute(select(HHNegotiation))).scalar_one()
            assert negotiation.external_negotiation_id == "neg-1"
            assert negotiation.external_resume_id == "res-1"
            assert negotiation.collection_name == "response"

            snapshot = (await session.execute(select(HHResumeSnapshot))).scalar_one()
            assert snapshot.external_resume_id == "res-1"
            assert snapshot.candidate_id == user.id

    @pytest.mark.asyncio
    async def test_import_negotiations_falls_back_to_collection_vacancy_id(self, admin_app):
        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                manager_account_id="acc-42",
                manager_id="mgr-1",
                access_token_encrypted=cipher.encrypt("access-123"),
                refresh_token_encrypted=cipher.encrypt("refresh-456"),
                webhook_url_key="collection-vacancy-key",
                profile_payload={},
            )
            session.add(connection)
            await session.flush()
            session.add(
                ExternalVacancyBinding(
                    vacancy_id=None,
                    connection_id=connection.id,
                    source="hh",
                    external_vacancy_id="131018950",
                    title_snapshot="Стажер",
                    payload_snapshot={},
                )
            )
            await session.commit()

        negotiation_payload = {
            "id": "neg-collection-only",
            "state": {"id": "response", "name": "Отклик"},
            "resume": {"id": "res-collection-only"},
            "actions": [],
        }

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_negotiation_collections.return_value = {
                    "collections": [
                        {"id": "response", "url": "https://api.hh.ru/negotiations/response?vacancy_id=131018950"}
                    ]
                }
                mock_client.list_negotiations_collection.return_value = {
                    "items": [negotiation_payload],
                    "page": 0,
                    "pages": 1,
                }
                mock_client.get_resume.return_value = {}
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    return client.post("/api/integrations/hh/import/negotiations?fetch_resume_details=false")

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 200

        async with async_session() as session:
            from sqlalchemy import select

            identity = (
                await session.execute(
                    select(CandidateExternalIdentity).where(
                        CandidateExternalIdentity.external_negotiation_id == "neg-collection-only"
                    )
                )
            ).scalar_one()
            assert identity.external_vacancy_id == "131018950"

            negotiation = (
                await session.execute(
                    select(HHNegotiation).where(HHNegotiation.external_negotiation_id == "neg-collection-only")
                )
            ).scalar_one()
            assert negotiation.external_vacancy_id == "131018950"

    @pytest.mark.asyncio
    async def test_import_negotiations_requests_collections_per_imported_vacancy(self, admin_app):
        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                manager_account_id="acc-42",
                manager_id="mgr-1",
                access_token_encrypted=cipher.encrypt("access-123"),
                refresh_token_encrypted=cipher.encrypt("refresh-456"),
                webhook_url_key="vacancy-scan-key",
                profile_payload={},
            )
            session.add(connection)
            await session.flush()
            session.add_all(
                [
                    ExternalVacancyBinding(
                        vacancy_id=None,
                        connection_id=connection.id,
                        source="hh",
                        external_vacancy_id="1001",
                        title_snapshot="A",
                        payload_snapshot={},
                    ),
                    ExternalVacancyBinding(
                        vacancy_id=None,
                        connection_id=connection.id,
                        source="hh",
                        external_vacancy_id="1002",
                        title_snapshot="B",
                        payload_snapshot={},
                    ),
                ]
            )
            await session.commit()

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_negotiation_collections.side_effect = [
                    {"collections": [{"id": "response", "url": "https://api.hh.ru/negotiations/response?vacancy_id=1001"}]},
                    {"collections": [{"id": "response", "url": "https://api.hh.ru/negotiations/response?vacancy_id=1002"}]},
                ]
                mock_client.list_negotiations_collection.return_value = {"items": [], "page": 0, "pages": 1}
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    response = client.post("/api/integrations/hh/import/negotiations")
                return response, mock_client

        resp, mock_client = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        assert resp.json()["result"]["collections_seen"] == 2
        vacancy_ids = [call.kwargs["vacancy_id"] for call in mock_client.list_negotiation_collections.await_args_list]
        assert vacancy_ids == ["1001", "1002"]

    @pytest.mark.asyncio
    async def test_import_negotiations_can_be_scoped_to_single_vacancy(self, admin_app):
        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                manager_account_id="acc-42",
                manager_id="mgr-1",
                access_token_encrypted=cipher.encrypt("access-123"),
                refresh_token_encrypted=cipher.encrypt("refresh-456"),
                webhook_url_key="scoped-key",
                profile_payload={},
            )
            session.add(connection)
            await session.flush()
            session.add_all(
                [
                    ExternalVacancyBinding(
                        vacancy_id=None,
                        connection_id=connection.id,
                        source="hh",
                        external_vacancy_id="1001",
                        title_snapshot="A",
                        payload_snapshot={},
                    ),
                    ExternalVacancyBinding(
                        vacancy_id=None,
                        connection_id=connection.id,
                        source="hh",
                        external_vacancy_id="1002",
                        title_snapshot="B",
                        payload_snapshot={},
                    ),
                ]
            )
            await session.commit()

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_negotiation_collections.return_value = {"collections": []}
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    response = client.post("/api/integrations/hh/import/negotiations?vacancy_id=1002")
                return response, mock_client

        resp, mock_client = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        vacancy_ids = [call.kwargs["vacancy_id"] for call in mock_client.list_negotiation_collections.await_args_list]
        assert vacancy_ids == ["1002"]

    @pytest.mark.asyncio
    async def test_import_negotiations_dedupes_generated_collections_and_resume_fetches(self, admin_app):
        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                manager_account_id="acc-42",
                manager_id="mgr-1",
                access_token_encrypted=cipher.encrypt("access-123"),
                refresh_token_encrypted=cipher.encrypt("refresh-456"),
                webhook_url_key="dedupe-key",
                profile_payload={},
            )
            session.add(connection)
            await session.flush()
            session.add(
                ExternalVacancyBinding(
                    vacancy_id=None,
                    connection_id=connection.id,
                    source="hh",
                    external_vacancy_id="1001",
                    title_snapshot="A",
                    payload_snapshot={},
                )
            )
            await session.commit()

        negotiation_payload = {
            "id": "neg-1",
            "state": {"id": "response"},
            "resume": {
                "id": "res-1",
                "url": "https://api.hh.ru/resumes/res-1?topic_id=neg-1&vacancy_id=1001",
            },
            "vacancy": {"id": "1001"},
            "actions": [],
        }
        resume_payload = {
            "id": "res-1",
            "first_name": "Иван",
            "last_name": "Петров",
            "updated_at": "2026-03-01T10:00:00+0300",
            "phone": "+7 (999) 555-11-22",
        }

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_negotiation_collections.return_value = {
                    "collections": [
                        {"id": "response", "url": "https://api.hh.ru/negotiations/response?vacancy_id=1001&page=0"},
                        {
                            "id": "response",
                            "url": "https://api.hh.ru/negotiations/response?vacancy_id=1001&order_by=created_at",
                        },
                        {
                            "id": "response_999",
                            "url": "https://api.hh.ru/negotiations/response?vacancy_id=1001",
                        },
                        {
                            "id": "vacancy_visitors",
                            "url": "https://api.hh.ru/negotiations/vacancy_visitors?vacancy_id=1001",
                        },
                        {
                            "id": "offer",
                            "url": "https://api.hh.ru/negotiations/offer?vacancy_id=1001",
                            "counters": {"total": 0},
                        },
                    ]
                }
                mock_client.list_negotiations_collection.return_value = {
                    "items": [negotiation_payload],
                    "page": 0,
                    "pages": 1,
                }
                mock_client.get_resume.return_value = resume_payload
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    response = client.post("/api/integrations/hh/import/negotiations")
                return response, mock_client

        resp, mock_client = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["collections_seen"] == 1
        assert result["negotiations_seen"] == 1
        assert mock_client.list_negotiations_collection.await_count == 1
        assert mock_client.get_resume.await_count == 1
