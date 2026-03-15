from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.background_tasks import enqueue_hh_auto_import_jobs
from backend.apps.admin_ui.security import Principal, require_admin
from backend.core.db import async_session
from backend.domain.hh_integration.crypto import HHSecretCipher
from backend.domain.hh_integration.jobs import (
    enqueue_hh_sync_job,
    process_pending_hh_sync_jobs,
)
from backend.domain.hh_integration.models import (
    ExternalVacancyBinding,
    HHConnection,
    HHSyncJob,
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


async def _seed_connection_with_vacancy() -> HHConnection:
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
            webhook_url_key="jobs-key",
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
        return connection


class TestHHJobQueue:
    @pytest.mark.asyncio
    async def test_enqueue_hh_job_dedupes_pending_signature(self):
        connection = await _seed_connection_with_vacancy()
        async with async_session() as session:
            connection = await session.get(HHConnection, connection.id)
            first, created_first = await enqueue_hh_sync_job(
                session,
                connection=connection,
                job_type="import_negotiations",
                entity_type="vacancy",
                entity_external_id="131018950",
                payload_json={"fetch_resume_details": False},
            )
            second, created_second = await enqueue_hh_sync_job(
                session,
                connection=connection,
                job_type="import_negotiations",
                entity_type="vacancy",
                entity_external_id="131018950",
                payload_json={"fetch_resume_details": False},
            )
            await session.commit()
        assert created_first is True
        assert created_second is False
        assert first.id == second.id

    @pytest.mark.asyncio
    async def test_process_pending_hh_sync_jobs_marks_done(self):
        connection = await _seed_connection_with_vacancy()
        async with async_session() as session:
            connection = await session.get(HHConnection, connection.id)
            job, _ = await enqueue_hh_sync_job(
                session,
                connection=connection,
                job_type="import_negotiations",
                entity_type="vacancy",
                entity_external_id="131018950",
                payload_json={"fetch_resume_details": False},
            )
            await session.commit()

        with patch("backend.domain.hh_integration.jobs.HHApiClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.list_negotiation_collections.return_value = {"collections": []}
            mock_client_cls.return_value = mock_client
            processed = await process_pending_hh_sync_jobs(batch_size=1)

        assert processed == 1
        async with async_session() as session:
            stored = await session.get(HHSyncJob, job.id)
            assert stored is not None
            assert stored.status == "done"

    @pytest.mark.asyncio
    async def test_enqueue_hh_auto_import_jobs_creates_deduped_jobs(self):
        await _seed_connection_with_vacancy()

        connections_seen, created_jobs = await enqueue_hh_auto_import_jobs()
        repeated_connections_seen, repeated_created_jobs = await enqueue_hh_auto_import_jobs()

        assert connections_seen == 1
        assert created_jobs == 2
        assert repeated_connections_seen == 1
        assert repeated_created_jobs == 0

        async with async_session() as session:
            jobs = list((await session.execute(select(HHSyncJob).order_by(HHSyncJob.id.asc()))).scalars().all())

        assert len(jobs) == 2
        assert {job.job_type for job in jobs} == {"import_vacancies", "import_negotiations"}
        negotiation_job = next(job for job in jobs if job.job_type == "import_negotiations")
        assert negotiation_job.entity_type == "employer"
        assert negotiation_job.payload_json == {"fetch_resume_details": False}


class TestHHJobRoutes:
    @pytest.mark.asyncio
    async def test_enqueue_and_list_hh_jobs_routes(self, admin_app):
        await _seed_connection_with_vacancy()

        def _call():
            with TestClient(admin_app) as client:
                created = client.post(
                    "/api/integrations/hh/jobs/import/negotiations?vacancy_id=131018950&fetch_resume_details=false"
                )
                listed = client.get("/api/integrations/hh/jobs")
                return created, listed

        created, listed = await asyncio.to_thread(_call)
        assert created.status_code == 200
        assert created.json()["created"] is True
        assert listed.status_code == 200
        jobs = listed.json()["jobs"]
        assert jobs[0]["job_type"] == "import_negotiations"
        assert jobs[0]["entity_external_id"] == "131018950"
