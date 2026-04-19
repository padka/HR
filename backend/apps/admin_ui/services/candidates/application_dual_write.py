from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.domain.applications import (
    ApplicationEventCommand,
    ApplicationEventPublisher,
    ApplicationEventType,
    PrimaryApplicationResolver,
    ResolutionStatus,
    ResolverContext,
    SqlAlchemyApplicationEventRepository,
    SqlAlchemyApplicationResolverRepository,
    SqlAlchemyApplicationUnitOfWork,
    StatusTransitionCommand,
)
from backend.domain.applications.idempotency import fingerprint_payload
from backend.domain.applications.persistent_idempotency import (
    ApplicationIdempotencyClaimRequest,
    ApplicationIdempotencyClaimResult,
    ApplicationIdempotencyRecord,
    SqlAlchemyApplicationIdempotencyRepository,
)
from backend.domain.candidates.status import CandidateStatus

CANDIDATE_CREATE_OPERATION_KIND = "resolver_create"
CANDIDATE_CREATE_PRODUCER_FAMILY = "admin_ui_candidate_create"
CANDIDATE_CREATE_SOURCE_SYSTEM = "admin_ui"
CANDIDATE_CREATE_SOURCE_REF = "api:candidates:create"
CANDIDATE_CREATE_CHANNEL = "admin_spa"
CANDIDATE_STATUS_OPERATION_KIND = "status_transition"
CANDIDATE_STATUS_PRODUCER_FAMILY = "admin_ui_candidate_status"
CANDIDATE_STATUS_SOURCE_SYSTEM = "admin_ui"
CANDIDATE_STATUS_SOURCE_REF = "candidate_status_update"
CANDIDATE_STATUS_CHANNEL = "admin_spa"


class CandidateCreateDuplicateError(ValueError):
    """Raised when candidate-create dual-write hits an existing Telegram candidate."""


@dataclass(frozen=True, slots=True)
class CandidateCreateDualWriteRequest:
    idempotency_key: str
    correlation_id: str
    payload_fingerprint: str
    principal_type: str
    principal_id: int
    source_system: str = CANDIDATE_CREATE_SOURCE_SYSTEM
    source_ref: str = CANDIDATE_CREATE_SOURCE_REF


@dataclass(frozen=True, slots=True)
class CandidateCreateDualWriteResult:
    candidate_id: int
    application_id: int
    requisition_id: int | None
    event_id: str
    application_created: bool
    duplicate_reused: bool = False


def build_candidate_create_payload_fingerprint(
    *,
    fio: str,
    city: str | None,
    phone: str | None,
    telegram_id: int | None,
    recruiter_id: int | None,
    source: str,
    initial_status: CandidateStatus | None,
    is_active: bool,
) -> str:
    payload: dict[str, Any] = {
        "fio": fio,
        "city": city,
        "phone": phone,
        "telegram_id": telegram_id,
        "recruiter_id": recruiter_id,
        "source": source,
        "initial_status": initial_status.value if initial_status is not None else None,
        "is_active": is_active,
    }
    return fingerprint_payload(payload)


@dataclass(frozen=True, slots=True)
class CandidateStatusDualWriteRequest:
    idempotency_key: str
    correlation_id: str
    payload_fingerprint: str
    principal_type: str | None
    principal_id: int | str | None
    source_system: str = CANDIDATE_STATUS_SOURCE_SYSTEM
    source_ref: str = CANDIDATE_STATUS_SOURCE_REF


@dataclass(frozen=True, slots=True)
class CandidateStatusDualWriteResult:
    candidate_id: int
    application_id: int
    requisition_id: int | None
    event_id: str
    application_created: bool
    duplicate_reused: bool = False


def build_candidate_status_payload_fingerprint(
    *,
    candidate_id: int,
    status_to: CandidateStatus | str | None,
    reason: str | None,
    comment: str | None,
    principal_type: str | None,
    principal_id: int | str | None,
    source_ref: str,
) -> str:
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "status_to": status_to.value if isinstance(status_to, CandidateStatus) else status_to,
        "reason": (reason or "").strip() or None,
        "comment": (comment or "").strip() or None,
        "principal_type": (principal_type or "").strip() or None,
        "principal_id": str(principal_id).strip() if principal_id is not None else None,
        "source_ref": source_ref,
    }
    return fingerprint_payload(payload)


