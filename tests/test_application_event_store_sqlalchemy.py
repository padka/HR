from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.applications import (
    ApplicationEventCommand,
    ApplicationEventPublisher,
    ApplicationEventRecord,
    ApplicationEventType,
    IdempotencyConflictError,
    StatusTransitionCommand,
)
from backend.domain.applications.repositories import (
    SqlAlchemyApplicationEventRepository,
)
from backend.domain.applications.uow import (
    SqlAlchemyApplicationUnitOfWork,
    TransactionRequiredError,
)
from backend.domain.candidates.models import User
from backend.domain.models import ApplicationEvent
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def db_session() -> Session:
    from backend.core.db import sync_engine

    with Session(sync_engine) as session:
        yield session


def _now() -> datetime:
    return datetime.now(UTC)


def _seed_candidate(session: Session, *, user_id: int = 1) -> User:
    candidate = User(
        id=user_id,
        candidate_id=f"cand-{user_id}",
        fio=f"Candidate {user_id}",
        source="manual",
        messenger_platform="telegram",
    )
    session.add(candidate)
    session.commit()
    return candidate


def _command(**overrides: object) -> ApplicationEventCommand:
    base = {
        "producer_family": "candidate-status",
        "idempotency_key": "evt-1",
        "event_type": ApplicationEventType.APPLICATION_CREATED.value,
        "candidate_id": 1,
        "source_system": "unit_test",
        "source_ref": "candidate:1",
        "metadata_json": {"phase": "orm"},
    }
    base.update(overrides)
    return ApplicationEventCommand(**base)


def _record(
    *,
    event_id: str,
    scoped_idempotency_key: str,
    raw_idempotency_key: str,
    payload_fingerprint: str,
    metadata_json: dict[str, object] | None = None,
) -> ApplicationEventRecord:
    return ApplicationEventRecord(
        event_id=event_id,
        correlation_id="corr-event-1",
        scoped_idempotency_key=scoped_idempotency_key,
        idempotency_key=raw_idempotency_key,
        producer_family="candidate-status",
        event_type=ApplicationEventType.APPLICATION_CREATED.value,
        occurred_at=_now(),
        candidate_id=1,
        application_id=None,
        requisition_id=None,
        source_system="unit_test",
        source_ref="candidate:1",
        actor_type="system",
        actor_id=None,
        channel=None,
        metadata_json=dict(metadata_json or {}),
        payload_fingerprint=payload_fingerprint,
    )


def test_event_store_requires_explicit_transaction(db_session: Session) -> None:
    _seed_candidate(db_session)
    repository = SqlAlchemyApplicationEventRepository(db_session)
    publisher = ApplicationEventPublisher(repository)

    with pytest.raises(TransactionRequiredError):
        publisher.publish_application_event(_command())


