from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.applications import (
    ApplicationCreateRequest,
    PrimaryApplicationResolver,
    ResolutionStatus,
    ResolverContext,
    ResolverSignal,
)
from backend.domain.applications.repositories import (
    SqlAlchemyApplicationResolverRepository,
)
from backend.domain.applications.uow import (
    SqlAlchemyApplicationUnitOfWork,
    TransactionRequiredError,
)
from backend.domain.candidates.models import User
from backend.domain.models import (
    Application,
    Interview,
    Recruiter,
    Requisition,
    Slot,
    SlotAssignment,
)
from sqlalchemy.orm import Session


@pytest.fixture
def db_session() -> Session:
    from backend.core.db import sync_engine

    with Session(sync_engine) as session:
        yield session


def _now() -> datetime:
    return datetime.now(UTC)


def _context(**overrides: object) -> ResolverContext:
    base = {
        "producer_family": "phase-b-prep",
        "source_system": "unit_test",
        "source_ref": "ctx-1",
        "allow_create": False,
        "require_application_anchor": False,
    }
    base.update(overrides)
    return ResolverContext(**base)


def _seed_candidate(session: Session, *, user_id: int = 1, candidate_key: str = "cand-1", hh_vacancy_id: str | None = None) -> User:
    candidate = User(
        id=user_id,
        candidate_id=candidate_key,
        fio=f"Candidate {user_id}",
        source="manual",
        messenger_platform="telegram",
        hh_vacancy_id=hh_vacancy_id,
    )
    session.add(candidate)
    session.commit()
    return candidate


def _seed_requisition(
    session: Session,
    *,
    requisition_id: int,
    vacancy_id: int | None = None,
    title: str = "Req",
) -> Requisition:
    requisition = Requisition(
        id=requisition_id,
        vacancy_id=vacancy_id,
        title=title,
        headcount=1,
        priority="normal",
        owner_type="manual",
        status="open",
        opened_at=_now(),
    )
    session.add(requisition)
    session.commit()
    return requisition


def _seed_application(
    session: Session,
    *,
    application_id: int,
    candidate_id: int,
    requisition_id: int | None = None,
    vacancy_id: int | None = None,
    lifecycle_status: str = "new",
    archived: bool = False,
) -> Application:
    application = Application(
        id=application_id,
        candidate_id=candidate_id,
        requisition_id=requisition_id,
        vacancy_id=vacancy_id,
        source="manual",
        source_detail="seed",
        lifecycle_status=lifecycle_status,
        archived_at=_now() if archived else None,
    )
    session.add(application)
    session.commit()
    return application


def _seed_slot_assignment(
    session: Session,
    *,
    assignment_id: int,
    candidate: User,
) -> SlotAssignment:
    recruiter = Recruiter(id=1, name="Recruiter 1")
    slot = Slot(
        id=1,
        recruiter_id=1,
        start_utc=_now(),
        duration_min=30,
        candidate_id=candidate.candidate_id,
        candidate_tg_id=candidate.telegram_id,
        status="booked",
    )
    assignment = SlotAssignment(
        id=assignment_id,
        slot_id=1,
        recruiter_id=1,
        candidate_id=candidate.candidate_id,
        origin="manual",
        status="confirmed",
        offered_at=_now(),
    )
    session.add_all([recruiter, slot, assignment])
    session.commit()
    return assignment


def test_explicit_application_lookup_resolves_existing_record(db_session: Session) -> None:
    candidate = _seed_candidate(db_session)
    _seed_application(db_session, application_id=101, candidate_id=candidate.id)
    repository = SqlAlchemyApplicationResolverRepository(db_session)
    resolver = PrimaryApplicationResolver(repository)

    result = resolver.resolve_primary_application(
        candidate.id,
        _context(candidate_id=candidate.id, explicit_application_id=101),
    )

    assert result.status == ResolutionStatus.RESOLVED
    assert result.application_id == 101
    assert result.used_signal == ResolverSignal.EXPLICIT_APPLICATION


