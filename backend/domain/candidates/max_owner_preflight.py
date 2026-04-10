from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    CandidateInviteToken,
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    ChatMessage,
    ChatMessageDirection,
    User,
)


def normalize_max_owner_value(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _trimmed_or_null(column):
    return func.nullif(func.trim(column), "")


@dataclass(frozen=True)
class MaxOwnerCandidateSnapshot:
    candidate_pk: int
    candidate_uuid: str | None
    fio: str | None
    source: str | None
    messenger_platform: str | None
    raw_max_user_id: str | None
    normalized_max_user_id: str | None
    candidate_status: str | None
    lifecycle_state: str | None
    last_activity: datetime | None
    chat_count: int
    max_chat_count: int
    inbound_chat_count: int
    outbound_chat_count: int
    active_journey_count: int
    active_max_journey_count: int
    max_invite_count: int
    active_max_invite_count: int
    used_max_invite_count: int
    latest_used_invite_external_id: str | None
    latest_used_invite_at: datetime | None
    latest_max_invite_status: str | None

    @property
    def has_whitespace_only_owner(self) -> bool:
        return self.raw_max_user_id is not None and self.normalized_max_user_id is None

    @property
    def raw_trimmed_changed(self) -> bool:
        if self.raw_max_user_id is None:
            return False
        return self.raw_max_user_id != self.raw_max_user_id.strip()

    @property
    def has_max_evidence(self) -> bool:
        return any(
            (
                self.max_chat_count > 0,
                self.used_max_invite_count > 0,
                self.active_max_journey_count > 0,
            )
        )

    @property
    def evidence_score(self) -> int:
        score = 0
        if self.max_chat_count > 0:
            score += 5
        if self.used_max_invite_count > 0:
            score += 4
        if self.active_max_journey_count > 0:
            score += 3
        if str(self.messenger_platform or "").strip().lower() == "max":
            score += 2
        if self.normalized_max_user_id and self.raw_max_user_id == self.normalized_max_user_id:
            score += 1
        if str(self.source or "").strip().lower() == "max_bot_public":
            score += 1
        return score

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_pk": self.candidate_pk,
            "candidate_uuid": self.candidate_uuid,
            "fio": self.fio,
            "source": self.source,
            "messenger_platform": self.messenger_platform,
            "raw_max_user_id": self.raw_max_user_id,
            "normalized_max_user_id": self.normalized_max_user_id,
            "candidate_status": self.candidate_status,
            "lifecycle_state": self.lifecycle_state,
            "last_activity": _iso(self.last_activity),
            "chat_count": self.chat_count,
            "max_chat_count": self.max_chat_count,
            "inbound_chat_count": self.inbound_chat_count,
            "outbound_chat_count": self.outbound_chat_count,
            "active_journey_count": self.active_journey_count,
            "active_max_journey_count": self.active_max_journey_count,
            "max_invite_count": self.max_invite_count,
            "active_max_invite_count": self.active_max_invite_count,
            "used_max_invite_count": self.used_max_invite_count,
            "latest_used_invite_external_id": self.latest_used_invite_external_id,
            "latest_used_invite_at": _iso(self.latest_used_invite_at),
            "latest_max_invite_status": self.latest_max_invite_status,
            "has_max_evidence": self.has_max_evidence,
            "evidence_score": self.evidence_score,
            "raw_trimmed_changed": self.raw_trimmed_changed,
            "has_whitespace_only_owner": self.has_whitespace_only_owner,
        }


@dataclass(frozen=True)
class DuplicateOwnerGroup:
    normalized_max_user_id: str
    candidate_count: int
    records: tuple[MaxOwnerCandidateSnapshot, ...]
    cleanup_bucket: str
    blocks_unique_index: bool
    expected_cleanup_action: str
    reason_codes: tuple[str, ...]
    authoritative_candidate_pk: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_max_user_id": self.normalized_max_user_id,
            "candidate_count": self.candidate_count,
            "cleanup_bucket": self.cleanup_bucket,
            "blocks_unique_index": self.blocks_unique_index,
            "expected_cleanup_action": self.expected_cleanup_action,
            "reason_codes": list(self.reason_codes),
            "authoritative_candidate_pk": self.authoritative_candidate_pk,
            "blast_radius": {
                "excess_owner_rows": max(0, self.candidate_count - 1),
                "chat_messages": sum(item.chat_count for item in self.records),
                "max_chat_messages": sum(item.max_chat_count for item in self.records),
                "used_max_invites": sum(item.used_max_invite_count for item in self.records),
                "active_max_journeys": sum(item.active_max_journey_count for item in self.records),
            },
            "records": [item.to_dict() for item in self.records],
        }


