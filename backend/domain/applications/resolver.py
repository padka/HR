from __future__ import annotations

from dataclasses import replace

from .contracts import (
    AIScopeConflictError,
    ApplicationCreateRequest,
    ApplicationRecord,
    ApplicationResolverRepository,
    CandidateNotFoundError,
    HHIdentityConflictError,
    ResolutionStatus,
    ResolverContext,
    ResolverContextConflictError,
    ResolverResult,
    ResolverSignal,
    ResolverSnapshot,
    SchedulingLinkIntegrityError,
    SlotAssignmentNotFoundError,
    ThreadCandidateMismatchError,
)
from .idempotency import build_resolver_idempotency_key


def _ensure_candidate_context(candidate_id: int, context: ResolverContext) -> None:
    if context.candidate_id is not None and context.candidate_id != candidate_id:
        raise ResolverContextConflictError(
            f"context candidate_id={context.candidate_id} does not match {candidate_id}"
        )


def _with_candidate(context: ResolverContext, candidate_id: int) -> ResolverContext:
    return replace(context, candidate_id=candidate_id)


def _resolved(
    *,
    snapshot: ResolverSnapshot,
    application: ApplicationRecord,
    signal: ResolverSignal,
    notes: tuple[str, ...] = (),
) -> ResolverResult:
    return ResolverResult(
        status=ResolutionStatus.RESOLVED,
        candidate_id=snapshot.candidate_id,
        application_id=application.application_id,
        requisition_id=application.requisition_id,
        created_application=False,
        used_signal=signal,
        resolution_notes=notes,
    )


def _created(
    *,
    snapshot: ResolverSnapshot,
    application: ApplicationRecord,
    signal: ResolverSignal,
    notes: tuple[str, ...] = (),
) -> ResolverResult:
    return ResolverResult(
        status=ResolutionStatus.CREATED,
        candidate_id=snapshot.candidate_id,
        application_id=application.application_id,
        requisition_id=application.requisition_id,
        created_application=True,
        used_signal=signal,
        resolution_notes=notes,
        emitted_event_types=("application.created",),
    )


def _ambiguous(snapshot: ResolverSnapshot, *notes: str) -> ResolverResult:
    return ResolverResult(
        status=ResolutionStatus.AMBIGUOUS,
        candidate_id=snapshot.candidate_id,
        requires_manual_resolution=True,
        resolution_notes=tuple(notes),
    )


def _duplicate_conflict(snapshot: ResolverSnapshot, *notes: str) -> ResolverResult:
    return ResolverResult(
        status=ResolutionStatus.DUPLICATE_CONFLICT,
        candidate_id=snapshot.candidate_id,
        requires_manual_resolution=True,
        resolution_notes=tuple(notes),
    )


def _unresolved(snapshot: ResolverSnapshot, *notes: str) -> ResolverResult:
    return ResolverResult(
        status=ResolutionStatus.UNRESOLVED,
        candidate_id=snapshot.candidate_id,
        resolution_notes=tuple(notes),
    )


def _require_candidate(snapshot: ResolverSnapshot) -> None:
    if not snapshot.candidate_exists:
        raise CandidateNotFoundError(f"candidate_id={snapshot.candidate_id} not found")


def _validate_snapshot(snapshot: ResolverSnapshot) -> None:
    _require_candidate(snapshot)
    if snapshot.scheduling_integrity_error:
        raise SchedulingLinkIntegrityError(
            "slot scheduling data is too inconsistent for deterministic resolution"
        )
    if snapshot.message_candidate_mismatch:
        raise ThreadCandidateMismatchError(
            "message thread candidate linkage is inconsistent"
        )
    if snapshot.ai_scope_conflict:
        raise AIScopeConflictError("AI scope cannot be mapped safely to this candidate")
    if snapshot.hh_identity_conflict:
        raise HHIdentityConflictError(
            "HH identity data maps to multiple candidate/application chains"
        )


def _pick_unique_match(
    *,
    snapshot: ResolverSnapshot,
    matches: tuple[ApplicationRecord, ...],
    signal: ResolverSignal,
    duplicate_note: str,
) -> ResolverResult | None:
    if not matches:
        return None
    if len(matches) > 1:
        return _duplicate_conflict(snapshot, duplicate_note)
    return _resolved(snapshot=snapshot, application=matches[0], signal=signal)


def _build_create_request(
    *,
    snapshot: ResolverSnapshot,
    context: ResolverContext,
    signal: ResolverSignal,
    requisition_id: int | None,
) -> ApplicationCreateRequest:
    return ApplicationCreateRequest(
        candidate_id=snapshot.candidate_id,
        requisition_id=requisition_id,
        vacancy_id=context.explicit_vacancy_id,
        signal=signal,
        idempotency_key=build_resolver_idempotency_key(
            candidate_id=snapshot.candidate_id,
            producer_family=context.producer_family,
            source_ref=context.source_ref,
            signal=signal.value,
            requisition_id=requisition_id,
        ),
        correlation_id=context.correlation_id,
        source_system=context.source_system,
        source_ref=context.source_ref,
    )


