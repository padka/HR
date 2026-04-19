from __future__ import annotations

import uuid

from .contracts import (
    ApplicationEventCommand,
    ApplicationEventRecord,
    ApplicationEventRepository,
    ApplicationEventType,
    EventPublishResult,
    IdempotencyConflictError,
    StatusTransitionCommand,
    utcnow,
)
from .idempotency import fingerprint_payload, scoped_idempotency_key


def _as_event_type(value: str) -> str:
    return str(value).strip()


def _build_record(command: ApplicationEventCommand) -> ApplicationEventRecord:
    event_id = command.event_id or str(uuid.uuid4())
    correlation_id = command.correlation_id or str(uuid.uuid4())
    occurred_at = command.occurred_at or utcnow()
    scoped_key = scoped_idempotency_key(command.producer_family, command.idempotency_key)
    metadata = dict(command.metadata_json)
    fingerprint = fingerprint_payload(
        {
            "event_type": _as_event_type(command.event_type),
            "candidate_id": command.candidate_id,
            "application_id": command.application_id,
            "requisition_id": command.requisition_id,
            "source_system": command.source_system,
            "source_ref": command.source_ref,
            "actor_type": command.actor_type,
            "actor_id": command.actor_id,
            "channel": command.channel,
            "metadata_json": metadata,
        }
    )
    return ApplicationEventRecord(
        event_id=event_id,
        correlation_id=correlation_id,
        scoped_idempotency_key=scoped_key,
        idempotency_key=command.idempotency_key.strip(),
        producer_family=command.producer_family.strip().lower(),
        event_type=_as_event_type(command.event_type),
        occurred_at=occurred_at,
        candidate_id=command.candidate_id,
        application_id=command.application_id,
        requisition_id=command.requisition_id,
        source_system=command.source_system,
        source_ref=command.source_ref,
        actor_type=command.actor_type,
        actor_id=command.actor_id,
        channel=command.channel,
        metadata_json=metadata,
        payload_fingerprint=fingerprint,
    )


def _validate_command(command: ApplicationEventCommand) -> None:
    if not command.producer_family.strip():
        raise ValueError("producer_family is required")
    if not command.idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    if not _as_event_type(command.event_type):
        raise ValueError("event_type is required")
    if command.candidate_id <= 0:
        raise ValueError("candidate_id must be positive")
    if not command.source_system.strip():
        raise ValueError("source_system is required")
    if not command.source_ref.strip():
        raise ValueError("source_ref is required")


class ApplicationEventPublisher:
    def __init__(self, repository: ApplicationEventRepository) -> None:
        self._repository = repository

    def publish_application_event(
        self, command: ApplicationEventCommand
    ) -> EventPublishResult:
        _validate_command(command)
        self._repository.ensure_transaction()
        record = _build_record(command)
        existing = self._repository.get_by_scoped_idempotency_key(
            scoped_idempotency_key=record.scoped_idempotency_key
        )
        if existing is not None:
            if existing.payload_fingerprint != record.payload_fingerprint:
                raise IdempotencyConflictError(
                    f"idempotency conflict for {record.scoped_idempotency_key}"
                )
            return EventPublishResult(event=existing, duplicate_reused=True)
        stored = self._repository.append_event(record)
        return EventPublishResult(event=stored, duplicate_reused=False)

    def publish_status_transition(
        self, command: StatusTransitionCommand
    ) -> EventPublishResult:
        metadata = dict(command.metadata_json)
        metadata["status_from"] = command.status_from
        metadata["status_to"] = command.status_to
        base = ApplicationEventCommand(
            producer_family=command.producer_family,
            idempotency_key=command.idempotency_key,
            event_type=ApplicationEventType.APPLICATION_STATUS_CHANGED.value,
            candidate_id=command.candidate_id,
            source_system=command.source_system,
            source_ref=command.source_ref,
            event_id=command.event_id,
            correlation_id=command.correlation_id,
            occurred_at=command.occurred_at,
            actor_type=command.actor_type,
            actor_id=command.actor_id,
            application_id=command.application_id,
            requisition_id=command.requisition_id,
            channel=command.channel,
            metadata_json=metadata,
        )
        return self.publish_application_event(base)

    def publish_message_event(
        self, command: ApplicationEventCommand
    ) -> EventPublishResult:
        return self.publish_application_event(command)

    def publish_interview_event(
        self, command: ApplicationEventCommand
    ) -> EventPublishResult:
        return self.publish_application_event(command)

    def publish_ai_event(self, command: ApplicationEventCommand) -> EventPublishResult:
        return self.publish_application_event(command)

    def publish_hh_event(self, command: ApplicationEventCommand) -> EventPublishResult:
        return self.publish_application_event(command)

    def publish_n8n_event(self, command: ApplicationEventCommand) -> EventPublishResult:
        return self.publish_application_event(command)
