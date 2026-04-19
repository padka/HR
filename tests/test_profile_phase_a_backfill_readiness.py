from __future__ import annotations

from argparse import Namespace
from datetime import UTC, datetime, timedelta

import pytest
from backend.core.db import async_session
from backend.domain.ai.models import AIOutput, AIRequestLog
from backend.domain.candidates.models import (
    CandidateInviteToken,
    CandidateJourneySession,
    ChatMessage,
    InterviewNote,
    User,
)
from backend.domain.detailization.models import DetailizationEntry
from backend.domain.models import (
    NotificationLog,
    OutboxNotification,
    Recruiter,
    Slot,
    SlotAssignment,
)
from scripts import profile_phase_a_backfill_readiness as profiler
from sqlalchemy.exc import ProgrammingError


@pytest.mark.asyncio
async def test_collect_backfill_readiness_report_classifies_conflicts() -> None:
    async with async_session() as session:
        recruiter = Recruiter(name="Recruiter One", tg_chat_id=101)
        session.add(recruiter)
        await session.flush()

        user_one = User(
            fio="Alice Candidate",
            phone_normalized="+79990000001",
            desired_position="Courier",
            source="manual",
            max_user_id="max-shared",
            city="Moscow",
        )
        user_two = User(
            fio="Bob Candidate",
            phone_normalized="+79990000001",
            max_user_id="max-shared",
        )
        session.add_all([user_one, user_two])
        await session.flush()

        slot = Slot(
            recruiter_id=recruiter.id,
            start_utc=datetime.now(UTC),
            duration_min=60,
            status="free",
        )
        session.add(slot)
        await session.flush()

        session.add_all(
            [
                SlotAssignment(slot_id=slot.id, recruiter_id=recruiter.id, status="offered"),
                ChatMessage(candidate_id=user_one.id, telegram_user_id=777, text="hi"),
                ChatMessage(candidate_id=user_two.id, telegram_user_id=777, text="hello"),
                OutboxNotification(type="invite"),
                NotificationLog(booking_id=slot.id, type="invite", delivery_status="sent"),
                DetailizationEntry(candidate_id=user_one.id, created_by_type="system", created_by_id=-1),
                AIOutput(
                    scope_type="thread",
                    scope_id=999,
                    kind="summary",
                    input_hash="hash-1",
                    payload_json={},
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                ),
                AIRequestLog(
                    principal_type="recruiter",
                    principal_id=recruiter.id,
                    scope_type="thread",
                    scope_id=999,
                    kind="summary",
                    provider="openai",
                    model="gpt-test",
                ),
                CandidateJourneySession(
                    candidate_id=user_one.id,
                    status="active",
                    current_step_key="profile",
                ),
                CandidateJourneySession(
                    candidate_id=user_one.id,
                    status="active",
                    current_step_key="booking",
                ),
                CandidateInviteToken(
                    candidate_id=user_one.candidate_id,
                    token="token-a",
                    status="active",
                    channel="generic",
                ),
                CandidateInviteToken(
                    candidate_id=user_one.candidate_id,
                    token="token-b",
                    status="active",
                    channel="generic",
                ),
                InterviewNote(user_id=user_one.id, data={}),
            ]
        )
        await session.commit()

    async with async_session() as session:
        report = await profiler.collect_backfill_readiness_report(session)

    assert report.counts["phone_normalized_duplicate_groups"] == 1
    assert report.counts["max_user_id_duplicate_groups"] == 1
    assert report.counts["chat_messages_telegram_cross_candidate_groups"] == 1
    assert report.counts["slot_assignments_without_candidate_anchor"] == 1
    assert report.counts["outbox_mapping_gaps"] == 1
    assert report.counts["notification_log_mapping_gaps"] == 1
    assert report.counts["detailization_without_slot_anchor"] == 1
    assert report.counts["ai_outputs_unmappable"] == 1
    assert report.counts["ai_request_logs_unmappable"] == 1
    assert report.counts["journey_sessions_multiple_active_per_candidate"] == 1
    assert report.counts["invite_token_channel_conflicts"] == 1
    assert any(item.key == "phone_normalized_duplicates" for item in report.blockers)
    assert any(item.key == "journey_access_gaps" for item in report.ambiguous_cases)
    assert any(item.queue == "identity_conflicts_review" for item in report.manual_review_queues)


@pytest.mark.asyncio
async def test_render_text_and_json_are_aggregate_only() -> None:
    async with async_session() as session:
        user = User(
            fio="Private Candidate",
            phone_normalized="+79995554433",
            desired_position="Operator",
            source="manual",
            max_user_id="max-private",
        )
        session.add(user)
        await session.commit()

    async with async_session() as session:
        report = await profiler.collect_backfill_readiness_report(session)

    rendered = profiler.render_backfill_readiness_text(report)
    payload = report.to_dict()

    assert "Private Candidate" not in rendered
    assert "+79995554433" not in rendered
    assert "max-private" not in rendered
    assert "Private Candidate" not in str(payload)
    assert "+79995554433" not in str(payload)
    assert "max-private" not in str(payload)


@pytest.mark.asyncio
async def test_run_returns_zero_on_warnings_and_one_on_execution_error(monkeypatch) -> None:
    args = Namespace(format="json")
    assert await profiler._run(args) == 0

    class BrokenAsyncSession:
        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(profiler, "async_session", lambda: BrokenAsyncSession())
    assert await profiler._run(args) == 1


@pytest.mark.asyncio
async def test_run_sanitizes_schema_error_output(monkeypatch, capsys) -> None:
    args = Namespace(format="text")

    class BrokenAsyncSession:
        async def __aenter__(self):
            raise ProgrammingError(
                "SELECT * FROM candidate_journey_sessions",
                {},
                Exception(
                    "column candidate_journey_sessions.last_access_session_id does not exist "
                    "on localhost:5432 db=recruitsmart"
                ),
            )

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(profiler, "async_session", lambda: BrokenAsyncSession())

    assert await profiler._run(args) == 1
    captured = capsys.readouterr()

    assert "database schema is unavailable or not migrated" in captured.err
    assert "ProgrammingError" in captured.err
    assert "last_access_session_id" not in captured.err
    assert "localhost" not in captured.err
    assert "recruitsmart" not in captured.err
