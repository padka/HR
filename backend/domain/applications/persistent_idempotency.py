from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from backend.domain.models import ApplicationIdempotencyKey
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .uow import ApplicationUnitOfWork, SqlAlchemyApplicationUnitOfWork

_UNSET = object()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class PersistentIdempotencyConflictError(ValueError):
    """Raised when a claimed persistent idempotency key is reused with a new payload."""


class PersistentIdempotencyClaimOutcome(str, Enum):
    CLAIMED = "claimed"
    REUSED = "reused"
    EXPIRED = "expired"


class PersistentIdempotencyStatus(str, Enum):
    CLAIMED = "claimed"
    COMPLETED = "completed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ApplicationIdempotencyClaimRequest:
    operation_kind: str
    producer_family: str
    idempotency_key: str
    payload_fingerprint: str
    candidate_id: int | None = None
    application_id: int | None = None
    requisition_id: int | None = None
    event_id: str | None = None
    correlation_id: str | None = None
    source_system: str | None = None
    source_ref: str | None = None
    status: str = PersistentIdempotencyStatus.CLAIMED.value
    expires_at: datetime | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApplicationIdempotencyRecord:
    id: int
    operation_kind: str
    producer_family: str
    idempotency_key: str
    payload_fingerprint: str
    candidate_id: int | None
    application_id: int | None
    requisition_id: int | None
    event_id: str | None
    correlation_id: str | None
    source_system: str | None
    source_ref: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    metadata_json: dict[str, Any]

    def is_expired(self, *, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        comparison_point = _as_utc(now or _utcnow())
        return _as_utc(self.expires_at) <= comparison_point


@dataclass(frozen=True, slots=True)
class ApplicationIdempotencyClaimResult:
    outcome: PersistentIdempotencyClaimOutcome
    record: ApplicationIdempotencyRecord

    @property
    def claimed(self) -> bool:
        return self.outcome == PersistentIdempotencyClaimOutcome.CLAIMED

    @property
    def reused(self) -> bool:
        return self.outcome == PersistentIdempotencyClaimOutcome.REUSED

    @property
    def expired(self) -> bool:
        return self.outcome == PersistentIdempotencyClaimOutcome.EXPIRED


def _normalize_optional(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_claim_request(
    request: ApplicationIdempotencyClaimRequest,
) -> ApplicationIdempotencyClaimRequest:
    operation_kind = request.operation_kind.strip().lower()
    producer_family = request.producer_family.strip().lower()
    idempotency_key = request.idempotency_key.strip()
    payload_fingerprint = request.payload_fingerprint.strip().lower()
    status = request.status.strip().lower()

    if not operation_kind:
        raise ValueError("operation_kind is required")
    if not producer_family:
        raise ValueError("producer_family is required")
    if not idempotency_key:
        raise ValueError("idempotency_key is required")
    if not payload_fingerprint:
        raise ValueError("payload_fingerprint is required")
    if not status:
        raise ValueError("status is required")

    return ApplicationIdempotencyClaimRequest(
        operation_kind=operation_kind,
        producer_family=producer_family,
        idempotency_key=idempotency_key,
        payload_fingerprint=payload_fingerprint,
        candidate_id=request.candidate_id,
        application_id=request.application_id,
        requisition_id=request.requisition_id,
        event_id=_normalize_optional(request.event_id),
        correlation_id=_normalize_optional(request.correlation_id),
        source_system=_normalize_optional(request.source_system),
        source_ref=_normalize_optional(request.source_ref),
        status=status,
        expires_at=request.expires_at,
        metadata_json=dict(request.metadata_json),
    )


def _to_record(model: ApplicationIdempotencyKey) -> ApplicationIdempotencyRecord:
    return ApplicationIdempotencyRecord(
        id=int(model.id),
        operation_kind=model.operation_kind,
        producer_family=model.producer_family,
        idempotency_key=model.idempotency_key,
        payload_fingerprint=model.payload_fingerprint,
        candidate_id=int(model.candidate_id) if model.candidate_id is not None else None,
        application_id=int(model.application_id) if model.application_id is not None else None,
        requisition_id=int(model.requisition_id) if model.requisition_id is not None else None,
        event_id=model.event_id,
        correlation_id=model.correlation_id,
        source_system=model.source_system,
        source_ref=model.source_ref,
        status=model.status,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
        expires_at=_as_utc(model.expires_at) if model.expires_at is not None else None,
        metadata_json=dict(model.metadata_json or {}),
    )


def _sqlite_next_pk(session: Session) -> int | None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return None
    next_id = session.execute(
        select(func.coalesce(func.max(ApplicationIdempotencyKey.id), 0) + 1)
    ).scalar_one()
    return int(next_id)


class SqlAlchemyApplicationIdempotencyRepository:
    """Persistent idempotency ledger adapter for Phase B preparation.

    The repository is intentionally isolated and is not wired into runtime flows
    in this task. It provides the cross-transaction claim/reuse/conflict
    semantics required by RS-IDEMP-019.
    """

    def __init__(
        self,
        session: Session,
        *,
        uow: ApplicationUnitOfWork | None = None,
    ) -> None:
        self._session = session
        self._uow = uow or SqlAlchemyApplicationUnitOfWork(session)

    def ensure_transaction(self) -> None:
        self._uow.ensure_transaction()

    def get_by_scope(
        self,
        *,
        operation_kind: str,
        producer_family: str,
        idempotency_key: str,
    ) -> ApplicationIdempotencyRecord | None:
        statement = select(ApplicationIdempotencyKey).where(
            ApplicationIdempotencyKey.operation_kind == operation_kind.strip().lower(),
            ApplicationIdempotencyKey.producer_family == producer_family.strip().lower(),
            ApplicationIdempotencyKey.idempotency_key == idempotency_key.strip(),
        )
        model = self._session.execute(statement).scalar_one_or_none()
        return _to_record(model) if model is not None else None

    def claim(
        self,
        request: ApplicationIdempotencyClaimRequest,
        *,
        now: datetime | None = None,
    ) -> ApplicationIdempotencyClaimResult:
        self.ensure_transaction()
        normalized = _normalize_claim_request(request)
        comparison_point = now or _utcnow()

        try:
            with self._session.begin_nested():
                model = ApplicationIdempotencyKey(
                    id=_sqlite_next_pk(self._session),
                    operation_kind=normalized.operation_kind,
                    producer_family=normalized.producer_family,
                    idempotency_key=normalized.idempotency_key,
                    payload_fingerprint=normalized.payload_fingerprint,
                    candidate_id=normalized.candidate_id,
                    application_id=normalized.application_id,
                    requisition_id=normalized.requisition_id,
                    event_id=normalized.event_id,
                    correlation_id=normalized.correlation_id,
                    source_system=normalized.source_system,
                    source_ref=normalized.source_ref,
                    status=normalized.status,
                    expires_at=normalized.expires_at,
                    metadata_json=dict(normalized.metadata_json),
                )
                self._session.add(model)
                self._session.flush()
                self._session.refresh(model)
        except IntegrityError as err:
            existing = self.get_by_scope(
                operation_kind=normalized.operation_kind,
                producer_family=normalized.producer_family,
                idempotency_key=normalized.idempotency_key,
            )
            if existing is None:
                raise err
            if existing.is_expired(now=comparison_point):
                return ApplicationIdempotencyClaimResult(
                    outcome=PersistentIdempotencyClaimOutcome.EXPIRED,
                    record=existing,
                )
            if existing.payload_fingerprint != normalized.payload_fingerprint:
                raise PersistentIdempotencyConflictError(
                    "persistent idempotency conflict for "
                    f"{normalized.operation_kind}:{normalized.producer_family}:{normalized.idempotency_key}"
                ) from err
            return ApplicationIdempotencyClaimResult(
                outcome=PersistentIdempotencyClaimOutcome.REUSED,
                record=existing,
            )

        return ApplicationIdempotencyClaimResult(
            outcome=PersistentIdempotencyClaimOutcome.CLAIMED,
            record=_to_record(model),
        )

    def link_result(
        self,
        *,
        operation_kind: str,
        producer_family: str,
        idempotency_key: str,
        candidate_id: int | None = None,
        application_id: int | None = None,
        requisition_id: int | None = None,
        event_id: str | None = None,
        status: str | None = PersistentIdempotencyStatus.COMPLETED.value,
        expires_at: datetime | None | object = _UNSET,
    ) -> ApplicationIdempotencyRecord:
        self.ensure_transaction()
        statement = select(ApplicationIdempotencyKey).where(
            ApplicationIdempotencyKey.operation_kind == operation_kind.strip().lower(),
            ApplicationIdempotencyKey.producer_family == producer_family.strip().lower(),
            ApplicationIdempotencyKey.idempotency_key == idempotency_key.strip(),
        )
        model = self._session.execute(statement).scalar_one_or_none()
        if model is None:
            raise LookupError(
                "persistent idempotency key not found for "
                f"{operation_kind}:{producer_family}:{idempotency_key}"
            )

        if candidate_id is not None:
            model.candidate_id = candidate_id
        if application_id is not None:
            model.application_id = application_id
        if requisition_id is not None:
            model.requisition_id = requisition_id
        if event_id is not None:
            model.event_id = _normalize_optional(event_id)
        if status is not None:
            normalized_status = status.strip().lower()
            if not normalized_status:
                raise ValueError("status cannot be blank")
            model.status = normalized_status
        if expires_at is not _UNSET:
            model.expires_at = expires_at
        model.updated_at = _utcnow()
        self._session.flush()
        self._session.refresh(model)
        return _to_record(model)


__all__ = [
    "ApplicationIdempotencyClaimRequest",
    "ApplicationIdempotencyClaimResult",
    "ApplicationIdempotencyRecord",
    "PersistentIdempotencyClaimOutcome",
    "PersistentIdempotencyConflictError",
    "PersistentIdempotencyStatus",
    "SqlAlchemyApplicationIdempotencyRepository",
]