def test_explicit_requisition_creates_application_inside_explicit_transaction(db_session: Session) -> None:
    candidate = _seed_candidate(db_session)
    _seed_requisition(db_session, requisition_id=501, vacancy_id=9001)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationResolverRepository(db_session, uow=uow)
    resolver = PrimaryApplicationResolver(repository)

    with uow.begin():
        result = resolver.ensure_application_for_candidate(
            candidate.id,
            _context(
                candidate_id=candidate.id,
                explicit_requisition_id=501,
                allow_create=True,
                require_application_anchor=True,
                explicit_vacancy_id=9001,
            ),
        )

    created = db_session.get(Application, result.application_id)
    assert result.status == ResolutionStatus.CREATED
    assert result.requisition_id == 501
    assert created is not None
    assert created.requisition_id == 501
    assert created.vacancy_id == 9001


def test_null_requisition_anchor_requires_explicit_transaction(db_session: Session) -> None:
    candidate = _seed_candidate(db_session)
    repository = SqlAlchemyApplicationResolverRepository(db_session)
    resolver = PrimaryApplicationResolver(repository)

    with pytest.raises(TransactionRequiredError):
        resolver.ensure_application_for_candidate(
            candidate.id,
            _context(
                candidate_id=candidate.id,
                allow_create=True,
                require_application_anchor=True,
            ),
        )


def test_null_requisition_anchor_is_created_only_when_contract_allows(db_session: Session) -> None:
    candidate = _seed_candidate(db_session)
    uow = SqlAlchemyApplicationUnitOfWork(db_session)
    repository = SqlAlchemyApplicationResolverRepository(db_session, uow=uow)
    resolver = PrimaryApplicationResolver(repository)

    unresolved = resolver.resolve_primary_application(candidate.id, _context(candidate_id=candidate.id))
    with uow.begin():
        created = resolver.ensure_application_for_candidate(
            candidate.id,
            _context(
                candidate_id=candidate.id,
                allow_create=True,
                require_application_anchor=True,
            ),
        )

    applications = repository.find_candidate_applications(candidate_id=candidate.id)
    assert unresolved.status == ResolutionStatus.UNRESOLVED
    assert created.status == ResolutionStatus.CREATED
    assert created.requisition_id is None
    assert len(applications) == 1
    assert applications[0].requisition_id is None


def test_slot_assignment_resolves_application_via_interview_link(db_session: Session) -> None:
    candidate = _seed_candidate(db_session)
    _seed_requisition(db_session, requisition_id=601)
    _seed_application(db_session, application_id=201, candidate_id=candidate.id, requisition_id=601)
    assignment = _seed_slot_assignment(db_session, assignment_id=77, candidate=candidate)
    interview = Interview(
        id=1,
        application_id=201,
        slot_assignment_id=assignment.id,
        kind="interview",
        status="scheduled",
        scheduled_at=_now(),
    )
    db_session.add(interview)
    db_session.commit()

    repository = SqlAlchemyApplicationResolverRepository(db_session)
    resolver = PrimaryApplicationResolver(repository)

    result = resolver.resolve_application_for_slot_assignment(
        assignment.id,
        _context(slot_assignment_id=assignment.id),
    )

    assert result.status == ResolutionStatus.RESOLVED
    assert result.application_id == 201
    assert result.used_signal == ResolverSignal.SLOT_ASSIGNMENT


def test_hh_vacancy_exact_match_resolves_existing_application(db_session: Session) -> None:
    candidate = _seed_candidate(db_session, hh_vacancy_id="9002")
    _seed_requisition(db_session, requisition_id=701, vacancy_id=9002)
    _seed_application(
        db_session,
        application_id=301,
        candidate_id=candidate.id,
        requisition_id=701,
        vacancy_id=9002,
    )

    repository = SqlAlchemyApplicationResolverRepository(db_session)
    resolver = PrimaryApplicationResolver(repository)

    result = resolver.resolve_application_for_hh_event(_context(hh_vacancy_id="9002"))

    assert result.status == ResolutionStatus.RESOLVED
    assert result.application_id == 301
    assert result.used_signal == ResolverSignal.HH_EXACT