def decide_primary_application(
    *,
    snapshot: ResolverSnapshot,
    context: ResolverContext,
    allow_create: bool,
) -> tuple[ResolverResult, ApplicationCreateRequest | None]:
    _validate_snapshot(snapshot)

    if snapshot.explicit_application is not None:
        return (
            _resolved(
                snapshot=snapshot,
                application=snapshot.explicit_application,
                signal=ResolverSignal.EXPLICIT_APPLICATION,
            ),
            None,
        )

    exact_duplicate = snapshot.duplicate_exact_matches
    if exact_duplicate:
        return (
            _duplicate_conflict(
                snapshot,
                "multiple active exact applications prevent deterministic selection",
            ),
            None,
        )

    exact_match = _pick_unique_match(
        snapshot=snapshot,
        matches=snapshot.explicit_requisition_matches,
        signal=ResolverSignal.EXPLICIT_REQUISITION,
        duplicate_note="multiple applications match the explicit requisition",
    )
    if exact_match is not None:
        return exact_match, None

    slot_match = _pick_unique_match(
        snapshot=snapshot,
        matches=snapshot.slot_assignment_matches,
        signal=ResolverSignal.SLOT_ASSIGNMENT,
        duplicate_note="multiple applications match the slot assignment",
    )
    if slot_match is not None:
        return slot_match, None

    hh_match = _pick_unique_match(
        snapshot=snapshot,
        matches=snapshot.hh_matches,
        signal=ResolverSignal.HH_EXACT,
        duplicate_note="multiple applications match the HH signal",
    )
    if hh_match is not None:
        return hh_match, None

    if context.allow_archived_reuse and len(snapshot.archived_matches) == 1:
        return (
            _resolved(
                snapshot=snapshot,
                application=snapshot.archived_matches[0],
                signal=ResolverSignal.EXPLICIT_REQUISITION,
                notes=("archived application reuse explicitly allowed",),
            ),
            None,
        )

    if len(snapshot.explicit_requisition_ids) > 1:
        return _ambiguous(snapshot, "multiple requisitions match the explicit demand"), None
    if len(snapshot.slot_assignment_requisition_ids) > 1:
        return _ambiguous(
            snapshot,
            "slot assignment maps to multiple requisitions; refusing aggressive guess",
        ), None
    if len(snapshot.hh_requisition_ids) > 1:
        return _ambiguous(
            snapshot,
            "HH signal maps to multiple requisitions; refusing aggressive guess",
        ), None

    null_matches = snapshot.null_requisition_matches
    if len(null_matches) > 1 or snapshot.duplicate_null_matches:
        return (
            _duplicate_conflict(
                snapshot,
                "multiple active null-requisition applications require manual review",
            ),
            None,
        )
    if len(null_matches) == 1:
        return (
            _resolved(
                snapshot=snapshot,
                application=null_matches[0],
                signal=ResolverSignal.NULL_REQUISITION_REUSE,
            ),
            None,
        )

    if not allow_create or not context.allow_create:
        return _unresolved(snapshot, "no deterministic application anchor found"), None

    if len(snapshot.explicit_requisition_ids) == 1:
        return _unresolved(
            snapshot, "create requisition-bound application for explicit demand"
        ), _build_create_request(
            snapshot=snapshot,
            context=context,
            signal=ResolverSignal.REQUISITION_CREATE,
            requisition_id=snapshot.explicit_requisition_ids[0],
        )

    if len(snapshot.slot_assignment_requisition_ids) == 1:
        return _unresolved(
            snapshot, "create requisition-bound application for slot-driven demand"
        ), _build_create_request(
            snapshot=snapshot,
            context=context,
            signal=ResolverSignal.SLOT_ASSIGNMENT,
            requisition_id=snapshot.slot_assignment_requisition_ids[0],
        )

    if len(snapshot.hh_requisition_ids) == 1:
        return _unresolved(
            snapshot, "create requisition-bound application for HH demand"
        ), _build_create_request(
            snapshot=snapshot,
            context=context,
            signal=ResolverSignal.HH_EXACT,
            requisition_id=snapshot.hh_requisition_ids[0],
        )

    if context.require_application_anchor:
        return _unresolved(
            snapshot,
            "create null-requisition application because caller requires an anchor",
        ), _build_create_request(
            snapshot=snapshot,
            context=context,
            signal=ResolverSignal.NULL_REQUISITION_CREATE,
            requisition_id=None,
        )

    return _unresolved(snapshot, "no deterministic application anchor found"), None


