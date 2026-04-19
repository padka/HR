from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from backend.domain.applications.persistent_idempotency import (
    ApplicationIdempotencyClaimRequest,
    PersistentIdempotencyClaimOutcome,
    PersistentIdempotencyConflictError,
    PersistentIdempotencyStatus,
    SqlAlchemyApplicationIdempotencyRepository,
)
from backend.domain.applications.uow import SqlAlchemyApplicationUnitOfWork
from backend.domain.base import Base
from backend.domain.candidates.models import User
from backend.domain.models import (
    Application,
    ApplicationIdempotencyKey,
    Requisition,
)
from sqlalchemy import func, select
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


def _seed_requisition(session: Session, *, requisition_id: int = 101) -> Requisition:
    requisition = Requisition(
        id=requisition_id,
        title=f"Req {requisition_id}",
        headcount=1,
        priority="normal",
        owner_type="recruiter",
        owner_id=1,
        status="open",
    )
    session.add(requisition)
    session.commit()
    return requisition


def _seed_application(
    session: Session,
    *,
    application_id: int = 201,
    candidate_id: int = 1,
    requisition_id: int | None = 101,
) -> Application:
    application = Application(
        id=application_id,
        candidate_id=candidate_id,
        requisition_id=requisition_id,
        vacancy_id=None,
        source="manual",
        lifecycle_status="new",
    )
    session.add(application)
    session.commit()
    return application


def _request(**overrides: object) -> ApplicationIdempotencyClaimRequest:
    base = {
        "operation_kind": "application_event",
        "producer_family": "candidate_status",
        "idempotency_key": "evt-1",
        "payload_fingerprint": "a" * 64,
        "candidate_id": 1,
        "application_id": None,
        "requisition_id": None,
        "event_id": None,
        "correlation_id": "corr-1",
        "source_system": "unit_test",
        "source_ref": "candidate:1",
        "status": PersistentIdempotencyStatus.CLAIMED.value,
        "metadata_json": {"phase": "test"},
    }
    base.update(overrides)
    return ApplicationIdempotencyClaimRequest(**base)


def test_persistent_idempotency_model_is_registered_in_metadata() -> None:
    assert "application_idempotency_keys" in Base.metadata.tables