def build_candidate_status_fallback_idempotency_key(
    *,
    candidate_id: int,
    status_from: str | None,
    status_to: CandidateStatus | str | None,
    reason: str | None,
    comment: str | None,
    principal_type: str | None,
    principal_id: int | str | None,
    previous_status_changed_at: datetime | None,
    source_ref: str,
) -> str:
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "status_from": status_from,
        "status_to": status_to.value if isinstance(status_to, CandidateStatus) else status_to,
        "reason": (reason or "").strip() or None,
        "comment": (comment or "").strip() or None,
        "principal_type": (principal_type or "").strip() or None,
        "principal_id": str(principal_id).strip() if principal_id is not None else None,
        "previous_status_changed_at": (
            previous_status_changed_at.astimezone(UTC).isoformat()
            if previous_status_changed_at is not None
            else None
        ),
        "source_ref": source_ref,
    }
    return f"status-{candidate_id}-{fingerprint_payload(payload)[:24]}"


async def claim_candidate_create(
    session: AsyncSession,
    request: CandidateCreateDualWriteRequest,
) -> ApplicationIdempotencyClaimResult:
    return await session.run_sync(_claim_candidate_create_sync, request)


def _claim_candidate_create_sync(
    sync_session: Session,
    request: CandidateCreateDualWriteRequest,
) -> ApplicationIdempotencyClaimResult:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(sync_session, uow=uow)
    with uow.begin():
        return repository.claim(
            ApplicationIdempotencyClaimRequest(
                operation_kind=CANDIDATE_CREATE_OPERATION_KIND,
                producer_family=CANDIDATE_CREATE_PRODUCER_FAMILY,
                idempotency_key=request.idempotency_key,
                payload_fingerprint=request.payload_fingerprint,
                correlation_id=request.correlation_id,
                source_system=request.source_system,
                source_ref=request.source_ref,
                metadata_json={"dual_write_path": "candidate_create"},
            )
        )


async def claim_candidate_status_transition(
    session: AsyncSession,
    request: CandidateStatusDualWriteRequest,
) -> ApplicationIdempotencyClaimResult:
    return await session.run_sync(_claim_candidate_status_transition_sync, request)


def _claim_candidate_status_transition_sync(
    sync_session: Session,
    request: CandidateStatusDualWriteRequest,
) -> ApplicationIdempotencyClaimResult:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(sync_session, uow=uow)
    with uow.begin():
        return repository.claim(
            ApplicationIdempotencyClaimRequest(
                operation_kind=CANDIDATE_STATUS_OPERATION_KIND,
                producer_family=CANDIDATE_STATUS_PRODUCER_FAMILY,
                idempotency_key=request.idempotency_key,
                payload_fingerprint=request.payload_fingerprint,
                correlation_id=request.correlation_id,
                source_system=request.source_system,
                source_ref=request.source_ref,
                metadata_json={"dual_write_path": "candidate_status_transition"},
            )
        )


async def get_candidate_status_transition_record(
    session: AsyncSession,
    request: CandidateStatusDualWriteRequest,
) -> ApplicationIdempotencyRecord | None:
    return await session.run_sync(_get_candidate_status_transition_record_sync, request)


def _get_candidate_status_transition_record_sync(
    sync_session: Session,
    request: CandidateStatusDualWriteRequest,
) -> ApplicationIdempotencyRecord | None:
    repository = SqlAlchemyApplicationIdempotencyRepository(sync_session)
    return repository.get_by_scope(
        operation_kind=CANDIDATE_STATUS_OPERATION_KIND,
        producer_family=CANDIDATE_STATUS_PRODUCER_FAMILY,
        idempotency_key=request.idempotency_key,
    )


def _publish_application_created_if_needed(
    *,
    publisher: ApplicationEventPublisher,
    idempotency_key: str,
    producer_family: str,
    candidate_id: int,
    application_id: int,
    requisition_id: int | None,
    source_system: str,
    source_ref: str,
    correlation_id: str,
    actor_type: str | None,
    actor_id: int | str | None,
    channel: str,
    metadata_json: dict[str, Any],
    created: bool,
) -> None:
    if not created:
        return
    publisher.publish_application_event(
        ApplicationEventCommand(
            producer_family=producer_family,
            idempotency_key=f"{idempotency_key}:application_created",
            event_type=ApplicationEventType.APPLICATION_CREATED.value,
            candidate_id=candidate_id,
            source_system=source_system,
            source_ref=source_ref,
            correlation_id=correlation_id,
            actor_type=actor_type,
            actor_id=actor_id,
            application_id=application_id,
            requisition_id=requisition_id,
            channel=channel,
            metadata_json=metadata_json,
        )
    )