def test_event_store_reuses_same_payload_by_scoped_idempotency_key(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationEventRepository(db_session, uow=uow)
    publisher = ApplicationEventPublisher(repository)

    with uow.begin():
        first = publisher.publish_application_event(_command())
    with uow.begin():
        second = publisher.publish_application_event(_command())

    assert first.duplicate_reused is False
    assert second.duplicate_reused is True
    assert second.event.event_id == first.event.event_id
    stored_rows = db_session.execute(select(ApplicationEvent)).scalars().all()
    assert len(stored_rows) == 1
    assert stored_rows[0].idempotency_key == "candidate-status:evt-1"


def test_event_store_reuses_same_payload_across_sessions(db_session: Session) -> None:
    _seed_candidate(db_session)
    first_command = _command(idempotency_key="evt-persist-1")

    uow1 = SqlAlchemyApplicationUnitOfWork(db_session)
    repository1 = SqlAlchemyApplicationEventRepository(db_session, uow=uow1)
    publisher1 = ApplicationEventPublisher(repository1)
    with uow1.begin():
        first = publisher1.publish_application_event(first_command)

    from backend.core.db import sync_engine

    with Session(sync_engine) as session2:
        uow2 = SqlAlchemyApplicationUnitOfWork(session2)
        repository2 = SqlAlchemyApplicationEventRepository(session2, uow=uow2)
        publisher2 = ApplicationEventPublisher(repository2)
        with uow2.begin():
            second = publisher2.publish_application_event(first_command)

    assert first.duplicate_reused is False
    assert second.duplicate_reused is True
    assert second.event.event_id == first.event.event_id

    stored_rows = db_session.execute(
        select(ApplicationEvent).where(ApplicationEvent.idempotency_key == "candidate-status:evt-persist-1")
    ).scalars().all()
    assert len(stored_rows) == 1


def test_event_store_conflicts_on_same_key_with_different_payload(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationEventRepository(db_session, uow=uow)
    publisher = ApplicationEventPublisher(repository)

    with uow.begin():
        publisher.publish_application_event(_command(metadata_json={"phase": "one"}))
    with pytest.raises(IdempotencyConflictError):
        with uow.begin():
            publisher.publish_application_event(_command(metadata_json={"phase": "two"}))


def test_event_store_conflicts_on_same_key_with_different_payload_across_sessions(
    db_session: Session,
) -> None:
    _seed_candidate(db_session)
    first_command = _command(idempotency_key="evt-cross", metadata_json={"phase": "one"})

    uow1 = SqlAlchemyApplicationUnitOfWork(db_session)
    repository1 = SqlAlchemyApplicationEventRepository(db_session, uow=uow1)
    publisher1 = ApplicationEventPublisher(repository1)
    with uow1.begin():
        publisher1.publish_application_event(first_command)

    from backend.core.db import sync_engine

    with Session(sync_engine) as session2:
        uow2 = SqlAlchemyApplicationUnitOfWork(session2)
        repository2 = SqlAlchemyApplicationEventRepository(session2, uow=uow2)
        publisher2 = ApplicationEventPublisher(repository2)
        with pytest.raises(IdempotencyConflictError):
            with uow2.begin():
                publisher2.publish_application_event(
                    _command(idempotency_key="evt-cross", metadata_json={"phase": "two"})
                )


def test_different_producer_families_can_coexist_with_same_raw_key(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationEventRepository(db_session, uow=uow)
    publisher = ApplicationEventPublisher(repository)

    with uow.begin():
        first = publisher.publish_application_event(_command(producer_family="candidate-status"))
    with uow.begin():
        second = publisher.publish_application_event(_command(producer_family="resolver-create"))

    assert first.duplicate_reused is False
    assert second.duplicate_reused is False
    assert first.event.scoped_idempotency_key == "candidate-status:evt-1"
    assert second.event.scoped_idempotency_key == "resolver-create:evt-1"

    stored_rows = db_session.execute(select(ApplicationEvent)).scalars().all()
    assert len(stored_rows) == 2


def test_nullable_application_and_requisition_are_persisted(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationEventRepository(db_session, uow=uow)
    publisher = ApplicationEventPublisher(repository)

    with uow.begin():
        result = publisher.publish_status_transition(
            StatusTransitionCommand(
                producer_family="candidate-status",
                idempotency_key="transition-1",
                event_type=ApplicationEventType.APPLICATION_STATUS_CHANGED.value,
                candidate_id=1,
                source_system="unit_test",
                source_ref="candidate:1",
                application_id=None,
                requisition_id=None,
                status_from="new",
                status_to="screening",
                metadata_json={"origin": "orm-test"},
            )
        )

    row = db_session.execute(select(ApplicationEvent)).scalar_one()
    assert result.event.application_id is None
    assert result.event.requisition_id is None
    assert row.application_id is None
    assert row.requisition_id is None
    assert row.status_from == "new"
    assert row.status_to == "screening"


def test_pg_concurrent_same_key_same_fingerprint_is_skipped_until_event_store_uses_ledger() -> None:
    from backend.core.db import sync_engine

    if sync_engine.url.get_backend_name() != "postgresql":
        pytest.skip("PostgreSQL concurrency coverage requires a PostgreSQL test target")

    pytest.skip(
        "Generic event-store concurrency proof stays skipped until the event-store path "
        "uses the persistent idempotency ledger; the first runtime dual-write is protected "
        "at the path level instead."
    )


def test_append_only_rows_survive_rollback_boundary(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationEventRepository(db_session, uow=uow)
    publisher = ApplicationEventPublisher(repository)

    with pytest.raises(RuntimeError):
        with uow.begin():
            publisher.publish_application_event(_command(idempotency_key="evt-rollback", occurred_at=_now()))
            raise RuntimeError("force rollback")

    stored_rows = db_session.execute(select(ApplicationEvent)).scalars().all()
    assert stored_rows == []


def test_current_event_store_has_no_persistent_unique_guard_limitation(
    db_session: Session,
) -> None:
    _seed_candidate(db_session)
    first_scoped_key = "candidate-status:dup-gap"

    uow1 = SqlAlchemyApplicationUnitOfWork(db_session)
    repository1 = SqlAlchemyApplicationEventRepository(db_session, uow=uow1)
    with uow1.begin():
        repository1.append_event(
            _record(
                event_id="11111111-1111-1111-1111-111111111111",
                scoped_idempotency_key=first_scoped_key,
                raw_idempotency_key="dup-gap",
                payload_fingerprint="fingerprint-one",
                metadata_json={"phase": "first"},
            )
        )

    from backend.core.db import sync_engine

    with Session(sync_engine) as session2:
        uow2 = SqlAlchemyApplicationUnitOfWork(session2)
        repository2 = SqlAlchemyApplicationEventRepository(session2, uow=uow2)
        with uow2.begin():
            repository2.append_event(
                _record(
                    event_id="22222222-2222-2222-2222-222222222222",
                    scoped_idempotency_key=first_scoped_key,
                    raw_idempotency_key="dup-gap",
                    payload_fingerprint="fingerprint-two",
                    metadata_json={"phase": "second"},
                )
            )

    stored_rows = db_session.execute(
        select(ApplicationEvent).where(ApplicationEvent.idempotency_key == first_scoped_key)
    ).scalars().all()
    assert len(stored_rows) == 2
