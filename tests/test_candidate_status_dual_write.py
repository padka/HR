from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from backend.apps.admin_ui.services.candidates.application_dual_write import (
    CANDIDATE_STATUS_OPERATION_KIND,
    CANDIDATE_STATUS_PRODUCER_FAMILY,
)
from backend.apps.admin_ui.services.candidates.helpers import update_candidate_status
from backend.core import settings as settings_module
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import (
    Application,
    ApplicationEvent,
    ApplicationIdempotencyKey,
)
from sqlalchemy import func, select


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


async def _seed_candidate(*, telegram_id: int, fio: str) -> int:
    async with async_session() as session:
        user = User(
            telegram_id=telegram_id,
            telegram_user_id=telegram_id,
            candidate_id=f"cand-{uuid4()}",
            fio=fio,
            city="Москва",
            source="manual",
            messenger_platform="telegram",
            candidate_status=CandidateStatus.LEAD,
            status_changed_at=datetime.now(UTC),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return int(user.id)


async def _application_event_types(candidate_id: int) -> set[str]:
    async with async_session() as session:
        events = (
            await session.execute(
                select(ApplicationEvent.event_type).where(ApplicationEvent.candidate_id == candidate_id)
            )
        ).scalars().all()
    return {str(item) for item in events}


@pytest.mark.asyncio
async def test_status_dual_write_disabled_keeps_legacy_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CANDIDATE_STATUS_DUAL_WRITE_ENABLED", raising=False)
    candidate_id = await _seed_candidate(
        telegram_id=7001001,
        fio="Legacy Status Candidate",
    )

    ok, _, stored_status, dispatch = await update_candidate_status(
        candidate_id,
        CandidateStatus.INTERVIEW_DECLINED.value,
        reason="manual decline",
    )

    assert ok is True
    assert stored_status == CandidateStatus.INTERVIEW_DECLINED.value
    assert dispatch is not None

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        application_count = int(
            await session.scalar(
                select(func.count()).select_from(Application).where(Application.candidate_id == candidate_id)
            )
            or 0
        )
        event_count = int(
            await session.scalar(
                select(func.count()).select_from(ApplicationEvent).where(ApplicationEvent.candidate_id == candidate_id)
            )
            or 0
        )
        ledger_count = int(
            await session.scalar(
                select(func.count()).select_from(ApplicationIdempotencyKey).where(
                    ApplicationIdempotencyKey.candidate_id == candidate_id
                )
            )
            or 0
        )

    assert user is not None
    assert user.candidate_status == CandidateStatus.INTERVIEW_DECLINED
    assert application_count == 0
    assert event_count == 0
    assert ledger_count == 0


@pytest.mark.asyncio
async def test_status_dual_write_enabled_creates_anchor_event_and_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CANDIDATE_STATUS_DUAL_WRITE_ENABLED", "1")
    candidate_id = await _seed_candidate(
        telegram_id=7001002,
        fio="Dual Write Status Candidate",
    )

    ok, _, stored_status, dispatch = await update_candidate_status(
        candidate_id,
        CandidateStatus.INTERVIEW_DECLINED.value,
        reason="manual decline",
        idempotency_key="status-transition-1",
    )

    assert ok is True
    assert stored_status == CandidateStatus.INTERVIEW_DECLINED.value
    assert dispatch is not None

    async with async_session() as session:
        application = await session.scalar(
            select(Application).where(Application.candidate_id == candidate_id)
        )
        ledger = await session.scalar(
            select(ApplicationIdempotencyKey).where(
                ApplicationIdempotencyKey.operation_kind == CANDIDATE_STATUS_OPERATION_KIND,
                ApplicationIdempotencyKey.producer_family == CANDIDATE_STATUS_PRODUCER_FAMILY,
                ApplicationIdempotencyKey.idempotency_key == "status-transition-1",
            )
        )

    assert application is not None
    assert application.requisition_id is None
    assert await _application_event_types(candidate_id) == {
        "application.created",
        "application.status_changed",
    }
    assert ledger is not None
    assert ledger.candidate_id == candidate_id
    assert ledger.application_id == application.id
    assert ledger.status == "completed"


@pytest.mark.asyncio
async def test_status_dual_write_reuses_same_key_without_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CANDIDATE_STATUS_DUAL_WRITE_ENABLED", "1")
    candidate_id = await _seed_candidate(
        telegram_id=7001003,
        fio="Dual Write Status Replay Candidate",
    )

    first = await update_candidate_status(
        candidate_id,
        CandidateStatus.INTERVIEW_DECLINED.value,
        reason="manual decline",
        idempotency_key="status-transition-reuse",
    )
    second = await update_candidate_status(
        candidate_id,
        CandidateStatus.INTERVIEW_DECLINED.value,
        reason="manual decline",
        idempotency_key="status-transition-reuse",
    )

    assert first[0] is True
    assert second[0] is True
    async with async_session() as session:
        application_count = int(
            await session.scalar(
                select(func.count()).select_from(Application).where(Application.candidate_id == candidate_id)
            )
            or 0
        )
        event_count = int(
            await session.scalar(
                select(func.count()).select_from(ApplicationEvent).where(ApplicationEvent.candidate_id == candidate_id)
            )
            or 0
        )
        ledger_count = int(
            await session.scalar(
                select(func.count()).select_from(ApplicationIdempotencyKey).where(
                    ApplicationIdempotencyKey.candidate_id == candidate_id,
                    ApplicationIdempotencyKey.operation_kind == CANDIDATE_STATUS_OPERATION_KIND,
                )
            )
            or 0
        )

    assert application_count == 1
    assert event_count == 2
    assert ledger_count == 1


@pytest.mark.asyncio
async def test_status_dual_write_conflicts_on_same_key_new_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CANDIDATE_STATUS_DUAL_WRITE_ENABLED", "1")
    candidate_id = await _seed_candidate(
        telegram_id=7001004,
        fio="Dual Write Status Conflict Candidate",
    )

    first = await update_candidate_status(
        candidate_id,
        CandidateStatus.INTERVIEW_DECLINED.value,
        reason="manual decline",
        idempotency_key="status-transition-conflict",
    )
    second = await update_candidate_status(
        candidate_id,
        CandidateStatus.NOT_HIRED.value,
        reason="different outcome",
        idempotency_key="status-transition-conflict",
    )

    assert first[0] is True
    assert second[0] is False
    assert "идемпотентности" in (second[1] or "").lower()
    async with async_session() as session:
        event_count = int(
            await session.scalar(
                select(func.count()).select_from(ApplicationEvent).where(ApplicationEvent.candidate_id == candidate_id)
            )
            or 0
        )
        user = await session.get(User, candidate_id)

    assert event_count == 2
    assert user is not None
    assert user.candidate_status == CandidateStatus.INTERVIEW_DECLINED
