from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.core.db import async_session
from backend.domain.candidates.max_owner_preflight import collect_max_owner_preflight_report
from backend.domain.candidates.models import (
    CandidateInviteToken,
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    User,
)


async def _create_candidate(
    *,
    candidate_uuid: str | None = None,
    max_user_id: str | None = None,
    messenger_platform: str = "telegram",
    source: str = "seed",
) -> User:
    async with async_session() as session:
        candidate = User(
            candidate_id=candidate_uuid or str(uuid4()),
            fio=f"Candidate {uuid4().hex[:6]}",
            phone="+79990000000",
            city="Москва",
            source=source,
            messenger_platform=messenger_platform,
            max_user_id=max_user_id,
            last_activity=datetime.now(UTC),
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        session.expunge(candidate)
        return candidate


async def _add_max_chat(candidate_id: int, *, direction: str = ChatMessageDirection.INBOUND.value) -> None:
    async with async_session() as session:
        message = ChatMessage(
            candidate_id=candidate_id,
            direction=direction,
            channel="max",
            text="MAX message",
            status=ChatMessageStatus.RECEIVED.value,
            created_at=datetime.now(UTC),
        )
        session.add(message)
        await session.commit()


async def _add_max_invite(
    *,
    candidate_uuid: str,
    status: str,
    used_by_external_id: str | None = None,
) -> None:
    async with async_session() as session:
        invite = CandidateInviteToken(
            candidate_id=candidate_uuid,
            token=f"mx_{uuid4().hex}",
            channel="max",
            status=status,
            used_by_external_id=used_by_external_id,
            used_at=datetime.now(UTC) if status == "used" else None,
            created_at=datetime.now(UTC),
        )
        session.add(invite)
        await session.commit()


async def _add_active_max_journey(candidate_id: int) -> None:
    async with async_session() as session:
        journey = CandidateJourneySession(
            candidate_id=candidate_id,
            entry_channel="max",
            status=CandidateJourneySessionStatus.ACTIVE.value,
            current_step_key="screening",
            started_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
        )
        session.add(journey)
        await session.commit()


@pytest.mark.asyncio
async def test_preflight_classifies_safe_auto_cleanup_duplicate_group_and_blank_owner() -> None:
    primary = await _create_candidate(
        max_user_id="mx-safe-owner",
        messenger_platform="max",
        source="max_bot_public",
    )
    secondary = await _create_candidate(
        max_user_id=" mx-safe-owner ",
        messenger_platform="telegram",
    )
    blank_owner = await _create_candidate(max_user_id="   ", messenger_platform="telegram")

    await _add_max_chat(primary.id)
    await _add_max_invite(
        candidate_uuid=str(primary.candidate_id),
        status="used",
        used_by_external_id="mx-safe-owner",
    )
    await _add_active_max_journey(primary.id)

    async with async_session() as session:
        report = await collect_max_owner_preflight_report(session, sample_limit=20)

    assert report.ready_for_unique_index is False
    assert report.blast_radius.duplicate_groups == 1

    group = next(item for item in report.duplicate_groups if item.normalized_max_user_id == "mx-safe-owner")
    assert group.cleanup_bucket == "safe_auto_cleanup"
    assert group.authoritative_candidate_pk == primary.id
    assert "single_authoritative_record" in group.reason_codes
    assert group.blocks_unique_index is True

    blank_anomaly = next(item for item in report.whitespace_anomalies if item.record.candidate_pk == blank_owner.id)
    assert blank_anomaly.anomaly_kind == "blank_or_whitespace_only"
    assert blank_anomaly.cleanup_bucket == "safe_auto_cleanup"
    assert blank_anomaly.blocks_unique_index is True

    duplicate_candidate_ids = [item.candidate_pk for item in group.records]
    assert duplicate_candidate_ids == [primary.id, secondary.id]
    assert report.blast_radius.ownership_conflicts == 0


@pytest.mark.asyncio
async def test_preflight_marks_manual_review_for_multi_evidence_duplicate_and_invite_mismatch() -> None:
    left = await _create_candidate(max_user_id="mx-manual", messenger_platform="max")
    right = await _create_candidate(max_user_id="mx-manual", messenger_platform="max")
    mismatched = await _create_candidate(max_user_id=" mx-mismatch ", messenger_platform="telegram")

    await _add_max_chat(left.id)
    await _add_max_chat(right.id, direction=ChatMessageDirection.OUTBOUND.value)
    await _add_max_invite(
        candidate_uuid=str(right.candidate_id),
        status="used",
        used_by_external_id="mx-manual",
    )
    await _add_max_invite(
        candidate_uuid=str(mismatched.candidate_id),
        status="used",
        used_by_external_id="mx-other-owner",
    )

    async with async_session() as session:
        report = await collect_max_owner_preflight_report(session, sample_limit=20)

    group = next(item for item in report.duplicate_groups if item.normalized_max_user_id == "mx-manual")
    assert group.cleanup_bucket == "manual_review_only"
    assert "multiple_records_have_max_evidence" in group.reason_codes
    assert group.blocks_unique_index is True

    mismatch_anomaly = next(
        item for item in report.whitespace_anomalies if item.record.candidate_pk == mismatched.id
    )
    assert mismatch_anomaly.anomaly_kind == "trim_only"
    assert mismatch_anomaly.cleanup_bucket == "manual_review_only"
    assert "invite_used_by_mismatch" in mismatch_anomaly.reason_codes

    conflict_kinds = {item.conflict_kind for item in report.ownership_conflicts}
    assert "invite_used_by_mismatch" in conflict_kinds
    assert report.blast_radius.ownership_conflicts >= 1