@dataclass(frozen=True)
class MaxOwnerWhitespaceAnomaly:
    anomaly_kind: str
    record: MaxOwnerCandidateSnapshot
    cleanup_bucket: str
    blocks_unique_index: bool
    expected_cleanup_action: str
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_kind": self.anomaly_kind,
            "cleanup_bucket": self.cleanup_bucket,
            "blocks_unique_index": self.blocks_unique_index,
            "expected_cleanup_action": self.expected_cleanup_action,
            "reason_codes": list(self.reason_codes),
            "record": self.record.to_dict(),
        }


@dataclass(frozen=True)
class MaxOwnerConflictCase:
    conflict_kind: str
    record: MaxOwnerCandidateSnapshot
    conflicting_external_id: str | None
    cleanup_bucket: str
    blocks_unique_index: bool
    expected_cleanup_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_kind": self.conflict_kind,
            "conflicting_external_id": self.conflicting_external_id,
            "cleanup_bucket": self.cleanup_bucket,
            "blocks_unique_index": self.blocks_unique_index,
            "expected_cleanup_action": self.expected_cleanup_action,
            "record": self.record.to_dict(),
        }


@dataclass(frozen=True)
class MaxOwnerBlastRadius:
    total_max_linked_candidates: int
    duplicate_groups: int
    duplicate_candidate_rows: int
    duplicate_excess_owner_rows: int
    duplicate_chat_messages: int
    duplicate_max_chat_messages: int
    duplicate_used_max_invites: int
    duplicate_active_max_journeys: int
    whitespace_anomalies: int
    blank_or_whitespace_only_rows: int
    trim_only_rows: int
    ownership_conflicts: int
    safe_auto_cleanup_groups: int
    safe_auto_cleanup_rows: int
    manual_review_groups: int
    manual_review_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_max_linked_candidates": self.total_max_linked_candidates,
            "duplicate_groups": self.duplicate_groups,
            "duplicate_candidate_rows": self.duplicate_candidate_rows,
            "duplicate_excess_owner_rows": self.duplicate_excess_owner_rows,
            "duplicate_chat_messages": self.duplicate_chat_messages,
            "duplicate_max_chat_messages": self.duplicate_max_chat_messages,
            "duplicate_used_max_invites": self.duplicate_used_max_invites,
            "duplicate_active_max_journeys": self.duplicate_active_max_journeys,
            "whitespace_anomalies": self.whitespace_anomalies,
            "blank_or_whitespace_only_rows": self.blank_or_whitespace_only_rows,
            "trim_only_rows": self.trim_only_rows,
            "ownership_conflicts": self.ownership_conflicts,
            "safe_auto_cleanup_groups": self.safe_auto_cleanup_groups,
            "safe_auto_cleanup_rows": self.safe_auto_cleanup_rows,
            "manual_review_groups": self.manual_review_groups,
            "manual_review_rows": self.manual_review_rows,
        }


