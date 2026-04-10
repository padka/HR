from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.hh_integration.crypto import HHSecretCipher
from backend.domain.hh_integration.jobs import process_pending_hh_sync_jobs
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    HHConnection,
    HHNegotiation,
    HHSyncJob,
)
from backend.domain.hh_integration.outbound import (
    enqueue_candidate_status_sync,
    resolve_hh_sync_intent,
)


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


async def _seed_outbound_candidate(*, actions: list[dict], status: CandidateStatus) -> tuple[int, int]:
    cipher = HHSecretCipher()
    now = datetime.now(UTC)
    async with async_session() as session:
        connection = HHConnection(
            principal_type="admin",
            principal_id=1,
            employer_id="emp-1",
            manager_account_id="acc-42",
            manager_id="mgr-1",
            access_token_encrypted=cipher.encrypt("access-123"),
            refresh_token_encrypted=cipher.encrypt("refresh-456"),
            webhook_url_key="outbound-key",
            profile_payload={},
        )
        session.add(connection)
        await session.flush()

        candidate = User(
            fio="HH Outbound Candidate",
            phone="+79995550011",
            source="hh",
            candidate_status=status,
            status_changed_at=now,
        )
        session.add(candidate)
        await session.flush()

        identity = CandidateExternalIdentity(
            candidate_id=candidate.id,
            source="hh",
            external_resume_id="res-1",
            external_negotiation_id="neg-1",
            external_vacancy_id="vac-1",
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
                external_vacancy_id="vac-1",
                employer_state="response",
                actions_snapshot={"actions": actions},
                payload_snapshot={"updated_at": now.isoformat()},
                last_hh_sync_at=now,
            )
        )
        await session.commit()
        return candidate.id, connection.id


class TestHHOutboundMapping:
    def test_resolve_hh_sync_intent_maps_supported_statuses(self):
        assert resolve_hh_sync_intent(CandidateStatus.INTERVIEW_SCHEDULED).value == "invite_to_interview"
        assert resolve_hh_sync_intent(CandidateStatus.NOT_HIRED).value == "reject_candidate"
        assert resolve_hh_sync_intent(CandidateStatus.HIRED).value == "mark_hired"
        assert resolve_hh_sync_intent(CandidateStatus.TEST2_COMPLETED).value == "no_op"


class TestHHOutboundJobs:
    @pytest.mark.asyncio
    async def test_enqueue_candidate_status_sync_dedupes_transition(self, hh_env):
        candidate_id, _ = await _seed_outbound_candidate(
            actions=[
                {
                    "id": "interview",
                    "name": "Собеседование",
                    "method": "PUT",
                    "url": "https://api.hh.ru/negotiations/interview/neg-1",
                    "enabled": True,
                }
            ],
            status=CandidateStatus.INTERVIEW_SCHEDULED,
        )

        async with async_session() as session:
            candidate = await session.get(User, candidate_id)
            first, created_first = await enqueue_candidate_status_sync(
                session,
                candidate=candidate,
                target_status=CandidateStatus.INTERVIEW_SCHEDULED,
            )
            second, created_second = await enqueue_candidate_status_sync(
                session,
                candidate=candidate,
                target_status=CandidateStatus.INTERVIEW_SCHEDULED,
            )
            await session.commit()

        assert created_first is True
        assert created_second is False
        assert first.id == second.id

    @pytest.mark.asyncio
    async def test_process_pending_hh_sync_jobs_executes_outbound_status_sync(self, hh_env):
        candidate_id, _ = await _seed_outbound_candidate(
            actions=[
                {
                    "id": "interview",
                    "name": "Собеседование",
                    "method": "PUT",
                    "url": "https://api.hh.ru/negotiations/interview/neg-1",
                    "enabled": True,
                }
            ],
            status=CandidateStatus.INTERVIEW_SCHEDULED,
        )

        async with async_session() as session:
            candidate = await session.get(User, candidate_id)
            await enqueue_candidate_status_sync(
                session,
                candidate=candidate,
                target_status=CandidateStatus.INTERVIEW_SCHEDULED,
            )
            await session.commit()

        with patch("backend.domain.hh_integration.jobs.import_hh_negotiations", new=AsyncMock(return_value=None)):
            with patch("backend.domain.hh_integration.jobs.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.execute_negotiation_action.return_value = {"ok": True}
                mock_client_cls.return_value = mock_client
                processed = await process_pending_hh_sync_jobs(batch_size=1)

        assert processed == 1
        async with async_session() as session:
            job = (
                await session.execute(
                    select(HHSyncJob).where(HHSyncJob.candidate_id == candidate_id).limit(1)
                )
            ).scalar_one()
            candidate = await session.get(User, candidate_id)

        assert job.status == "done"
        assert job.failure_code is None
        assert job.result_json["action_id"] == "interview"
        assert candidate.hh_sync_status == "synced"
        assert candidate.hh_sync_error is None

    @pytest.mark.asyncio
    async def test_process_pending_hh_sync_jobs_marks_dead_when_action_unavailable(self, hh_env):
        candidate_id, _ = await _seed_outbound_candidate(
            actions=[
                {
                    "id": "view",
                    "name": "Посмотреть",
                    "method": "GET",
                    "url": "https://api.hh.ru/negotiations/view/neg-1",
                    "enabled": True,
                }
            ],
            status=CandidateStatus.INTERVIEW_SCHEDULED,
        )

        async with async_session() as session:
            candidate = await session.get(User, candidate_id)
            await enqueue_candidate_status_sync(
                session,
                candidate=candidate,
                target_status=CandidateStatus.INTERVIEW_SCHEDULED,
            )
            await session.commit()

        with patch("backend.domain.hh_integration.jobs.import_hh_negotiations", new=AsyncMock(return_value=None)):
            processed = await process_pending_hh_sync_jobs(batch_size=1)

        assert processed == 1
        async with async_session() as session:
            job = (
                await session.execute(
                    select(HHSyncJob).where(HHSyncJob.candidate_id == candidate_id).limit(1)
                )
            ).scalar_one()
            candidate = await session.get(User, candidate_id)

        assert job.status == "dead"
        assert job.failure_code == "action_unavailable"
        assert candidate.hh_sync_status == "failed_sync"
        assert candidate.hh_sync_error == "action_unavailable"