def test_claim_creates_one_persistent_row(db_session: Session) -> None:
    _seed_candidate(db_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(
        db_session,
        uow=SqlAlchemyApplicationUnitOfWork(db_session),
    )

    with SqlAlchemyApplicationUnitOfWork(db_session).begin():
        result = repository.claim(_request())

    assert result.outcome == PersistentIdempotencyClaimOutcome.CLAIMED
    assert result.record.application_id is None
    stored_rows = db_session.execute(select(ApplicationIdempotencyKey)).scalars().all()
    assert len(stored_rows) == 1


def test_same_key_same_fingerprint_reuses_existing_claim(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(db_session, uow=uow)

    with uow.begin():
        first = repository.claim(_request())
    with uow.begin():
        second = repository.claim(_request())

    assert first.outcome == PersistentIdempotencyClaimOutcome.CLAIMED
    assert second.outcome == PersistentIdempotencyClaimOutcome.REUSED
    assert second.record.id == first.record.id
    stored_rows = db_session.execute(select(ApplicationIdempotencyKey)).scalars().all()
    assert len(stored_rows) == 1


def test_same_key_different_fingerprint_conflicts(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(db_session, uow=uow)

    with uow.begin():
        repository.claim(_request())

    with pytest.raises(PersistentIdempotencyConflictError):
        with uow.begin():
            repository.claim(_request(payload_fingerprint="b" * 64))


def test_different_operation_kind_can_reuse_same_raw_key(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(db_session, uow=uow)

    with uow.begin():
        first = repository.claim(_request(operation_kind="application_event"))
    with uow.begin():
        second = repository.claim(_request(operation_kind="resolver_create"))

    assert first.record.id != second.record.id
    assert db_session.execute(select(func.count()).select_from(ApplicationIdempotencyKey)).scalar_one() == 2


def test_different_producer_family_can_reuse_same_raw_key(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(db_session, uow=uow)

    with uow.begin():
        first = repository.claim(_request(producer_family="candidate_status"))
    with uow.begin():
        second = repository.claim(_request(producer_family="hh_sync"))

    assert first.record.id != second.record.id
    assert db_session.execute(select(func.count()).select_from(ApplicationIdempotencyKey)).scalar_one() == 2


def test_nullable_result_anchors_are_accepted_and_linkable(db_session: Session) -> None:
    candidate = _seed_candidate(db_session)
    requisition = _seed_requisition(db_session)
    application = _seed_application(
        db_session,
        candidate_id=candidate.id,
        requisition_id=requisition.id,
    )
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(db_session, uow=uow)

    with uow.begin():
        claim = repository.claim(
            _request(
                operation_kind="resolver_create",
                application_id=None,
                requisition_id=None,
                event_id=None,
            )
        )

    assert claim.record.application_id is None
    assert claim.record.requisition_id is None
    assert claim.record.event_id is None

    with uow.begin():
        linked = repository.link_result(
            operation_kind="resolver_create",
            producer_family="candidate_status",
            idempotency_key="evt-1",
            candidate_id=candidate.id,
            application_id=application.id,
            requisition_id=requisition.id,
            event_id="evt-linked-1",
        )

    assert linked.candidate_id == candidate.id
    assert linked.application_id == application.id
    assert linked.requisition_id == requisition.id
    assert linked.event_id == "evt-linked-1"
    assert linked.status == PersistentIdempotencyStatus.COMPLETED.value


def test_expired_existing_claim_is_classified_without_reuse(db_session: Session) -> None:
    _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationIdempotencyRepository(db_session, uow=uow)
    expired_at = _now() - timedelta(minutes=1)

    with uow.begin():
        repository.claim(_request(expires_at=expired_at))

    with uow.begin():
        result = repository.claim(_request(expires_at=expired_at))

    assert result.outcome == PersistentIdempotencyClaimOutcome.EXPIRED
    assert result.record.expires_at == expired_at


def test_postgres_concurrent_claims_reuse_same_row() -> None:
    from backend.core.db import sync_engine

    if sync_engine.url.get_backend_name() != "postgresql":
        pytest.skip("PostgreSQL is required for same-key concurrency proof")

    with Session(sync_engine) as seed_session:
        _seed_candidate(seed_session)

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []
    results: list[tuple[str, str, int]] = []

    def worker(label: str) -> None:
        try:
            with Session(sync_engine) as session:
                uow = SqlAlchemyApplicationUnitOfWork(session)
                repository = SqlAlchemyApplicationIdempotencyRepository(session, uow=uow)
                with uow.begin():
                    barrier.wait(timeout=5)
                    claim = repository.claim(
                        _request(
                            operation_kind="application_event",
                            producer_family="pg_concurrency",
                            idempotency_key="pg-evt-1",
                            payload_fingerprint="c" * 64,
                        )
                    )
                    results.append((label, claim.outcome.value, claim.record.id))
        except BaseException as exc:  # pragma: no cover - debugging capture
            errors.append(exc)

    first = threading.Thread(target=worker, args=("first",), daemon=True)
    second = threading.Thread(target=worker, args=("second",), daemon=True)
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)

    if first.is_alive() or second.is_alive():
        pytest.fail("PostgreSQL concurrency worker threads did not finish")
    if errors:
        raise AssertionError(f"PostgreSQL concurrency claim failed: {errors!r}")

    outcomes = sorted(outcome for _, outcome, _ in results)
    row_ids = {row_id for _, _, row_id in results}
    assert outcomes == [
        PersistentIdempotencyClaimOutcome.CLAIMED.value,
        PersistentIdempotencyClaimOutcome.REUSED.value,
    ]
    assert len(row_ids) == 1

    with Session(sync_engine) as verify_session:
        count = verify_session.execute(
            select(func.count()).select_from(ApplicationIdempotencyKey).where(
                ApplicationIdempotencyKey.operation_kind == "application_event",
                ApplicationIdempotencyKey.producer_family == "pg_concurrency",
                ApplicationIdempotencyKey.idempotency_key == "pg-evt-1",
            )
        ).scalar_one()
    assert count == 1
