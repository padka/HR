from __future__ import annotations

import pytest
from backend.domain.applications import (
    ApplicationEventCommand,
    ApplicationEventPublisher,
    ApplicationEventRecord,
    ApplicationEventRepository,
    ApplicationEventType,
    IdempotencyConflictError,
    StatusTransitionCommand,
)

pytestmark = pytest.mark.no_db_cleanup


class FakeEventRepository(ApplicationEventRepository):
    def __init__(self) -> None:
        self.transaction_checks = 0
        self.records: dict[str, ApplicationEventRecord] = {}
        self.append_calls: list[ApplicationEventRecord] = []

    def ensure_transaction(self) -> None:
        self.transaction_checks += 1

    def get_by_scoped_idempotency_key(
        self, *, scoped_idempotency_key: str
    ) -> ApplicationEventRecord | None:
        return self.records.get(scoped_idempotency_key)

    def append_event(self, record: ApplicationEventRecord) -> ApplicationEventRecord:
        self.records[record.scoped_idempotency_key] = record
        self.append_calls.append(record)
        return record


def _command(**overrides: object) -> ApplicationEventCommand:
    base = {
        "producer_family": "candidate-status",
        "idempotency_key": "change-1",
        "event_type": ApplicationEventType.APPLICATION_CREATED.value,
        "candidate_id": 1,
        "source_system": "admin_ui",
        "source_ref": "candidate:1",
        "metadata_json": {"phase": "skeleton"},
    }
    base.update(overrides)
    return ApplicationEventCommand(**base)


def test_event_id_and_correlation_id_are_generated() -> None:
    repository = FakeEventRepository()
    publisher = ApplicationEventPublisher(repository)

    result = publisher.publish_application_event(_command())

    assert result.event.event_id
    assert result.event.correlation_id
    assert repository.transaction_checks == 1
    assert len(repository.append_calls) == 1


def test_producer_scoped_idempotency_key_is_used() -> None:
    repository = FakeEventRepository()
    publisher = ApplicationEventPublisher(repository)

    result = publisher.publish_application_event(_command(producer_family="hh-sync"))

    assert result.event.scoped_idempotency_key == "hh-sync:change-1"


def test_same_key_same_payload_reuses_existing_event() -> None:
    repository = FakeEventRepository()
    publisher = ApplicationEventPublisher(repository)
    command = _command()

    first = publisher.publish_application_event(command)
    second = publisher.publish_application_event(command)

    assert first.duplicate_reused is False
    assert second.duplicate_reused is True
    assert second.event.event_id == first.event.event_id
    assert len(repository.append_calls) == 1


def test_same_key_different_payload_conflicts() -> None:
    repository = FakeEventRepository()
    publisher = ApplicationEventPublisher(repository)

    publisher.publish_application_event(_command(metadata_json={"stage": "one"}))

    with pytest.raises(IdempotencyConflictError):
        publisher.publish_application_event(_command(metadata_json={"stage": "two"}))


def test_append_only_semantics_keep_original_event_record() -> None:
    repository = FakeEventRepository()
    publisher = ApplicationEventPublisher(repository)
    command = _command(event_type=ApplicationEventType.MESSAGE_SENT.value)

    first = publisher.publish_application_event(command)
    second = publisher.publish_application_event(command)

    assert len(repository.append_calls) == 1
    assert second.event == first.event


def test_status_transition_adds_metadata_and_nullable_anchors_are_allowed() -> None:
    repository = FakeEventRepository()
    publisher = ApplicationEventPublisher(repository)
    command = StatusTransitionCommand(
        producer_family="candidate-status",
        idempotency_key="transition-1",
        event_type=ApplicationEventType.APPLICATION_STATUS_CHANGED.value,
        candidate_id=1,
        source_system="admin_ui",
        source_ref="candidate:1",
        application_id=None,
        requisition_id=None,
        status_from="new",
        status_to="screening",
        metadata_json={"origin": "unit-test"},
    )

    result = publisher.publish_status_transition(command)

    assert result.event.event_type == ApplicationEventType.APPLICATION_STATUS_CHANGED.value
    assert result.event.application_id is None
    assert result.event.requisition_id is None
    assert result.event.metadata_json["status_from"] == "new"
    assert result.event.metadata_json["status_to"] == "screening"


def test_distinct_keys_under_same_correlation_are_allowed() -> None:
    repository = FakeEventRepository()
    publisher = ApplicationEventPublisher(repository)

    first = publisher.publish_application_event(
        _command(
            correlation_id="corr-1",
            idempotency_key="message-1",
            event_type=ApplicationEventType.MESSAGE_INTENT_CREATED.value,
        )
    )
    second = publisher.publish_application_event(
        _command(
            correlation_id="corr-1",
            idempotency_key="message-2",
            event_type=ApplicationEventType.MESSAGE_SENT.value,
        )
    )

    assert first.event.correlation_id == second.event.correlation_id
    assert first.event.event_id != second.event.event_id
    assert len(repository.append_calls) == 2


def test_invalid_command_fails_before_append() -> None:
    repository = FakeEventRepository()
    publisher = ApplicationEventPublisher(repository)

    with pytest.raises(ValueError):
        publisher.publish_application_event(_command(producer_family=""))

    assert repository.transaction_checks == 0
    assert repository.append_calls == []
