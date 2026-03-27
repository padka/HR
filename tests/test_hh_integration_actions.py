from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from backend.apps.admin_ui.security import Principal, require_admin, require_csrf_token, require_principal
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.hh_integration.crypto import HHSecretCipher
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    ExternalVacancyBinding,
    HHConnection,
    HHNegotiation,
    HHResumeSnapshot,
    HHSyncJob,
)
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture
def hh_env(monkeypatch):
    monkeypatch.setenv("HH_INTEGRATION_ENABLED", "1")
    monkeypatch.setenv("HH_CLIENT_ID", "hh-client")
    monkeypatch.setenv("HH_CLIENT_SECRET", "hh-secret")
    monkeypatch.setenv("HH_REDIRECT_URI", "https://crm.example.com/api/integrations/hh/oauth/callback")
    monkeypatch.setenv("HH_WEBHOOK_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("HH_USER_AGENT", "RecruitSmartTest/1.0 (qa@example.com)")
    monkeypatch.setenv("CRM_PUBLIC_URL", "https://crm.example.test")
    monkeypatch.setenv("CANDIDATE_PORTAL_PUBLIC_URL", "https://crm.example.test")
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
    app.dependency_overrides[require_principal] = lambda: Principal(type="admin", id=1)
    app.dependency_overrides[require_csrf_token] = lambda: None
    try:
        yield app
    finally:
        app.dependency_overrides.pop(require_admin, None)
        app.dependency_overrides.pop(require_principal, None)
        app.dependency_overrides.pop(require_csrf_token, None)
        settings_module.get_settings.cache_clear()


async def _seed_candidate_with_hh_action():
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
            webhook_url_key="actions-key",
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
        candidate = User(fio="Иван Петров", source="hh")
        session.add(candidate)
        await session.flush()
        identity = CandidateExternalIdentity(
            candidate_id=candidate.id,
            source="hh",
            external_resume_id="res-1",
            external_negotiation_id="neg-1",
            external_vacancy_id="131018950",
            payload_snapshot={},
        )
        session.add(identity)
        await session.flush()
        session.add(
            HHNegotiation(
                connection_id=connection.id,
                candidate_identity_id=identity.id,
                external_negotiation_id="neg-1",
                external_resume_id="res-1",
                external_vacancy_id="131018950",
                employer_state="response",
                actions_snapshot={
                    "actions": [
                        {
                            "id": "interview",
                            "name": "Собеседование",
                            "method": "PUT",
                            "url": "https://api.hh.ru/negotiations/interview/neg-1",
                            "arguments": [{"id": "message", "required": False}],
                            "resulting_employer_state": {"id": "interview", "name": "Собеседование"},
                            "sub_actions": [
                                {
                                    "id": "interview_custom",
                                    "name": "Собеседование (custom)",
                                    "method": "PUT",
                                    "url": "https://api.hh.ru/negotiations/interview_custom/neg-1",
                                }
                            ],
                        }
                    ]
                },
                payload_snapshot={"updated_at": "2026-03-07T00:00:00+00:00"},
            )
        )
        session.add(
            HHResumeSnapshot(
                candidate_id=candidate.id,
                external_resume_id="res-1",
                payload_json={"title": "Стажер поддержки", "updated_at": "2026-03-06T10:00:00+00:00"},
            )
        )
        session.add(
            HHSyncJob(
                connection_id=connection.id,
                job_type="import_negotiations",
                direction="inbound",
                entity_type="vacancy",
                entity_external_id="131018950",
                status="done",
                attempts=1,
                idempotency_key="job-1",
                payload_json={},
            )
        )
        await session.commit()
        return candidate.id


class TestHHActionsRoutes:
    @pytest.mark.asyncio
    async def test_get_hh_candidate_summary(self, admin_app):
        candidate_id = await _seed_candidate_with_hh_action()

        def _call():
            with TestClient(admin_app) as client:
                return client.get(f"/api/candidates/{candidate_id}/hh")

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()
        assert body["linked"] is True
        assert body["resume"]["id"] == "res-1"
        assert body["vacancy"]["id"] == "131018950"
        assert body["negotiation"]["id"] == "neg-1"
        assert body["available_actions"][0]["id"] == "interview"
        assert body["recent_jobs"][0]["job_type"] == "import_negotiations"

    @pytest.mark.asyncio
    async def test_get_hh_candidate_actions(self, admin_app):
        candidate_id = await _seed_candidate_with_hh_action()

        def _call():
            with TestClient(admin_app) as client:
                return client.get(f"/api/integrations/hh/candidates/{candidate_id}/actions")

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()
        assert body["negotiation_id"] == "neg-1"
        assert body["vacancy_id"] == "131018950"
        assert body["actions"][0]["id"] == "interview"
        assert body["actions"][0]["sub_actions"][0]["id"] == "interview_custom"

    @pytest.mark.asyncio
    async def test_execute_hh_candidate_action_and_refresh_scope(self, admin_app):
        candidate_id = await _seed_candidate_with_hh_action()

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.execute_negotiation_action.return_value = {"ok": True}
                mock_client.list_negotiation_collections.return_value = {"collections": []}
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    response = client.post(
                        f"/api/integrations/hh/candidates/{candidate_id}/actions/interview_custom",
                        json={"arguments": {"message": "Приглашаем"}},
                    )
                return response, mock_client

        resp, mock_client = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["action_id"] == "interview_custom"
        mock_client.execute_negotiation_action.assert_awaited_once()
        kwargs = mock_client.execute_negotiation_action.await_args.kwargs
        assert kwargs["action_url"] == "https://api.hh.ru/negotiations/interview_custom/neg-1"
        assert kwargs["arguments"] == {"message": "Приглашаем"}
        list_kwargs = mock_client.list_negotiation_collections.await_args.kwargs
        assert list_kwargs["vacancy_id"] == "131018950"

    @pytest.mark.asyncio
    async def test_send_hh_entry_link_uses_message_action(self, admin_app):
        candidate_id = await _seed_candidate_with_hh_action()

        def _call():
            with patch("backend.apps.admin_ui.routers.api_misc.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.execute_negotiation_action.return_value = {"ok": True}
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    response = client.post(f"/api/candidates/{candidate_id}/hh/send-entry-link")
                return response, mock_client

        resp, mock_client = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["sent"] is True
        assert "candidate/start?entry=" in body["hh_entry_url"]
        mock_client.execute_negotiation_action.assert_awaited_once()
        kwargs = mock_client.execute_negotiation_action.await_args.kwargs
        assert "Выберите удобный канал" in kwargs["arguments"]["message"]

    @pytest.mark.asyncio
    async def test_send_hh_entry_link_returns_blocked_when_message_action_missing(self, admin_app):
        candidate_id = await _seed_candidate_with_hh_action()

        async def _strip_actions() -> None:
            async with async_session() as session:
                negotiation = (
                    await session.execute(
                        select(HHNegotiation)
                        .order_by(HHNegotiation.id.desc())
                        .limit(1)
                    )
                ).scalar_one()
                negotiation.actions_snapshot = {
                    "actions": [
                        {
                            "id": "view",
                            "name": "Посмотреть",
                            "method": "GET",
                            "url": "https://api.hh.ru/negotiations/view/neg-1",
                            "arguments": [],
                        }
                    ]
                }
                await session.commit()

        await _strip_actions()

        def _call():
            with TestClient(admin_app) as client:
                return client.post(f"/api/candidates/{candidate_id}/hh/send-entry-link")

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 409
        body = resp.json()
        assert body["ok"] is False
        assert body["blocked_reason"] == "hh_message_action_missing"
