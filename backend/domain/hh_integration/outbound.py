"""Outbound CRM -> HH synchronization orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
from sqlalchemy import desc, select

from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.hh_integration.contracts import (
    HHIdentitySyncStatus,
    HHSyncDirection,
)
from backend.domain.hh_integration.jobs import enqueue_hh_sync_job
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    HHConnection,
    HHNegotiation,
)


class HHSyncIntent(str, Enum):
    NO_OP = "no_op"
    INVITE_TO_INTERVIEW = "invite_to_interview"
    REJECT_CANDIDATE = "reject_candidate"
    MARK_HIRED = "mark_hired"


_STATUS_TO_INTENT: dict[CandidateStatus, HHSyncIntent] = {
    CandidateStatus.INTERVIEW_SCHEDULED: HHSyncIntent.INVITE_TO_INTERVIEW,
    CandidateStatus.INTERVIEW_CONFIRMED: HHSyncIntent.INVITE_TO_INTERVIEW,
    CandidateStatus.INTERVIEW_DECLINED: HHSyncIntent.REJECT_CANDIDATE,
    CandidateStatus.TEST2_FAILED: HHSyncIntent.REJECT_CANDIDATE,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION: HHSyncIntent.REJECT_CANDIDATE,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: HHSyncIntent.REJECT_CANDIDATE,
    CandidateStatus.NOT_HIRED: HHSyncIntent.REJECT_CANDIDATE,
    CandidateStatus.HIRED: HHSyncIntent.MARK_HIRED,
}


@dataclass(frozen=True)
class CandidateHHLinkContext:
    connection: HHConnection | None
    identity: CandidateExternalIdentity | None
    negotiation: HHNegotiation | None


def resolve_hh_sync_intent(target_status: CandidateStatus) -> HHSyncIntent:
    return _STATUS_TO_INTENT.get(target_status, HHSyncIntent.NO_OP)


def should_sync_candidate_status(target_status: CandidateStatus) -> bool:
    return resolve_hh_sync_intent(target_status) != HHSyncIntent.NO_OP


def build_status_sync_idempotency_key(
    *,
    candidate_id: int,
    target_status: CandidateStatus,
    status_changed_at: datetime | None,
) -> str:
    changed_marker = status_changed_at.isoformat() if status_changed_at else "missing-status-changed-at"
    raw = f"candidate_status_sync:{candidate_id}:{target_status.value}:{changed_marker}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def load_candidate_hh_link_context(session, *, candidate_id: int) -> CandidateHHLinkContext:
    identity = (
        await session.execute(
            select(CandidateExternalIdentity).where(
                CandidateExternalIdentity.candidate_id == candidate_id,
                CandidateExternalIdentity.source == "hh",
            )
        )
    ).scalar_one_or_none()

    negotiation = None
    if identity is not None:
        negotiation = (
            await session.execute(
                select(HHNegotiation)
                .where(HHNegotiation.candidate_identity_id == identity.id)
                .order_by(desc(HHNegotiation.updated_at), desc(HHNegotiation.id))
                .limit(1)
            )
        ).scalar_one_or_none()

    connection = None
    connection_id = None
    if negotiation is not None and negotiation.connection_id is not None:
        connection_id = negotiation.connection_id
    elif identity is not None:
        connection_id = None

    if connection_id is not None:
        connection = await session.get(HHConnection, connection_id)
    if connection is None:
        connection = (
            await session.execute(
                select(HHConnection)
                .where(
                    HHConnection.principal_type == "admin",
                    HHConnection.status == "active",
                )
                .order_by(desc(HHConnection.updated_at), desc(HHConnection.id))
                .limit(1)
            )
        ).scalar_one_or_none()

    return CandidateHHLinkContext(
        connection=connection,
        identity=identity,
        negotiation=negotiation,
    )


async def enqueue_candidate_status_sync(
    session,
    *,
    candidate: User,
    target_status: CandidateStatus,
) -> tuple[object | None, bool]:
    intent = resolve_hh_sync_intent(target_status)
    if intent == HHSyncIntent.NO_OP:
        return None, False

    context = await load_candidate_hh_link_context(session, candidate_id=int(candidate.id))
    idempotency_key = build_status_sync_idempotency_key(
        candidate_id=int(candidate.id),
        target_status=target_status,
        status_changed_at=getattr(candidate, "status_changed_at", None),
    )

    payload = {
        "candidate_id": int(candidate.id),
        "candidate_status": target_status.value,
        "intent": intent.value,
        "identity_id": int(context.identity.id) if context.identity is not None else None,
        "negotiation_id": context.negotiation.external_negotiation_id if context.negotiation is not None else None,
        "vacancy_id": (
            context.identity.external_vacancy_id
            if context.identity is not None
            else getattr(candidate, "hh_vacancy_id", None)
        ),
    }

    if context.identity is None:
        candidate.hh_sync_status = HHIdentitySyncStatus.FAILED
        candidate.hh_sync_error = "identity_not_linked"
    else:
        candidate.hh_sync_status = "pending"
        candidate.hh_sync_error = None

    job, created = await enqueue_hh_sync_job(
        session,
        connection=context.connection,
        job_type="sync_candidate_status",
        entity_type="candidate",
        entity_external_id=str(candidate.id),
        payload_json=payload,
        direction=HHSyncDirection.OUTBOUND,
        idempotency_key=idempotency_key,
        candidate_id=int(candidate.id),
    )
    return job, created


__all__ = [
    "CandidateHHLinkContext",
    "HHSyncIntent",
    "build_status_sync_idempotency_key",
    "enqueue_candidate_status_sync",
    "load_candidate_hh_link_context",
    "resolve_hh_sync_intent",
    "should_sync_candidate_status",
]