@dataclass(frozen=True)
class MaxOwnerPreflightReport:
    generated_at: datetime
    sample_limit: int
    ready_for_unique_index: bool
    blocking_checks: tuple[str, ...]
    requirements_before_unique_index: tuple[str, ...]
    blast_radius: MaxOwnerBlastRadius
    duplicate_groups: tuple[DuplicateOwnerGroup, ...]
    whitespace_anomalies: tuple[MaxOwnerWhitespaceAnomaly, ...]
    ownership_conflicts: tuple[MaxOwnerConflictCase, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": _iso(self.generated_at),
            "sample_limit": self.sample_limit,
            "ready_for_unique_index": self.ready_for_unique_index,
            "blocking_checks": list(self.blocking_checks),
            "requirements_before_unique_index": list(self.requirements_before_unique_index),
            "blast_radius": self.blast_radius.to_dict(),
            "duplicate_groups": [item.to_dict() for item in self.duplicate_groups],
            "whitespace_anomalies": [item.to_dict() for item in self.whitespace_anomalies],
            "ownership_conflicts": [item.to_dict() for item in self.ownership_conflicts],
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _coerce_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _candidate_snapshot_statement():
    chat_stats = (
        select(
            ChatMessage.candidate_id.label("candidate_pk"),
            func.count(ChatMessage.id).label("chat_count"),
            func.sum(case((ChatMessage.channel == "max", 1), else_=0)).label("max_chat_count"),
            func.sum(
                case((ChatMessage.direction == ChatMessageDirection.INBOUND.value, 1), else_=0)
            ).label("inbound_chat_count"),
            func.sum(
                case((ChatMessage.direction == ChatMessageDirection.OUTBOUND.value, 1), else_=0)
            ).label("outbound_chat_count"),
        )
        .group_by(ChatMessage.candidate_id)
        .subquery()
    )

    invite_stats = (
        select(
            CandidateInviteToken.candidate_id.label("candidate_uuid"),
            func.sum(case((CandidateInviteToken.channel == "max", 1), else_=0)).label("max_invite_count"),
            func.sum(
                case(
                    (
                        and_(
                            CandidateInviteToken.channel == "max",
                            CandidateInviteToken.status == "active",
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("active_max_invite_count"),
            func.sum(
                case(
                    (
                        and_(
                            CandidateInviteToken.channel == "max",
                            CandidateInviteToken.status == "used",
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("used_max_invite_count"),
        )
        .group_by(CandidateInviteToken.candidate_id)
        .subquery()
    )

    latest_used_invite_ranked = (
        select(
            CandidateInviteToken.candidate_id.label("candidate_uuid"),
            _trimmed_or_null(CandidateInviteToken.used_by_external_id).label("latest_used_invite_external_id"),
            CandidateInviteToken.used_at.label("latest_used_invite_at"),
            CandidateInviteToken.status.label("latest_max_invite_status"),
            func.row_number()
            .over(
                partition_by=CandidateInviteToken.candidate_id,
                order_by=(CandidateInviteToken.used_at.desc(), CandidateInviteToken.id.desc()),
            )
            .label("row_no"),
        )
        .where(
            CandidateInviteToken.channel == "max",
            _trimmed_or_null(CandidateInviteToken.used_by_external_id).is_not(None),
        )
        .subquery()
    )
    latest_used_invite = (
        select(
            latest_used_invite_ranked.c.candidate_uuid,
            latest_used_invite_ranked.c.latest_used_invite_external_id,
            latest_used_invite_ranked.c.latest_used_invite_at,
            latest_used_invite_ranked.c.latest_max_invite_status,
        )
        .where(latest_used_invite_ranked.c.row_no == 1)
        .subquery()
    )

    journey_stats = (
        select(
            CandidateJourneySession.candidate_id.label("candidate_pk"),
            func.sum(
                case(
                    (
                        CandidateJourneySession.status == CandidateJourneySessionStatus.ACTIVE.value,
                        1,
                    ),
                    else_=0,
                )
            ).label("active_journey_count"),
            func.sum(
                case(
                    (
                        and_(
                            CandidateJourneySession.status == CandidateJourneySessionStatus.ACTIVE.value,
                            CandidateJourneySession.entry_channel == "max",
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("active_max_journey_count"),
        )
        .group_by(CandidateJourneySession.candidate_id)
        .subquery()
    )

    return (
        select(
            User.id.label("candidate_pk"),
            User.candidate_id.label("candidate_uuid"),
            User.fio.label("fio"),
            User.source.label("source"),
            User.messenger_platform.label("messenger_platform"),
            User.max_user_id.label("raw_max_user_id"),
            _trimmed_or_null(User.max_user_id).label("normalized_max_user_id"),
            User.candidate_status.label("candidate_status"),
            User.lifecycle_state.label("lifecycle_state"),
            User.last_activity.label("last_activity"),
            func.coalesce(chat_stats.c.chat_count, 0).label("chat_count"),
            func.coalesce(chat_stats.c.max_chat_count, 0).label("max_chat_count"),
            func.coalesce(chat_stats.c.inbound_chat_count, 0).label("inbound_chat_count"),
            func.coalesce(chat_stats.c.outbound_chat_count, 0).label("outbound_chat_count"),
            func.coalesce(journey_stats.c.active_journey_count, 0).label("active_journey_count"),
            func.coalesce(journey_stats.c.active_max_journey_count, 0).label("active_max_journey_count"),
            func.coalesce(invite_stats.c.max_invite_count, 0).label("max_invite_count"),
            func.coalesce(invite_stats.c.active_max_invite_count, 0).label("active_max_invite_count"),
            func.coalesce(invite_stats.c.used_max_invite_count, 0).label("used_max_invite_count"),
            latest_used_invite.c.latest_used_invite_external_id,
            latest_used_invite.c.latest_used_invite_at,
            latest_used_invite.c.latest_max_invite_status,
        )
        .outerjoin(chat_stats, chat_stats.c.candidate_pk == User.id)
        .outerjoin(journey_stats, journey_stats.c.candidate_pk == User.id)
        .outerjoin(invite_stats, invite_stats.c.candidate_uuid == User.candidate_id)
        .outerjoin(latest_used_invite, latest_used_invite.c.candidate_uuid == User.candidate_id)
    )


def _snapshot_from_row(row) -> MaxOwnerCandidateSnapshot:
    candidate_status = row.candidate_status
    if candidate_status is not None and hasattr(candidate_status, "value"):
        candidate_status = candidate_status.value
    return MaxOwnerCandidateSnapshot(
        candidate_pk=int(row.candidate_pk),
        candidate_uuid=str(row.candidate_uuid) if row.candidate_uuid is not None else None,
        fio=str(row.fio) if row.fio is not None else None,
        source=str(row.source) if row.source is not None else None,
        messenger_platform=str(row.messenger_platform) if row.messenger_platform is not None else None,
        raw_max_user_id=str(row.raw_max_user_id) if row.raw_max_user_id is not None else None,
        normalized_max_user_id=(
            str(row.normalized_max_user_id) if row.normalized_max_user_id is not None else None
        ),
        candidate_status=str(candidate_status) if candidate_status is not None else None,
        lifecycle_state=str(row.lifecycle_state) if row.lifecycle_state is not None else None,
        last_activity=row.last_activity,
        chat_count=int(row.chat_count or 0),
        max_chat_count=int(row.max_chat_count or 0),
        inbound_chat_count=int(row.inbound_chat_count or 0),
        outbound_chat_count=int(row.outbound_chat_count or 0),
        active_journey_count=int(row.active_journey_count or 0),
        active_max_journey_count=int(row.active_max_journey_count or 0),
        max_invite_count=int(row.max_invite_count or 0),
        active_max_invite_count=int(row.active_max_invite_count or 0),
        used_max_invite_count=int(row.used_max_invite_count or 0),
        latest_used_invite_external_id=(
            str(row.latest_used_invite_external_id) if row.latest_used_invite_external_id is not None else None
        ),
        latest_used_invite_at=row.latest_used_invite_at,
        latest_max_invite_status=(
            str(row.latest_max_invite_status) if row.latest_max_invite_status is not None else None
        ),
    )


async def load_candidates_by_max_owner(
    session: AsyncSession,
    *,
    max_user_id: str,
) -> list[User]:
    normalized = normalize_max_owner_value(max_user_id)
    if normalized is None:
        return []
    rows = await session.scalars(
        select(User)
        .where(_trimmed_or_null(User.max_user_id) == normalized)
        .order_by(User.id.asc())
    )
    return list(rows.all())


def _classify_duplicate_group(
    normalized_max_user_id: str,
    records: list[MaxOwnerCandidateSnapshot],
) -> DuplicateOwnerGroup:
    ordered = sorted(
        records,
        key=lambda item: (
            item.evidence_score,
            _coerce_utc(item.last_activity),
            -item.candidate_pk,
        ),
        reverse=True,
    )
    authoritative = ordered[0] if ordered else None
    manual_reasons: list[str] = []

    evidence_rows = [
        item
        for item in records
        if item.has_max_evidence or str(item.messenger_platform or "").strip().lower() == "max"
    ]
    distinct_used_invite_external_ids = {
        item.latest_used_invite_external_id
        for item in records
        if item.latest_used_invite_external_id
    }
    mismatched_invite_rows = [
        item
        for item in records
        if item.latest_used_invite_external_id
        and item.normalized_max_user_id
        and item.latest_used_invite_external_id != item.normalized_max_user_id
    ]

    if len(evidence_rows) != 1:
        manual_reasons.append("multiple_records_have_max_evidence")
    if len(distinct_used_invite_external_ids) > 1:
        manual_reasons.append("multiple_used_invite_external_ids")
    if mismatched_invite_rows:
        manual_reasons.append("invite_used_by_mismatch")

    if not manual_reasons:
        cleanup_bucket = "safe_auto_cleanup"
        reason_codes = ("single_authoritative_record",)
        if any(item.raw_trimmed_changed for item in records):
            reason_codes = (*reason_codes, "trim_collision_present")
        expected_cleanup_action = (
            "Preserve the authoritative candidate and clear `max_user_id` on secondary rows "
            "only after verifying they have no MAX chats, used MAX invites, or active MAX journeys."
        )
    else:
        cleanup_bucket = "manual_review_only"
        reason_codes = tuple(manual_reasons)
        expected_cleanup_action = (
            "Manual review required: inspect chats, invites, and journey ownership, then merge or "
            "relink candidates before clearing any secondary `max_user_id`."
        )

    return DuplicateOwnerGroup(
        normalized_max_user_id=normalized_max_user_id,
        candidate_count=len(records),
        records=tuple(ordered),
        cleanup_bucket=cleanup_bucket,
        blocks_unique_index=True,
        expected_cleanup_action=expected_cleanup_action,
        reason_codes=reason_codes,
        authoritative_candidate_pk=authoritative.candidate_pk if authoritative is not None else None,
    )


def _classify_whitespace_anomaly(
    record: MaxOwnerCandidateSnapshot,
    *,
    duplicate_owner_exists: bool,
) -> MaxOwnerWhitespaceAnomaly:
    reason_codes: list[str] = []
    if record.has_whitespace_only_owner:
        anomaly_kind = "blank_or_whitespace_only"
        if record.has_max_evidence or record.latest_used_invite_external_id or str(record.messenger_platform or "").strip().lower() == "max":
            cleanup_bucket = "manual_review_only"
            reason_codes.append("max_evidence_present")
            expected_cleanup_action = (
                "Manual review required: reconcile messenger preference, invite usage, and MAX activity "
                "before clearing whitespace-only `max_user_id`."
            )
        else:
            cleanup_bucket = "safe_auto_cleanup"
            reason_codes.append("blank_owner_without_max_evidence")
            expected_cleanup_action = "Set `max_user_id` to NULL."
    else:
        anomaly_kind = "trim_only"
        if duplicate_owner_exists:
            cleanup_bucket = "manual_review_only"
            reason_codes.append("trimmed_value_already_owned")
            expected_cleanup_action = (
                "Do not trim in place until the duplicate-owner group is resolved, because the trimmed value "
                "already belongs to another candidate."
            )
        elif (
            record.latest_used_invite_external_id
            and record.normalized_max_user_id
            and record.latest_used_invite_external_id != record.normalized_max_user_id
        ):
            cleanup_bucket = "manual_review_only"
            reason_codes.append("invite_used_by_mismatch")
            expected_cleanup_action = (
                "Manual review required: latest used MAX invite disagrees with the trimmed `max_user_id`."
            )
        else:
            cleanup_bucket = "safe_auto_cleanup"
            reason_codes.append("trim_only_without_conflict")
            expected_cleanup_action = "Trim surrounding whitespace in place, then re-run the duplicate-owner audit."

    return MaxOwnerWhitespaceAnomaly(
        anomaly_kind=anomaly_kind,
        record=record,
        cleanup_bucket=cleanup_bucket,
        blocks_unique_index=True,
        expected_cleanup_action=expected_cleanup_action,
        reason_codes=tuple(reason_codes),
    )


def _build_conflict_cases(
    records: list[MaxOwnerCandidateSnapshot],
) -> list[MaxOwnerConflictCase]:
    result: list[MaxOwnerConflictCase] = []
    seen: set[tuple[int, str]] = set()
    for record in records:
        normalized_platform = str(record.messenger_platform or "").strip().lower()
        if record.latest_used_invite_external_id and record.normalized_max_user_id is None:
            key = (record.candidate_pk, "used_invite_without_candidate_owner")
            if key not in seen:
                seen.add(key)
                result.append(
                    MaxOwnerConflictCase(
                        conflict_kind="used_invite_without_candidate_owner",
                        record=record,
                        conflicting_external_id=record.latest_used_invite_external_id,
                        cleanup_bucket="manual_review_only",
                        blocks_unique_index=True,
                        expected_cleanup_action=(
                            "Manual review required: candidate has a used MAX invite but no normalized `max_user_id`; "
                            "restore the correct owner or explicitly clear the stale invite ownership record."
                        ),
                    )
                )
        if (
            record.latest_used_invite_external_id
            and record.normalized_max_user_id
            and record.latest_used_invite_external_id != record.normalized_max_user_id
        ):
            key = (record.candidate_pk, "invite_used_by_mismatch")
            if key not in seen:
                seen.add(key)
                result.append(
                    MaxOwnerConflictCase(
                        conflict_kind="invite_used_by_mismatch",
                        record=record,
                        conflicting_external_id=record.latest_used_invite_external_id,
                        cleanup_bucket="manual_review_only",
                        blocks_unique_index=True,
                        expected_cleanup_action=(
                            "Manual review required: latest used MAX invite points to a different external id than "
                            "the candidate row currently owns."
                        ),
                    )
                )
        if normalized_platform == "max" and record.normalized_max_user_id is None:
            key = (record.candidate_pk, "preferred_max_without_owner")
            if key not in seen:
                seen.add(key)
                result.append(
                    MaxOwnerConflictCase(
                        conflict_kind="preferred_max_without_owner",
                        record=record,
                        conflicting_external_id=None,
                        cleanup_bucket="manual_review_only",
                        blocks_unique_index=True,
                        expected_cleanup_action=(
                            "Manual review required: candidate prefers MAX but has no normalized `max_user_id`; "
                            "fix ownership before relying on MAX delivery."
                        ),
                    )
                )
    return result


async def collect_max_owner_preflight_report(
    session: AsyncSession,
    *,
    sample_limit: int = 50,
) -> MaxOwnerPreflightReport:
    sample_limit = max(1, int(sample_limit))
    normalized_max_user_id = _trimmed_or_null(User.max_user_id)

    duplicate_groups_query = (
        select(
            normalized_max_user_id.label("normalized_max_user_id"),
            func.count(User.id).label("candidate_count"),
        )
        .where(normalized_max_user_id.is_not(None))
        .group_by(normalized_max_user_id)
        .having(func.count(User.id) > 1)
        .subquery()
    )

    duplicate_rows = (
        await session.execute(
            _candidate_snapshot_statement()
            .join(
                duplicate_groups_query,
                duplicate_groups_query.c.normalized_max_user_id == normalized_max_user_id,
            )
            .order_by(
                duplicate_groups_query.c.normalized_max_user_id.asc(),
                User.id.asc(),
            )
        )
    ).all()

    grouped_duplicates: dict[str, list[MaxOwnerCandidateSnapshot]] = {}
    for row in duplicate_rows:
        snapshot = _snapshot_from_row(row)
        key = str(row.normalized_max_user_id)
        grouped_duplicates.setdefault(key, []).append(snapshot)

    duplicate_groups = [
        _classify_duplicate_group(key, records)
        for key, records in grouped_duplicates.items()
    ]
    duplicate_groups.sort(key=lambda item: (item.cleanup_bucket != "manual_review_only", item.normalized_max_user_id))

    duplicate_owner_values = set(grouped_duplicates.keys())
    whitespace_rows = (
        await session.execute(
            _candidate_snapshot_statement()
            .where(
                User.max_user_id.is_not(None),
                or_(
                    func.trim(User.max_user_id) == "",
                    User.max_user_id != func.trim(User.max_user_id),
                ),
            )
            .order_by(User.id.asc())
        )
    ).all()
    whitespace_anomalies = [
        _classify_whitespace_anomaly(
            _snapshot_from_row(row),
            duplicate_owner_exists=(
                row.normalized_max_user_id is not None
                and str(row.normalized_max_user_id) in duplicate_owner_values
            ),
        )
        for row in whitespace_rows
    ]

    # Reuse the same projection for conflict classification to keep candidate-level evidence consistent.
    all_candidate_rows = (
        await session.execute(
            _candidate_snapshot_statement()
            .where(
                or_(
                    normalized_max_user_id.is_not(None),
                    User.max_user_id.is_not(None),
                    func.lower(func.coalesce(User.messenger_platform, "")) == "max",
                )
            )
            .order_by(User.id.asc())
        )
    ).all()
    all_snapshots = [_snapshot_from_row(row) for row in all_candidate_rows]
    ownership_conflicts = _build_conflict_cases(all_snapshots)

    total_max_linked_candidates = int(
        await session.scalar(
            select(func.count(User.id)).where(normalized_max_user_id.is_not(None))
        )
        or 0
    )

    safe_auto_cleanup_rows = sum(
        max(0, group.candidate_count - 1)
        for group in duplicate_groups
        if group.cleanup_bucket == "safe_auto_cleanup"
    ) + sum(
        1 for item in whitespace_anomalies if item.cleanup_bucket == "safe_auto_cleanup"
    )
    manual_review_rows = sum(
        group.candidate_count
        for group in duplicate_groups
        if group.cleanup_bucket == "manual_review_only"
    ) + len(ownership_conflicts) + sum(
        1 for item in whitespace_anomalies if item.cleanup_bucket == "manual_review_only"
    )

    blast_radius = MaxOwnerBlastRadius(
        total_max_linked_candidates=total_max_linked_candidates,
        duplicate_groups=len(duplicate_groups),
        duplicate_candidate_rows=sum(group.candidate_count for group in duplicate_groups),
        duplicate_excess_owner_rows=sum(max(0, group.candidate_count - 1) for group in duplicate_groups),
        duplicate_chat_messages=sum(sum(item.chat_count for item in group.records) for group in duplicate_groups),
        duplicate_max_chat_messages=sum(
            sum(item.max_chat_count for item in group.records) for group in duplicate_groups
        ),
        duplicate_used_max_invites=sum(
            sum(item.used_max_invite_count for item in group.records) for group in duplicate_groups
        ),
        duplicate_active_max_journeys=sum(
            sum(item.active_max_journey_count for item in group.records) for group in duplicate_groups
        ),
        whitespace_anomalies=len(whitespace_anomalies),
        blank_or_whitespace_only_rows=sum(
            1 for item in whitespace_anomalies if item.anomaly_kind == "blank_or_whitespace_only"
        ),
        trim_only_rows=sum(1 for item in whitespace_anomalies if item.anomaly_kind == "trim_only"),
        ownership_conflicts=len(ownership_conflicts),
        safe_auto_cleanup_groups=sum(
            1 for group in duplicate_groups if group.cleanup_bucket == "safe_auto_cleanup"
        ),
        safe_auto_cleanup_rows=safe_auto_cleanup_rows,
        manual_review_groups=sum(
            1 for group in duplicate_groups if group.cleanup_bucket == "manual_review_only"
        ),
        manual_review_rows=manual_review_rows,
    )

    blocking_checks: list[str] = []
    if duplicate_groups:
        blocking_checks.append("duplicate_max_user_id_groups")
    if whitespace_anomalies:
        blocking_checks.append("blank_or_whitespace_max_user_id")
    if ownership_conflicts:
        blocking_checks.append("conflicting_candidate_ownership")

    requirements_before_unique_index = (
        "No duplicate groups remain for normalized `trim(max_user_id)`.",
        "Every non-null `max_user_id` is already trimmed and non-empty.",
        "No candidate has MAX invite ownership that disagrees with `users.max_user_id`.",
        "Every candidate with preferred MAX channel has exactly one normalized MAX owner.",
    )

    return MaxOwnerPreflightReport(
        generated_at=datetime.now(UTC),
        sample_limit=sample_limit,
        ready_for_unique_index=not blocking_checks,
        blocking_checks=tuple(blocking_checks),
        requirements_before_unique_index=requirements_before_unique_index,
        blast_radius=blast_radius,
        duplicate_groups=tuple(duplicate_groups[:sample_limit]),
        whitespace_anomalies=tuple(whitespace_anomalies[:sample_limit]),
        ownership_conflicts=tuple(ownership_conflicts[:sample_limit]),
    )


def render_max_owner_preflight_text(report: MaxOwnerPreflightReport) -> str:
    lines = [
        "MAX owner preflight",
        f"generated_at: {report.generated_at.isoformat()}",
        f"ready_for_unique_index: {'yes' if report.ready_for_unique_index else 'no'}",
        f"blocking_checks: {', '.join(report.blocking_checks) if report.blocking_checks else 'none'}",
        "",
        "Blast radius:",
        f"- total_max_linked_candidates: {report.blast_radius.total_max_linked_candidates}",
        f"- duplicate_groups: {report.blast_radius.duplicate_groups}",
        f"- duplicate_candidate_rows: {report.blast_radius.duplicate_candidate_rows}",
        f"- duplicate_excess_owner_rows: {report.blast_radius.duplicate_excess_owner_rows}",
        f"- duplicate_max_chat_messages: {report.blast_radius.duplicate_max_chat_messages}",
        f"- duplicate_used_max_invites: {report.blast_radius.duplicate_used_max_invites}",
        f"- duplicate_active_max_journeys: {report.blast_radius.duplicate_active_max_journeys}",
        f"- whitespace_anomalies: {report.blast_radius.whitespace_anomalies}",
        f"- ownership_conflicts: {report.blast_radius.ownership_conflicts}",
        "",
        "Requirements before unique index:",
    ]
    lines.extend(f"- {item}" for item in report.requirements_before_unique_index)

    if report.duplicate_groups:
        lines.extend(["", "Duplicate groups:"])
        for group in report.duplicate_groups:
            lines.append(
                f"- owner={group.normalized_max_user_id} "
                f"bucket={group.cleanup_bucket} "
                f"blocker={'yes' if group.blocks_unique_index else 'no'} "
                f"authoritative_candidate_pk={group.authoritative_candidate_pk}"
            )
            lines.append(f"  reasons={', '.join(group.reason_codes)}")
            lines.append(f"  action={group.expected_cleanup_action}")
            for record in group.records:
                lines.append(
                    "  "
                    f"candidate_pk={record.candidate_pk} "
                    f"uuid={record.candidate_uuid} "
                    f"raw={record.raw_max_user_id!r} "
                    f"platform={record.messenger_platform!r} "
                    f"evidence_score={record.evidence_score} "
                    f"max_chat_count={record.max_chat_count} "
                    f"used_max_invite_count={record.used_max_invite_count} "
                    f"active_max_journey_count={record.active_max_journey_count}"
                )

    if report.whitespace_anomalies:
        lines.extend(["", "Whitespace anomalies:"])
        for anomaly in report.whitespace_anomalies:
            record = anomaly.record
            lines.append(
                f"- candidate_pk={record.candidate_pk} "
                f"kind={anomaly.anomaly_kind} "
                f"bucket={anomaly.cleanup_bucket} "
                f"raw={record.raw_max_user_id!r} "
                f"normalized={record.normalized_max_user_id!r}"
            )
            lines.append(f"  reasons={', '.join(anomaly.reason_codes)}")
            lines.append(f"  action={anomaly.expected_cleanup_action}")

    if report.ownership_conflicts:
        lines.extend(["", "Ownership conflicts:"])
        for conflict in report.ownership_conflicts:
            record = conflict.record
            lines.append(
                f"- candidate_pk={record.candidate_pk} "
                f"kind={conflict.conflict_kind} "
                f"current_owner={record.normalized_max_user_id!r} "
                f"invite_owner={conflict.conflicting_external_id!r}"
            )
            lines.append(f"  action={conflict.expected_cleanup_action}")

    return "\n".join(lines)
