#!/usr/bin/env python3
"""Read-only readiness audit for Phase B application/event dual-write."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
from backend.domain.hh_integration.models import CandidateExternalIdentity
from backend.domain.models import NotificationLog, OutboxNotification, SlotAssignment
from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

ACTIVE_SLOT_STATUSES = (
    "offered",
    "confirmed",
    "reschedule_requested",
    "reschedule_confirmed",
)


@dataclass(frozen=True)
class BucketSummary:
    key: str
    severity: str
    count: int
    summary: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "severity": self.severity,
            "count": self.count,
            "summary": self.summary,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class ManualReviewQueue:
    queue: str
    trigger_count: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue": self.queue,
            "trigger_count": self.trigger_count,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BackfillReadinessReport:
    generated_at: str
    counts: dict[str, int]
    blockers: list[BucketSummary] = field(default_factory=list)
    warnings: list[BucketSummary] = field(default_factory=list)
    ambiguous_cases: list[BucketSummary] = field(default_factory=list)
    manual_review_queues: list[ManualReviewQueue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "counts": dict(sorted(self.counts.items())),
            "blockers": [item.to_dict() for item in self.blockers],
            "warnings": [item.to_dict() for item in self.warnings],
            "ambiguous_cases": [item.to_dict() for item in self.ambiguous_cases],
            "manual_review_queues": [item.to_dict() for item in self.manual_review_queues],
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only aggregate audit for Phase B primary application resolver, "
            "transactional event publisher, and backfill readiness."
        )
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    return parser.parse_args()


def _present_str(column):
    return and_(column.is_not(None), column != "")


async def _scalar_int(session: AsyncSession, statement) -> int:
    value = await session.scalar(statement)
    return int(value or 0)


async def _duplicate_groups(
    session: AsyncSession,
    column,
    *,
    exclude_blank: bool = False,
) -> tuple[int, int]:
    conditions = [column.is_not(None)]
    if exclude_blank:
        conditions.append(column != "")
    subquery = (
        select(column.label("value"), func.count().label("row_count"))
        .where(*conditions)
        .group_by(column)
        .having(func.count() > 1)
        .subquery()
    )
    groups = await _scalar_int(session, select(func.count()).select_from(subquery))
    affected_rows = await _scalar_int(
        session,
        select(func.coalesce(func.sum(subquery.c.row_count), 0)),
    )
    return groups, affected_rows


async def collect_backfill_readiness_report(session: AsyncSession) -> BackfillReadinessReport:
    user_alias = aliased(User)

    counts: dict[str, int] = {}

    counts["users_total"] = await _scalar_int(session, select(func.count()).select_from(User))
    counts["slot_assignments_total"] = await _scalar_int(
        session, select(func.count()).select_from(SlotAssignment)
    )
    counts["chat_messages_total"] = await _scalar_int(
        session, select(func.count()).select_from(ChatMessage)
    )
    counts["outbox_notifications_total"] = await _scalar_int(
        session, select(func.count()).select_from(OutboxNotification)
    )
    counts["notification_logs_total"] = await _scalar_int(
        session, select(func.count()).select_from(NotificationLog)
    )
    counts["detailization_entries_total"] = await _scalar_int(
        session, select(func.count()).select_from(DetailizationEntry)
    )
    counts["interview_notes_total"] = await _scalar_int(
        session, select(func.count()).select_from(InterviewNote)
    )
    counts["ai_outputs_total"] = await _scalar_int(
        session, select(func.count()).select_from(AIOutput)
    )
    counts["ai_request_logs_total"] = await _scalar_int(
        session, select(func.count()).select_from(AIRequestLog)
    )
    counts["journey_sessions_total"] = await _scalar_int(
        session, select(func.count()).select_from(CandidateJourneySession)
    )
    counts["candidate_invite_tokens_total"] = await _scalar_int(
        session, select(func.count()).select_from(CandidateInviteToken)
    )
    counts["candidate_external_identities_total"] = await _scalar_int(
        session, select(func.count()).select_from(CandidateExternalIdentity)
    )

    counts["users_with_hh_fields"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(User)
        .where(
            or_(
                _present_str(User.hh_resume_id),
                _present_str(User.hh_negotiation_id),
                _present_str(User.hh_vacancy_id),
            )
        ),
    )

    counts["users_with_source_or_desired_position_no_vacancy"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(User)
        .where(
            or_(_present_str(User.desired_position), and_(User.source.is_not(None), User.source != "bot")),
            not_(
                or_(
                    _present_str(User.hh_vacancy_id),
                    select(func.count())
                    .select_from(CandidateExternalIdentity)
                    .where(
                        CandidateExternalIdentity.candidate_id == User.id,
                        _present_str(CandidateExternalIdentity.external_vacancy_id),
                    )
                    .scalar_subquery()
                    > 0,
                )
            ),
        ),
    )

    counts["users_with_city_no_vacancy"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(User)
        .where(
            _present_str(User.city),
            not_(
                or_(
                    _present_str(User.hh_vacancy_id),
                    select(func.count())
                    .select_from(CandidateExternalIdentity)
                    .where(
                        CandidateExternalIdentity.candidate_id == User.id,
                        _present_str(CandidateExternalIdentity.external_vacancy_id),
                    )
                    .scalar_subquery()
                    > 0,
                )
            ),
        ),
    )

    phone_groups, phone_affected = await _duplicate_groups(
        session, User.phone_normalized, exclude_blank=True
    )
    tg_id_groups, tg_id_affected = await _duplicate_groups(session, User.telegram_id)
    tg_user_groups, tg_user_affected = await _duplicate_groups(session, User.telegram_user_id)
    max_groups, max_affected = await _duplicate_groups(
        session, User.max_user_id, exclude_blank=True
    )
    hh_resume_groups, hh_resume_affected = await _duplicate_groups(
        session, User.hh_resume_id, exclude_blank=True
    )
    hh_negotiation_groups, hh_negotiation_affected = await _duplicate_groups(
        session, User.hh_negotiation_id, exclude_blank=True
    )

    counts["phone_normalized_duplicate_groups"] = phone_groups
    counts["phone_normalized_affected_candidates"] = phone_affected
    counts["telegram_id_duplicate_groups"] = tg_id_groups
    counts["telegram_id_affected_candidates"] = tg_id_affected
    counts["telegram_user_id_duplicate_groups"] = tg_user_groups
    counts["telegram_user_id_affected_candidates"] = tg_user_affected
    counts["max_user_id_duplicate_groups"] = max_groups
    counts["max_user_id_affected_candidates"] = max_affected
    counts["hh_resume_duplicate_groups"] = hh_resume_groups
    counts["hh_resume_affected_candidates"] = hh_resume_affected
    counts["hh_negotiation_duplicate_groups"] = hh_negotiation_groups
    counts["hh_negotiation_affected_candidates"] = hh_negotiation_affected

    counts["chat_messages_telegram_cross_candidate_groups"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(
            select(
                ChatMessage.telegram_user_id,
                func.count(func.distinct(ChatMessage.candidate_id)).label("candidate_count"),
            )
            .where(ChatMessage.telegram_user_id.is_not(None))
            .group_by(ChatMessage.telegram_user_id)
            .having(func.count(func.distinct(ChatMessage.candidate_id)) > 1)
            .subquery()
        ),
    )

    counts["invite_token_telegram_claim_conflicts"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(
            select(
                CandidateInviteToken.used_by_telegram_id,
                func.count(func.distinct(CandidateInviteToken.candidate_id)).label("candidate_count"),
            )
            .where(CandidateInviteToken.used_by_telegram_id.is_not(None))
            .group_by(CandidateInviteToken.used_by_telegram_id)
            .having(func.count(func.distinct(CandidateInviteToken.candidate_id)) > 1)
            .subquery()
        ),
    )

    counts["slot_assignments_without_candidate_anchor"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(SlotAssignment)
        .where(SlotAssignment.candidate_id.is_(None), SlotAssignment.candidate_tg_id.is_(None)),
    )
    counts["slot_assignments_tg_only_without_user_match"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(SlotAssignment)
        .where(
            SlotAssignment.candidate_id.is_(None),
            SlotAssignment.candidate_tg_id.is_not(None),
            not_(
                select(func.count())
                .select_from(User)
                .where(
                    or_(
                        User.telegram_id == SlotAssignment.candidate_tg_id,
                        User.telegram_user_id == SlotAssignment.candidate_tg_id,
                    )
                )
                .scalar_subquery()
                > 0
            ),
        ),
    )
    counts["slot_assignment_active_conflicts_by_candidate"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(
            select(SlotAssignment.candidate_id)
            .where(
                SlotAssignment.candidate_id.is_not(None),
                SlotAssignment.status.in_(ACTIVE_SLOT_STATUSES),
            )
            .group_by(SlotAssignment.candidate_id)
            .having(func.count() > 1)
            .subquery()
        ),
    )
    counts["slot_assignment_active_conflicts_by_candidate_tg"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(
            select(SlotAssignment.candidate_tg_id)
            .where(
                SlotAssignment.candidate_tg_id.is_not(None),
                SlotAssignment.status.in_(ACTIVE_SLOT_STATUSES),
            )
            .group_by(SlotAssignment.candidate_tg_id)
            .having(func.count() > 1)
            .subquery()
        ),
    )

    counts["chat_messages_candidate_mismatch"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(ChatMessage)
        .join(user_alias, user_alias.id == ChatMessage.candidate_id)
        .where(
            ChatMessage.telegram_user_id.is_not(None),
            not_(
                or_(
                    user_alias.telegram_id == ChatMessage.telegram_user_id,
                    user_alias.telegram_user_id == ChatMessage.telegram_user_id,
                )
            ),
        ),
    )

    counts["outbox_mapping_gaps"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(OutboxNotification)
        .where(
            OutboxNotification.booking_id.is_(None),
            OutboxNotification.candidate_tg_id.is_(None),
            or_(OutboxNotification.correlation_id.is_(None), OutboxNotification.correlation_id == ""),
            or_(
                OutboxNotification.provider_message_id.is_(None),
                OutboxNotification.provider_message_id == "",
            ),
        ),
    )
    counts["notification_log_mapping_gaps"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(NotificationLog)
        .where(
            NotificationLog.candidate_tg_id.is_(None),
            or_(NotificationLog.provider_message_id.is_(None), NotificationLog.provider_message_id == ""),
        ),
    )

    counts["detailization_without_slot_anchor"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(DetailizationEntry)
        .where(
            DetailizationEntry.is_deleted.is_(False),
            DetailizationEntry.slot_assignment_id.is_(None),
            DetailizationEntry.slot_id.is_(None),
        ),
    )

    counts["ai_outputs_unmappable"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(AIOutput)
        .where(
            or_(
                AIOutput.scope_type != "candidate",
                not_(
                    select(func.count())
                    .select_from(User)
                    .where(User.id == AIOutput.scope_id)
                    .scalar_subquery()
                    > 0
                ),
            )
        ),
    )
    counts["ai_request_logs_unmappable"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(AIRequestLog)
        .where(
            or_(
                AIRequestLog.scope_type != "candidate",
                not_(
                    select(func.count())
                    .select_from(User)
                    .where(User.id == AIRequestLog.scope_id)
                    .scalar_subquery()
                    > 0
                ),
            )
        ),
    )

    counts["journey_sessions_multiple_active_per_candidate"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(
            select(CandidateJourneySession.candidate_id)
            .where(CandidateJourneySession.status == "active")
            .group_by(CandidateJourneySession.candidate_id)
            .having(func.count() > 1)
            .subquery()
        ),
    )
    counts["journey_sessions_without_access_anchor"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(CandidateJourneySession)
        .where(
            CandidateJourneySession.status == "active",
            CandidateJourneySession.last_access_session_id.is_(None),
        ),
    )

    counts["invite_token_channel_conflicts"] = await _scalar_int(
        session,
        select(func.count())
        .select_from(
            select(CandidateInviteToken.candidate_id, CandidateInviteToken.channel)
            .where(CandidateInviteToken.status == "active")
            .group_by(CandidateInviteToken.candidate_id, CandidateInviteToken.channel)
            .having(func.count() > 1)
            .subquery()
        ),
    )

    blockers: list[BucketSummary] = []
    warnings: list[BucketSummary] = []
    ambiguous_cases: list[BucketSummary] = []

    def add_bucket(target: list[BucketSummary], key: str, severity: str, count: int, summary: str, recommendation: str) -> None:
        if count > 0:
            target.append(
                BucketSummary(
                    key=key,
                    severity=severity,
                    count=count,
                    summary=summary,
                    recommendation=recommendation,
                )
            )

    telegram_identity_conflicts = (
        counts["telegram_id_duplicate_groups"]
        + counts["telegram_user_id_duplicate_groups"]
        + counts["chat_messages_telegram_cross_candidate_groups"]
        + counts["invite_token_telegram_claim_conflicts"]
    )
    hh_identity_conflicts = (
        counts["hh_resume_duplicate_groups"] + counts["hh_negotiation_duplicate_groups"]
    )
    scheduling_conflicts = (
        counts["slot_assignments_without_candidate_anchor"]
        + counts["slot_assignments_tg_only_without_user_match"]
        + counts["slot_assignment_active_conflicts_by_candidate"]
        + counts["slot_assignment_active_conflicts_by_candidate_tg"]
    )

    add_bucket(
        blockers,
        "phone_normalized_duplicates",
        "blocker",
        counts["phone_normalized_duplicate_groups"],
        "Several users share the same normalized phone and cannot be auto-owned safely.",
        "Repair phone ownership before resolver hardening or merge review.",
    )
    add_bucket(
        blockers,
        "telegram_identity_conflicts",
        "blocker",
        telegram_identity_conflicts,
        "Telegram identity evidence maps to multiple candidates or multiple candidate chains.",
        "Review Telegram ownership and invite claims before channel identity hardening.",
    )
    add_bucket(
        blockers,
        "max_user_id_conflicts",
        "blocker",
        counts["max_user_id_duplicate_groups"],
        "MAX identities are shared by multiple candidates.",
        "Clean duplicate MAX ownership before enabling MAX-aware resolver logic.",
    )
    add_bucket(
        blockers,
        "scheduling_link_conflicts",
        "blocker",
        scheduling_conflicts,
        "Scheduling anchors are missing or duplicated and would make application binding unsafe.",
        "Repair slot assignment ownership before slot-driven resolver rollout.",
    )
    add_bucket(
        blockers,
        "invite_token_channel_conflicts",
        "blocker",
        counts["invite_token_channel_conflicts"],
        "Active invite tokens collide per candidate/channel and can create duplicate access anchors.",
        "Supersede duplicate active invite chains before access/session backfill.",
    )

    add_bucket(
        warnings,
        "hh_identity_conflicts",
        "warning",
        hh_identity_conflicts,
        "HH resume or negotiation identifiers are not unique enough for straight-through application binding.",
        "Reconcile HH identity rows before strict requisition binding.",
    )
    add_bucket(
        warnings,
        "weak_demand_only_candidates",
        "warning",
        counts["users_with_source_or_desired_position_no_vacancy"],
        "Candidates have weak demand signals but no deterministic vacancy anchor.",
        "Backfill candidate-scoped applications with null requisition instead of guessing demand.",
    )
    add_bucket(
        warnings,
        "city_only_candidates",
        "warning",
        counts["users_with_city_no_vacancy"],
        "City is present without a deterministic demand anchor.",
        "Treat city as routing context only, not as requisition resolver input.",
    )
    add_bucket(
        warnings,
        "chat_candidate_mismatch",
        "warning",
        counts["chat_messages_candidate_mismatch"],
        "Chat rows reference Telegram users that do not match the linked candidate record.",
        "Keep these rows candidate-scoped only until message-thread backfill rules are validated.",
    )
    add_bucket(
        warnings,
        "detailization_without_slot_anchor",
        "warning",
        counts["detailization_without_slot_anchor"],
        "Detailization rows exist without slot or assignment anchors.",
        "Treat them as interview evidence only; do not auto-create interviews from them.",
    )
    add_bucket(
        warnings,
        "ai_provenance_gaps",
        "warning",
        counts["ai_outputs_unmappable"] + counts["ai_request_logs_unmappable"],
        "Part of the AI audit trail cannot map cleanly to candidate/application grain.",
        "Limit AI backfill to deterministic candidate-scoped records first.",
    )

    add_bucket(
        ambiguous_cases,
        "outbox_mapping_gaps",
        "ambiguous",
        counts["outbox_mapping_gaps"],
        "Outbox rows lack enough anchors to reconstruct deterministic delivery attempts.",
        "Leave these rows out of strict delivery backfill and track them in a manual review queue.",
    )
    add_bucket(
        ambiguous_cases,
        "notification_log_mapping_gaps",
        "ambiguous",
        counts["notification_log_mapping_gaps"],
        "Notification logs are only partially attributable to a future delivery attempt.",
        "Backfill them as advisory evidence or leave null-forward.",
    )
    add_bucket(
        ambiguous_cases,
        "journey_access_gaps",
        "ambiguous",
        counts["journey_sessions_multiple_active_per_candidate"]
        + counts["journey_sessions_without_access_anchor"],
        "Journey sessions do not yet map cleanly to access/session ownership.",
        "Keep historical journey rows progress-only and fill forward into new access/session tables.",
    )

    manual_review_queues: list[ManualReviewQueue] = []

    def add_queue(queue: str, trigger_count: int, reason: str) -> None:
        if trigger_count > 0:
            manual_review_queues.append(
                ManualReviewQueue(
                    queue=queue,
                    trigger_count=trigger_count,
                    reason=reason,
                )
            )

    add_queue(
        "identity_conflicts_review",
        counts["phone_normalized_duplicate_groups"]
        + telegram_identity_conflicts
        + counts["max_user_id_duplicate_groups"],
        "Resolve phone, Telegram and MAX ownership conflicts before strict resolver matching.",
    )
    add_queue(
        "ambiguous_demand_review",
        counts["users_with_source_or_desired_position_no_vacancy"] + counts["users_with_city_no_vacancy"],
        "Demand hints exist without deterministic requisition binding.",
    )
    add_queue(
        "scheduling_link_review",
        scheduling_conflicts,
        "Slot assignment anchors are missing, duplicated or unmatched.",
    )
    add_queue(
        "delivery_mapping_review",
        counts["chat_messages_candidate_mismatch"]
        + counts["outbox_mapping_gaps"]
        + counts["notification_log_mapping_gaps"],
        "Messaging artifacts cannot all be reconstructed into clean thread/delivery history.",
    )
    add_queue(
        "ai_provenance_review",
        counts["ai_outputs_unmappable"] + counts["ai_request_logs_unmappable"],
        "AI artifacts need candidate/application provenance review before backfill.",
    )
    add_queue(
        "journey_access_review",
        counts["journey_sessions_multiple_active_per_candidate"]
        + counts["journey_sessions_without_access_anchor"]
        + counts["invite_token_channel_conflicts"],
        "Journey and access rows need cleanup before access/session hardening.",
    )

    return BackfillReadinessReport(
        generated_at=datetime.now(UTC).isoformat(),
        counts=counts,
        blockers=blockers,
        warnings=warnings,
        ambiguous_cases=ambiguous_cases,
        manual_review_queues=manual_review_queues,
    )


def render_backfill_readiness_text(report: BackfillReadinessReport) -> str:
    lines = [
        "Phase A backfill readiness",
        f"Generated at: {report.generated_at}",
        "",
        "Counts",
    ]
    for key, value in sorted(report.counts.items()):
        lines.append(f"- {key}: {value}")

    def render_section(title: str, entries: list[BucketSummary]) -> None:
        lines.append("")
        lines.append(title)
        if not entries:
            lines.append("- none")
            return
        for item in entries:
            lines.append(f"- {item.key}: {item.count} ({item.summary})")

    render_section("Blockers", report.blockers)
    render_section("Warnings", report.warnings)
    render_section("Ambiguous cases", report.ambiguous_cases)

    lines.append("")
    lines.append("Manual review queues")
    if not report.manual_review_queues:
        lines.append("- none")
    else:
        for item in report.manual_review_queues:
            lines.append(f"- {item.queue}: {item.trigger_count} ({item.reason})")
    return "\n".join(lines)


def _emit_execution_error(message: str, exc: BaseException | None = None) -> None:
    print(message, file=sys.stderr)
    if exc is not None:
        print(f"Error class: {type(exc).__name__}", file=sys.stderr)


async def _run(args: argparse.Namespace) -> int:
    try:
        async with async_session() as session:
            report = await collect_backfill_readiness_report(session)
    except (OperationalError, ProgrammingError) as exc:
        _emit_execution_error(
            "Phase A backfill readiness audit failed: database schema is unavailable or not migrated. "
            "Point DATABASE_URL to an initialized RecruitSmart database before running this audit.",
            exc,
        )
        return 1
    except SQLAlchemyError as exc:
        _emit_execution_error(
            "Phase A backfill readiness audit failed: SQLAlchemy execution error.",
            exc,
        )
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        _emit_execution_error(
            "Phase A backfill readiness audit failed: unexpected execution error.",
            exc,
        )
        return 1

    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_backfill_readiness_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run(_parse_args())))