class PrimaryApplicationResolver:
    def __init__(self, repository: ApplicationResolverRepository) -> None:
        self._repository = repository

    def resolve_primary_application(
        self, candidate_id: int, context: ResolverContext
    ) -> ResolverResult:
        _ensure_candidate_context(candidate_id, context)
        resolved_context = _with_candidate(context, candidate_id)
        snapshot = self._repository.get_snapshot(
            candidate_id=candidate_id,
            context=resolved_context,
        )
        result, _ = decide_primary_application(
            snapshot=snapshot,
            context=resolved_context,
            allow_create=False,
        )
        return result

    def ensure_application_for_candidate(
        self, candidate_id: int, context: ResolverContext
    ) -> ResolverResult:
        _ensure_candidate_context(candidate_id, context)
        resolved_context = _with_candidate(context, candidate_id)
        snapshot = self._repository.get_snapshot(
            candidate_id=candidate_id,
            context=resolved_context,
        )
        result, create_request = decide_primary_application(
            snapshot=snapshot,
            context=resolved_context,
            allow_create=True,
        )
        if create_request is None:
            return result

        existing = self._repository.get_created_application_by_idempotency(
            idempotency_key=create_request.idempotency_key
        )
        if existing is not None:
            return _resolved(
                snapshot=snapshot,
                application=existing,
                signal=create_request.signal,
                notes=("create request already satisfied for this idempotency key",),
            )

        created = self._repository.create_application(create_request)
        return _created(
            snapshot=snapshot,
            application=created,
            signal=create_request.signal,
            notes=result.resolution_notes,
        )

    def resolve_application_for_slot_assignment(
        self, slot_assignment_id: int, context: ResolverContext
    ) -> ResolverResult:
        snapshot = self._repository.get_slot_assignment_snapshot(
            slot_assignment_id=slot_assignment_id,
            context=context,
        )
        if not snapshot.slot_assignment_found:
            raise SlotAssignmentNotFoundError(
                f"slot_assignment_id={slot_assignment_id} not found"
            )
        result, create_request = decide_primary_application(
            snapshot=snapshot,
            context=_with_candidate(context, snapshot.candidate_id),
            allow_create=bool(context.allow_create),
        )
        if create_request is None:
            return result
        existing = self._repository.get_created_application_by_idempotency(
            idempotency_key=create_request.idempotency_key
        )
        if existing is not None:
            return _resolved(
                snapshot=snapshot,
                application=existing,
                signal=create_request.signal,
                notes=("slot-based create request already satisfied",),
            )
        created = self._repository.create_application(create_request)
        return _created(
            snapshot=snapshot,
            application=created,
            signal=create_request.signal,
            notes=result.resolution_notes,
        )

    def resolve_application_for_hh_event(self, context: ResolverContext) -> ResolverResult:
        snapshot = self._repository.get_hh_event_snapshot(context=context)
        result, create_request = decide_primary_application(
            snapshot=snapshot,
            context=_with_candidate(context, snapshot.candidate_id),
            allow_create=bool(context.allow_create),
        )
        if create_request is None:
            return result
        existing = self._repository.get_created_application_by_idempotency(
            idempotency_key=create_request.idempotency_key
        )
        if existing is not None:
            return _resolved(
                snapshot=snapshot,
                application=existing,
                signal=create_request.signal,
                notes=("HH create request already satisfied",),
            )
        created = self._repository.create_application(create_request)
        return _created(
            snapshot=snapshot,
            application=created,
            signal=create_request.signal,
            notes=result.resolution_notes,
        )

    def resolve_application_for_message(self, context: ResolverContext) -> ResolverResult:
        snapshot = self._repository.get_message_snapshot(context=context)
        result, create_request = decide_primary_application(
            snapshot=snapshot,
            context=_with_candidate(context, snapshot.candidate_id),
            allow_create=bool(context.allow_create),
        )
        if create_request is None:
            return result
        existing = self._repository.get_created_application_by_idempotency(
            idempotency_key=create_request.idempotency_key
        )
        if existing is not None:
            return _resolved(
                snapshot=snapshot,
                application=existing,
                signal=create_request.signal,
                notes=("message create request already satisfied",),
            )
        created = self._repository.create_application(create_request)
        return _created(
            snapshot=snapshot,
            application=created,
            signal=create_request.signal,
            notes=result.resolution_notes,
        )

    def resolve_application_for_ai_output(self, context: ResolverContext) -> ResolverResult:
        snapshot = self._repository.get_ai_output_snapshot(context=context)
        result, create_request = decide_primary_application(
            snapshot=snapshot,
            context=_with_candidate(context, snapshot.candidate_id),
            allow_create=bool(context.allow_create),
        )
        if create_request is None:
            return result
        existing = self._repository.get_created_application_by_idempotency(
            idempotency_key=create_request.idempotency_key
        )
        if existing is not None:
            return _resolved(
                snapshot=snapshot,
                application=existing,
                signal=create_request.signal,
                notes=("AI create request already satisfied",),
            )
        created = self._repository.create_application(create_request)
        return _created(
            snapshot=snapshot,
            application=created,
            signal=create_request.signal,
            notes=result.resolution_notes,
        )
