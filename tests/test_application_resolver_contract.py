from __future__ import annotations

import pytest
from backend.domain.applications import (
    ApplicationCreateRequest,
    ApplicationRecord,
    ApplicationResolverRepository,
    ApplicationState,
    PrimaryApplicationResolver,
    ResolutionStatus,
    ResolverContext,
    ResolverContextConflictError,
    ResolverSignal,
    ResolverSnapshot,
)

pytestmark = pytest.mark.no_db_cleanup


class FakeResolverRepository(ApplicationResolverRepository):
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, int], ResolverSnapshot] = {}
        self.hints: dict[str, ResolverSnapshot] = {}
        self.created_by_idempotency: dict[str, ApplicationRecord] = {}
        self.create_calls: list[ApplicationCreateRequest] = []
        self._next_application_id = 9000

    def put_candidate_snapshot(self, candidate_id: int, snapshot: ResolverSnapshot) -> None:
        self.snapshots[("candidate", candidate_id)] = snapshot

    def put_slot_snapshot(self, slot_assignment_id: int, snapshot: ResolverSnapshot) -> None:
        self.snapshots[("slot", slot_assignment_id)] = snapshot

    def put_hint_snapshot(self, key: str, snapshot: ResolverSnapshot) -> None:
        self.hints[key] = snapshot

    def get_snapshot(self, *, candidate_id: int, context: ResolverContext) -> ResolverSnapshot:
        return self.snapshots[("candidate", candidate_id)]

    def get_slot_assignment_snapshot(
        self, *, slot_assignment_id: int, context: ResolverContext
    ) -> ResolverSnapshot:
        return self.snapshots[("slot", slot_assignment_id)]

    def get_hh_event_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        return self.hints["hh"]

    def get_message_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        return self.hints["message"]

    def get_ai_output_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        return self.hints["ai"]

    def get_created_application_by_idempotency(
        self, *, idempotency_key: str
    ) -> ApplicationRecord | None:
        return self.created_by_idempotency.get(idempotency_key)

    def create_application(self, request: ApplicationCreateRequest) -> ApplicationRecord:
        self.create_calls.append(request)
        record = ApplicationRecord(
            application_id=self._next_application_id,
            candidate_id=request.candidate_id,
            requisition_id=request.requisition_id,
            vacancy_id=request.vacancy_id,
            state=ApplicationState.ACTIVE,
        )
        self._next_application_id += 1
        self.created_by_idempotency[request.idempotency_key] = record
        return record


def _context(**overrides: object) -> ResolverContext:
    base = {
        "producer_family": "candidate-create",
        "source_system": "admin_ui",
        "source_ref": "source-1",
        "allow_create": False,
        "require_application_anchor": False,
    }
    base.update(overrides)
    return ResolverContext(**base)


def _application(
    application_id: int,
    *,
    candidate_id: int = 1,
    requisition_id: int | None = None,
    state: ApplicationState = ApplicationState.ACTIVE,
) -> ApplicationRecord:
    return ApplicationRecord(
        application_id=application_id,
        candidate_id=candidate_id,
        requisition_id=requisition_id,
        state=state,
    )


def test_explicit_application_id_wins() -> None:
    repo = FakeResolverRepository()
    repo.put_candidate_snapshot(
        1,
        ResolverSnapshot(candidate_id=1, explicit_application=_application(11, requisition_id=101)),
    )
    resolver = PrimaryApplicationResolver(repo)

    result = resolver.resolve_primary_application(
        1, _context(explicit_application_id=11, candidate_id=1)
    )

    assert result.status == ResolutionStatus.RESOLVED
    assert result.application_id == 11
    assert result.used_signal == ResolverSignal.EXPLICIT_APPLICATION
    assert repo.create_calls == []


def test_context_candidate_mismatch_raises() -> None:
    repo = FakeResolverRepository()
    repo.put_candidate_snapshot(1, ResolverSnapshot(candidate_id=1))
    resolver = PrimaryApplicationResolver(repo)

    with pytest.raises(ResolverContextConflictError):
        resolver.resolve_primary_application(1, _context(candidate_id=2))


def test_explicit_requisition_creates_application_when_allowed() -> None:
    repo = FakeResolverRepository()
    repo.put_candidate_snapshot(
        1,
        ResolverSnapshot(candidate_id=1, explicit_requisition_ids=(501,)),
    )
    resolver = PrimaryApplicationResolver(repo)

    result = resolver.ensure_application_for_candidate(
        1,
        _context(
            candidate_id=1,
            explicit_requisition_id=501,
            allow_create=True,
            require_application_anchor=True,
        ),
    )

    assert result.status == ResolutionStatus.CREATED
    assert result.requisition_id == 501
    assert result.created_application is True
    assert repo.create_calls[0].signal == ResolverSignal.REQUISITION_CREATE