def test_multiple_matching_requisitions_remain_ambiguous(db_session: Session) -> None:
    _seed_candidate(db_session, hh_vacancy_id="9003")
    _seed_requisition(db_session, requisition_id=801, vacancy_id=9003, title="Req A")
    _seed_requisition(db_session, requisition_id=802, vacancy_id=9003, title="Req B")

    repository = SqlAlchemyApplicationResolverRepository(db_session)
    resolver = PrimaryApplicationResolver(repository)

    result = resolver.resolve_application_for_hh_event(_context(hh_vacancy_id="9003"))

    assert result.status == ResolutionStatus.AMBIGUOUS
    assert result.application_id is None
    assert result.requires_manual_resolution is True


def test_archived_application_does_not_silently_reopen(db_session: Session) -> None:
    candidate = _seed_candidate(db_session)
    _seed_requisition(db_session, requisition_id=901)
    _seed_application(
        db_session,
        application_id=401,
        candidate_id=candidate.id,
        requisition_id=901,
        archived=True,
    )
    repository = SqlAlchemyApplicationResolverRepository(db_session)
    resolver = PrimaryApplicationResolver(repository)

    result = resolver.resolve_primary_application(
        candidate.id,
        _context(candidate_id=candidate.id, explicit_requisition_id=901),
    )

    assert result.status == ResolutionStatus.UNRESOLVED
    assert result.application_id is None


def test_duplicate_active_exact_applications_return_conflict(db_session: Session) -> None:
    candidate = _seed_candidate(db_session)
    _seed_requisition(db_session, requisition_id=1001)
    _seed_application(db_session, application_id=501, candidate_id=candidate.id, requisition_id=1001)
    _seed_application(db_session, application_id=502, candidate_id=candidate.id, requisition_id=1001)
    repository = SqlAlchemyApplicationResolverRepository(db_session)
    resolver = PrimaryApplicationResolver(repository)

    result = resolver.resolve_primary_application(
        candidate.id,
        _context(candidate_id=candidate.id, explicit_requisition_id=1001),
    )

    assert result.status == ResolutionStatus.DUPLICATE_CONFLICT
    assert result.requires_manual_resolution is True


def test_current_create_idempotency_cache_is_session_local_limitation(
    db_session: Session,
) -> None:
    candidate = _seed_candidate(db_session)
    _seed_requisition(db_session, requisition_id=1101, vacancy_id=9101)
    request = ApplicationCreateRequest(
        candidate_id=candidate.id,
        requisition_id=1101,
        vacancy_id=9101,
        signal=ResolverSignal.REQUISITION_CREATE,
        idempotency_key="phase-b-prep:create:1101",
        correlation_id="corr-create-1",
        source_system="unit_test",
        source_ref="candidate:1:req:1101",
    )

    uow1 = SqlAlchemyApplicationUnitOfWork(db_session)
    repository1 = SqlAlchemyApplicationResolverRepository(db_session, uow=uow1)
    with uow1.begin():
        first = repository1.create_application(request)
        assert (
            repository1.get_created_application_by_idempotency(
                idempotency_key=request.idempotency_key
            )
            == first
        )

    from backend.core.db import sync_engine

    with Session(sync_engine) as session2:
        uow2 = SqlAlchemyApplicationUnitOfWork(session2)
        repository2 = SqlAlchemyApplicationResolverRepository(session2, uow=uow2)

        assert (
            repository2.get_created_application_by_idempotency(
                idempotency_key=request.idempotency_key
            )
            is None
        )

        with uow2.begin():
            second = repository2.create_application(request)

        created_rows = session2.query(Application).filter(Application.candidate_id == candidate.id).all()
        assert len(created_rows) == 2
        assert second.application_id != first.application_id