async def finalize_candidate_create_dual_write(
    session: AsyncSession,
    *,
    candidate_id: int,
    source: str,
    initial_status: CandidateStatus | None,
    request: CandidateCreateDualWriteRequest,
) -> CandidateCreateDualWriteResult:
    return await session.run_sync(
        _finalize_candidate_create_dual_write_sync,
        candidate_id,
        source,
        initial_status.value if initial_status is not None else None,
        request,
    )


def _finalize_candidate_create_dual_write_sync(
    sync_session: Session,
    candidate_id: int,
    source: str,
    initial_status: str | None,
    request: CandidateCreateDualWriteRequest,
) -> CandidateCreateDualWriteResult:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    ledger = SqlAlchemyApplicationIdempotencyRepository(sync_session, uow=uow)
    resolver = PrimaryApplicationResolver(
        SqlAlchemyApplicationResolverRepository(sync_session, uow=uow)
    )
    publisher = ApplicationEventPublisher(
        SqlAlchemyApplicationEventRepository(sync_session, uow=uow)
    )

    with uow.begin():
        resolution = resolver.ensure_application_for_candidate(
            candidate_id,
            ResolverContext(
                producer_family=CANDIDATE_CREATE_PRODUCER_FAMILY,
                source_system=request.source_system,
                source_ref=request.source_ref,
                candidate_id=candidate_id,
                actor_type=request.principal_type,
                actor_id=request.principal_id,
                correlation_id=request.correlation_id,
                allow_create=True,
                require_application_anchor=True,
            ),
        )
        if resolution.status not in {
            ResolutionStatus.RESOLVED,
            ResolutionStatus.CREATED,
        } or resolution.application_id is None:
            raise RuntimeError(
                "candidate create dual-write could not resolve a primary application"
            )

        event_metadata = {
            "dual_write_path": "candidate_create",
            "legacy_source": source,
            "initial_status": initial_status,
            "application_created": resolution.created_application,
        }
        _publish_application_created_if_needed(
            publisher=publisher,
            idempotency_key=request.idempotency_key,
            producer_family=CANDIDATE_CREATE_PRODUCER_FAMILY,
            candidate_id=candidate_id,
            application_id=resolution.application_id,
            requisition_id=resolution.requisition_id,
            source_system=request.source_system,
            source_ref=request.source_ref,
            correlation_id=request.correlation_id,
            actor_type=request.principal_type,
            actor_id=request.principal_id,
            channel=CANDIDATE_CREATE_CHANNEL,
            metadata_json=event_metadata,
            created=resolution.created_application,
        )
        event_result = publisher.publish_application_event(
            ApplicationEventCommand(
                producer_family=CANDIDATE_CREATE_PRODUCER_FAMILY,
                idempotency_key=request.idempotency_key,
                event_type=ApplicationEventType.CANDIDATE_CREATED.value,
                candidate_id=candidate_id,
                source_system=request.source_system,
                source_ref=request.source_ref,
                correlation_id=request.correlation_id,
                actor_type=request.principal_type,
                actor_id=request.principal_id,
                application_id=resolution.application_id,
                requisition_id=resolution.requisition_id,
                channel=CANDIDATE_CREATE_CHANNEL,
                metadata_json=event_metadata,
            )
        )
        linked = ledger.link_result(
            operation_kind=CANDIDATE_CREATE_OPERATION_KIND,
            producer_family=CANDIDATE_CREATE_PRODUCER_FAMILY,
            idempotency_key=request.idempotency_key,
            candidate_id=candidate_id,
            application_id=resolution.application_id,
            requisition_id=resolution.requisition_id,
            event_id=event_result.event.event_id,
        )
        resolved_candidate_id = linked.candidate_id or candidate_id
        return CandidateCreateDualWriteResult(
            candidate_id=resolved_candidate_id,
            application_id=resolution.application_id,
            requisition_id=resolution.requisition_id,
            event_id=event_result.event.event_id,
            application_created=resolution.created_application,
            duplicate_reused=event_result.duplicate_reused,
        )


async def finalize_candidate_status_dual_write(
    session: AsyncSession,
    *,
    candidate_id: int,
    status_from: str | None,
    status_to: str,
    reason: str | None,
    comment: str | None,
    request: CandidateStatusDualWriteRequest,
) -> CandidateStatusDualWriteResult:
    return await session.run_sync(
        _finalize_candidate_status_dual_write_sync,
        candidate_id,
        status_from,
        status_to,
        reason,
        comment,
        request,
    )