def test_active_slot_assignment_resolves_existing_application() -> None:
    repo = FakeResolverRepository()
    repo.put_slot_snapshot(
        77,
        ResolverSnapshot(
            candidate_id=1,
            slot_assignment_matches=(_application(22, requisition_id=502),),
        ),
    )
    resolver = PrimaryApplicationResolver(repo)

    result = resolver.resolve_application_for_slot_assignment(
        77,
        _context(slot_assignment_id=77),
    )

    assert result.status == ResolutionStatus.RESOLVED
    assert result.application_id == 22
    assert result.used_signal == ResolverSignal.SLOT_ASSIGNMENT


def test_hh_vacancy_exact_match_resolves_application() -> None:
    repo = FakeResolverRepository()
    repo.put_hint_snapshot(
        "hh",
        ResolverSnapshot(
            candidate_id=1,
            hh_matches=(_application(33, requisition_id=700),),
        ),
    )
    resolver = PrimaryApplicationResolver(repo)

    result = resolver.resolve_application_for_hh_event(
        _context(candidate_id=1, hh_vacancy_id="hh-1")
    )

    assert result.status == ResolutionStatus.RESOLVED
    assert result.application_id == 33
    assert result.used_signal == ResolverSignal.HH_EXACT


def test_multiple_possible_requisitions_are_ambiguous() -> None:
    repo = FakeResolverRepository()
    repo.put_candidate_snapshot(
        1,
        ResolverSnapshot(candidate_id=1, hh_requisition_ids=(10, 20)),
    )
    resolver = PrimaryApplicationResolver(repo)

    result = resolver.resolve_primary_application(
        1,
        _context(candidate_id=1, hh_vacancy_id="hh-ambiguous"),
    )

    assert result.status == ResolutionStatus.AMBIGUOUS
    assert result.requires_manual_resolution is True
    assert result.application_id is None
    assert repo.create_calls == []


def test_no_demand_context_creates_null_anchor_only_when_requested() -> None:
    repo = FakeResolverRepository()
    repo.put_candidate_snapshot(1, ResolverSnapshot(candidate_id=1))
    resolver = PrimaryApplicationResolver(repo)

    unresolved = resolver.resolve_primary_application(1, _context(candidate_id=1))
    created = resolver.ensure_application_for_candidate(
        1,
        _context(
            candidate_id=1,
            allow_create=True,
            require_application_anchor=True,
        ),
    )

    assert unresolved.status == ResolutionStatus.UNRESOLVED
    assert created.status == ResolutionStatus.CREATED
    assert created.requisition_id is None
    assert repo.create_calls[-1].signal == ResolverSignal.NULL_REQUISITION_CREATE


def test_archived_application_does_not_silently_reopen() -> None:
    repo = FakeResolverRepository()
    repo.put_candidate_snapshot(
        1,
        ResolverSnapshot(
            candidate_id=1,
            archived_matches=(_application(44, requisition_id=800, state=ApplicationState.ARCHIVED),),
            explicit_requisition_ids=(800,),
        ),
    )
    resolver = PrimaryApplicationResolver(repo)

    result = resolver.resolve_primary_application(
        1,
        _context(candidate_id=1, explicit_requisition_id=800),
    )

    assert result.status == ResolutionStatus.UNRESOLVED
    assert result.application_id is None
    assert repo.create_calls == []


def test_duplicate_application_risk_returns_conflict() -> None:
    repo = FakeResolverRepository()
    repo.put_candidate_snapshot(
        1,
        ResolverSnapshot(
            candidate_id=1,
            duplicate_exact_matches=(
                _application(55, requisition_id=900),
                _application(56, requisition_id=900),
            ),
        ),
    )
    resolver = PrimaryApplicationResolver(repo)

    result = resolver.resolve_primary_application(
        1,
        _context(candidate_id=1, explicit_requisition_id=900),
    )

    assert result.status == ResolutionStatus.DUPLICATE_CONFLICT
    assert result.requires_manual_resolution is True
    assert repo.create_calls == []


def test_same_create_idempotency_reuses_created_application() -> None:
    repo = FakeResolverRepository()
    snapshot = ResolverSnapshot(candidate_id=1, explicit_requisition_ids=(777,))
    repo.put_candidate_snapshot(1, snapshot)
    resolver = PrimaryApplicationResolver(repo)
    context = _context(
        candidate_id=1,
        explicit_requisition_id=777,
        allow_create=True,
        require_application_anchor=True,
    )

    first = resolver.ensure_application_for_candidate(1, context)
    second = resolver.ensure_application_for_candidate(1, context)

    assert first.status == ResolutionStatus.CREATED
    assert second.status == ResolutionStatus.RESOLVED
    assert second.application_id == first.application_id
    assert len(repo.create_calls) == 1
