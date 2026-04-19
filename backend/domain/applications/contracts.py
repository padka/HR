from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    CREATED = "created"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    DUPLICATE_CONFLICT = "duplicate_conflict"


class ResolverSignal(str, Enum):
    EXPLICIT_APPLICATION = "explicit_application"
    EXPLICIT_REQUISITION = "explicit_requisition"
    SLOT_ASSIGNMENT = "slot_assignment"
    HH_EXACT = "hh_exact"
    NULL_REQUISITION_REUSE = "null_requisition_reuse"
    NULL_REQUISITION_CREATE = "null_requisition_create"
    REQUISITION_CREATE = "requisition_create"


class ApplicationState(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    TERMINAL = "terminal"


class ApplicationEventType(str, Enum):
    ASSESSMENT_COMPLETED = "assessment.completed"
    SCREENING_DECISION_MADE = "screening.decision_made"
    CANDIDATE_CREATED = "candidate.created"
    CANDIDATE_UPDATED = "candidate.updated"
    CANDIDATE_CHANNEL_IDENTITY_LINKED = "candidate.channel_identity.linked"
    CANDIDATE_ACCESS_LINK_ISSUED = "candidate.access_link.issued"
    CANDIDATE_ACCESS_LINK_REUSED = "candidate.access_link.reused"
    CANDIDATE_ACCESS_LINK_ROTATED = "candidate.access_link.rotated"
    CANDIDATE_ACCESS_LINK_REVOKED = "candidate.access_link.revoked"
    CANDIDATE_ACCESS_LINK_LAUNCHED = "candidate.access_link.launched"
    APPLICATION_CREATED = "application.created"
    APPLICATION_STATUS_CHANGED = "application.status_changed"
    APPLICATION_OWNER_ASSIGNED = "application.owner_assigned"
    MESSAGE_INTENT_CREATED = "message.intent_created"
    MESSAGE_SENT = "message.sent"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_FAILED = "message.failed"
    INTERVIEW_SCHEDULED = "interview.scheduled"
    INTERVIEW_CONFIRMED = "interview.confirmed"
    INTERVIEW_COMPLETED = "interview.completed"
    INTERVIEW_NO_SHOW = "interview.no_show"
    AI_RECOMMENDATION_GENERATED = "ai.recommendation.generated"
    AI_RECOMMENDATION_ACCEPTED = "ai.recommendation.accepted"
    AI_RECOMMENDATION_EDITED = "ai.recommendation.edited"
    AI_RECOMMENDATION_REJECTED = "ai.recommendation.rejected"
    HH_NEGOTIATION_IMPORTED = "hh.negotiation.imported"
    HH_STATUS_SYNC_REQUESTED = "hh.status_sync.requested"
    HH_STATUS_SYNC_COMPLETED = "hh.status_sync.completed"
    N8N_WORKFLOW_TRIGGERED = "n8n.workflow.triggered"
    N8N_WORKFLOW_COMPLETED = "n8n.workflow.completed"
    N8N_WORKFLOW_FAILED = "n8n.workflow.failed"


class ApplicationResolverError(ValueError):
    """Base exception for pure resolver contract failures."""


class CandidateNotFoundError(ApplicationResolverError):
    """Raised when the candidate snapshot cannot be loaded."""


class ResolverContextConflictError(ApplicationResolverError):
    """Raised when the context contradicts the candidate or signal snapshot."""


class DuplicateActiveApplicationError(ApplicationResolverError):
    """Raised when multiple active applications make deterministic resolution unsafe."""


class ApplicationCreateConflictError(ApplicationResolverError):
    """Raised when a create path is requested but cannot be satisfied safely."""


class SlotAssignmentNotFoundError(ApplicationResolverError):
    """Raised when slot-assignment-based resolution cannot load its source anchor."""


class SchedulingLinkIntegrityError(ApplicationResolverError):
    """Raised when slot scheduling data is too inconsistent for safe resolution."""


class HHIdentityConflictError(ApplicationResolverError):
    """Raised when HH identities map to multiple candidate/application chains."""


class ThreadCandidateMismatchError(ApplicationResolverError):
    """Raised when a message thread and candidate do not match."""


class AIScopeConflictError(ApplicationResolverError):
    """Raised when AI scope data cannot be mapped safely to a candidate/application."""


class IdempotencyConflictError(ValueError):
    """Raised when the same scoped idempotency key is reused with a new payload."""


@dataclass(frozen=True, slots=True)
class ApplicationRecord:
    application_id: int
    candidate_id: int
    requisition_id: int | None = None
    vacancy_id: int | None = None
    state: ApplicationState = ApplicationState.ACTIVE

    @property
    def is_active(self) -> bool:
        return self.state == ApplicationState.ACTIVE


@dataclass(frozen=True, slots=True)
class ResolverContext:
    producer_family: str
    source_system: str
    source_ref: str
    candidate_id: int | None = None
    actor_type: str | None = None
    actor_id: str | int | None = None
    correlation_id: str | None = None
    explicit_application_id: int | None = None
    explicit_requisition_id: int | None = None
    explicit_vacancy_id: int | None = None
    slot_assignment_id: int | None = None
    slot_id: int | None = None
    hh_resume_id: str | None = None
    hh_negotiation_id: str | None = None
    hh_vacancy_id: str | None = None
    message_thread_id: int | None = None
    message_correlation_id: str | None = None
    ai_scope_type: str | None = None
    ai_scope_id: int | None = None
    allow_create: bool = False
    require_application_anchor: bool = False
    allow_archived_reuse: bool = False


@dataclass(frozen=True, slots=True)
class ResolverSnapshot:
    candidate_id: int
    candidate_exists: bool = True
    explicit_application: ApplicationRecord | None = None
    explicit_requisition_matches: tuple[ApplicationRecord, ...] = ()
    explicit_requisition_ids: tuple[int, ...] = ()
    slot_assignment_matches: tuple[ApplicationRecord, ...] = ()
    slot_assignment_requisition_ids: tuple[int, ...] = ()
    hh_matches: tuple[ApplicationRecord, ...] = ()
    hh_requisition_ids: tuple[int, ...] = ()
    null_requisition_matches: tuple[ApplicationRecord, ...] = ()
    archived_matches: tuple[ApplicationRecord, ...] = ()
    duplicate_exact_matches: tuple[ApplicationRecord, ...] = ()
    duplicate_null_matches: tuple[ApplicationRecord, ...] = ()
    slot_assignment_found: bool = True
    message_candidate_mismatch: bool = False
    ai_scope_conflict: bool = False
    hh_identity_conflict: bool = False
    scheduling_integrity_error: bool = False


@dataclass(frozen=True, slots=True)
class ApplicationCreateRequest:
    candidate_id: int
    requisition_id: int | None
    vacancy_id: int | None
    signal: ResolverSignal
    idempotency_key: str
    correlation_id: str | None
    source_system: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class ResolverResult:
    status: ResolutionStatus
    candidate_id: int
    application_id: int | None = None
    requisition_id: int | None = None
    created_application: bool = False
    used_signal: ResolverSignal | None = None
    resolution_notes: tuple[str, ...] = ()
    emitted_event_types: tuple[str, ...] = ()
    requires_manual_resolution: bool = False


class ApplicationResolverRepository(Protocol):
    def get_snapshot(self, *, candidate_id: int, context: ResolverContext) -> ResolverSnapshot:
        ...

    def get_slot_assignment_snapshot(
        self, *, slot_assignment_id: int, context: ResolverContext
    ) -> ResolverSnapshot:
        ...

    def get_hh_event_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        ...

    def get_message_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        ...

    def get_ai_output_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        ...

    def get_created_application_by_idempotency(
        self, *, idempotency_key: str
    ) -> ApplicationRecord | None:
        ...

    def create_application(self, request: ApplicationCreateRequest) -> ApplicationRecord:
        ...


@dataclass(frozen=True, slots=True)
class ApplicationEventCommand:
    producer_family: str
    idempotency_key: str
    event_type: str
    candidate_id: int
    source_system: str
    source_ref: str
    event_id: str | None = None
    correlation_id: str | None = None
    occurred_at: datetime | None = None
    actor_type: str | None = None
    actor_id: str | int | None = None
    application_id: int | None = None
    requisition_id: int | None = None
    channel: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StatusTransitionCommand(ApplicationEventCommand):
    status_from: str | None = None
    status_to: str | None = None


@dataclass(frozen=True, slots=True)
class ApplicationEventRecord:
    event_id: str
    correlation_id: str
    scoped_idempotency_key: str
    idempotency_key: str
    producer_family: str
    event_type: str
    occurred_at: datetime
    candidate_id: int
    application_id: int | None
    requisition_id: int | None
    source_system: str
    source_ref: str
    actor_type: str | None
    actor_id: str | int | None
    channel: str | None
    metadata_json: dict[str, Any]
    payload_fingerprint: str


@dataclass(frozen=True, slots=True)
class EventPublishResult:
    event: ApplicationEventRecord
    duplicate_reused: bool = False


class ApplicationEventRepository(Protocol):
    def ensure_transaction(self) -> None:
        ...

    def get_by_scoped_idempotency_key(
        self, *, scoped_idempotency_key: str
    ) -> ApplicationEventRecord | None:
        ...

    def append_event(self, record: ApplicationEventRecord) -> ApplicationEventRecord:
        ...


def utcnow() -> datetime:
    return datetime.now(UTC)