def _finalize_candidate_status_dual_write_sync(
    sync_session: Session,
    candidate_id: int,
    status_from: str | None,
    status_to: str,
    reason: str | None,
    comment: str | None,
    request: CandidateStatusDualWriteRequest,
) -> CandidateStatusDualWriteResult:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    ledger = SqlAlchemyApplicationIdempotencyRepository(sync_session, uow=uow)
    resolver = PrimaryApplicationResolver(
        SqlAlchemyApplicationResolverRepository(sync_session, uow=uow)
    )
    publisher = ApplicationEventPublisher(
        SqlAlchemyApplicationEventRepository(sync_session, uow=uow)
    )

    with uow.begin():
        resolution = resolver.ensure_application_for_candidate(
            candidate_id,
            ResolverContext(
                producer_family=CANDIDATE_STATUS_PRODUCER_FAMILY,
                source_system=request.source_system,
                source_ref=request.source_ref,
                candidate_id=candidate_id,
                actor_type=request.principal_type,
                actor_id=request.principal_id,
                correlation_id=request.correlation_id,
                allow_create=True,
                require_application_anchor=True,
            ),
        )
        if resolution.status not in {
            ResolutionStatus.RESOLVED,
            ResolutionStatus.CREATED,
        } or resolution.application_id is None:
            raise RuntimeError(
                "candidate status dual-write could not resolve a primary application"
            )

        event_metadata = {
            "dual_write_path": "candidate_status_transition",
            "reason": (reason or "").strip() or None,
            "comment": (comment or "").strip() or None,
            "application_created": resolution.created_application,
        }
        _publish_application_created_if_needed(
            publisher=publisher,
            idempotency_key=request.idempotency_key,
            producer_family=CANDIDATE_STATUS_PRODUCER_FAMILY,
            candidate_id=candidate_id,
            application_id=resolution.application_id,
            requisition_id=resolution.requisition_id,
            source_system=request.source_system,
            source_ref=request.source_ref,
            correlation_id=request.correlation_id,
            actor_type=request.principal_type,
            actor_id=request.principal_id,
            channel=CANDIDATE_STATUS_CHANNEL,
            metadata_json=event_metadata,
            created=resolution.created_application,
        )
        event_result = publisher.publish_status_transition(
            StatusTransitionCommand(
                producer_family=CANDIDATE_STATUS_PRODUCER_FAMILY,
                idempotency_key=request.idempotency_key,
                event_type=ApplicationEventType.APPLICATION_STATUS_CHANGED.value,
                candidate_id=candidate_id,
                source_system=request.source_system,
                source_ref=request.source_ref,
                correlation_id=request.correlation_id,
                actor_type=request.principal_type,
                actor_id=request.principal_id,
                application_id=resolution.application_id,
                requisition_id=resolution.requisition_id,
                channel=CANDIDATE_STATUS_CHANNEL,
                metadata_json=event_metadata,
                status_from=status_from,
                status_to=status_to,
            )
        )
        linked = ledger.link_result(
            operation_kind=CANDIDATE_STATUS_OPERATION_KIND,
            producer_family=CANDIDATE_STATUS_PRODUCER_FAMILY,
            idempotency_key=request.idempotency_key,
            candidate_id=candidate_id,
            application_id=resolution.application_id,
            requisition_id=resolution.requisition_id,
            event_id=event_result.event.event_id,
        )
        resolved_candidate_id = linked.candidate_id or candidate_id
        return CandidateStatusDualWriteResult(
            candidate_id=resolved_candidate_id,
            application_id=resolution.application_id,
            requisition_id=resolution.requisition_id,
            event_id=event_result.event.event_id,
            application_created=resolution.created_application,
            duplicate_reused=event_result.duplicate_reused,
        )


__all__ = [
    "CANDIDATE_CREATE_OPERATION_KIND",
    "CANDIDATE_CREATE_PRODUCER_FAMILY",
    "CANDIDATE_STATUS_OPERATION_KIND",
    "CANDIDATE_STATUS_PRODUCER_FAMILY",
    "CandidateCreateDualWriteRequest",
    "CandidateCreateDualWriteResult",
    "CandidateCreateDuplicateError",
    "CandidateStatusDualWriteRequest",
    "CandidateStatusDualWriteResult",
    "build_candidate_create_payload_fingerprint",
    "build_candidate_status_fallback_idempotency_key",
    "build_candidate_status_payload_fingerprint",
    "claim_candidate_create",
    "claim_candidate_status_transition",
    "finalize_candidate_create_dual_write",
    "finalize_candidate_status_dual_write",
    "get_candidate_status_transition_record",
]
