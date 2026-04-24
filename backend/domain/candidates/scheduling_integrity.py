from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import false, or_, select
from sqlalchemy.orm import selectinload

from backend.domain.candidates.models import User
from backend.domain.models import Slot, SlotAssignment, SlotAssignmentStatus, SlotStatus

WRITE_BEHAVIOR_ALLOW = "allow"
WRITE_BEHAVIOR_ALLOW_WITH_WARNING = "allow_with_warning"
WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR = "needs_manual_repair"

INTEGRITY_STATE_CONSISTENT = "consistent"
INTEGRITY_STATE_TRANSITIONAL_WARNING = "transitional_warning"
INTEGRITY_STATE_NEEDS_MANUAL_REPAIR = "needs_manual_repair"

REPAIRABILITY_NOT_NEEDED = "not_needed"
REPAIRABILITY_REPAIRABLE = "repairable"
REPAIRABILITY_MANUAL_ONLY = "manual_only"

REPAIR_ACTION_ASSIGNMENT_AUTHORITATIVE = "assignment_authoritative"
REPAIR_ACTION_RESOLVE_TO_ACTIVE_ASSIGNMENT = "resolve_to_active_assignment"
REPAIR_ACTION_CANCEL_ACTIVE_ASSIGNMENT = "cancel_active_assignment"
REPAIR_ACTION_REBIND_ASSIGNMENT_SLOT = "rebind_assignment_slot"

_MANUAL_REPAIR_AUDIT_ACTION = "scheduling_repair.manual_resolution"
_AUDIT_FIELDS_COMMON = [
    "performed_by_type",
    "performed_by_id",
    "repair_action",
    "issue_codes_before",
    "issue_codes_after",
    "required_confirmations",
]

ACTIVE_ASSIGNMENT_STATUSES = {
    SlotAssignmentStatus.OFFERED,
    SlotAssignmentStatus.CONFIRMED,
    SlotAssignmentStatus.RESCHEDULE_REQUESTED,
    SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
}

ACTIVE_SLOT_STATUSES = {
    SlotStatus.PENDING,
    SlotStatus.BOOKED,
    SlotStatus.CONFIRMED,
    SlotStatus.CONFIRMED_BY_CANDIDATE,
}

_ALLOWED_SLOT_STATUSES_BY_ASSIGNMENT = {
    SlotAssignmentStatus.OFFERED: {SlotStatus.PENDING},
    SlotAssignmentStatus.CONFIRMED: {
        SlotStatus.BOOKED,
        SlotStatus.CONFIRMED,
        SlotStatus.CONFIRMED_BY_CANDIDATE,
    },
    SlotAssignmentStatus.RESCHEDULE_REQUESTED: {
        SlotStatus.PENDING,
        SlotStatus.BOOKED,
        SlotStatus.CONFIRMED_BY_CANDIDATE,
    },
    SlotAssignmentStatus.RESCHEDULE_CONFIRMED: {
        SlotStatus.BOOKED,
        SlotStatus.CONFIRMED,
        SlotStatus.CONFIRMED_BY_CANDIDATE,
    },
}

_REPAIRABLE_ASSIGNMENT_STATUSES = {
    SlotAssignmentStatus.OFFERED,
    SlotAssignmentStatus.CONFIRMED,
    SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
}


def _normalize_assignment_status(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _normalize_slot_status(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _comparable_dt(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _pick_latest_assignment(slot_assignments: Sequence[SlotAssignment]) -> Optional[SlotAssignment]:
    if not slot_assignments:
        return None
    return max(
        slot_assignments,
        key=lambda item: (
            _comparable_dt(
                getattr(item, "updated_at", None)
                or getattr(item, "created_at", None)
            ),
            getattr(item, "id", 0),
        ),
    )


def _pick_active_slot(slots: Sequence[Slot], *, now: datetime) -> Optional[Slot]:
    active_slots = [
        slot
        for slot in slots
        if _normalize_slot_status(getattr(slot, "status", None)) in ACTIVE_SLOT_STATUSES
    ]
    if not active_slots:
        return None
    upcoming = [
        slot
        for slot in active_slots
        if getattr(slot, "start_utc", None) is None
        or getattr(slot, "start_utc", None) >= now - timedelta(hours=1)
    ]
    pool = upcoming or active_slots
    return min(
        pool,
        key=lambda item: (
            (
                _comparable_dt(getattr(item, "start_utc", None))
                if getattr(item, "start_utc", None) is not None
                else datetime.max.replace(tzinfo=timezone.utc)
            ),
            getattr(item, "id", 0),
        ),
    )


def _issue(
    *,
    code: str,
    message: str,
    write_behavior: str,
    severity: str = "warning",
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "write_behavior": write_behavior,
    }


def _known_candidate_tg_ids(
    slots: Sequence[Slot],
    slot_assignments: Sequence[SlotAssignment],
    active_assignment: Optional[SlotAssignment],
) -> set[int]:
    values: set[int] = set()
    for raw in (
        getattr(active_assignment, "candidate_tg_id", None),
        *(getattr(assignment, "candidate_tg_id", None) for assignment in slot_assignments),
    ):
        if raw is None:
            continue
        try:
            values.add(int(raw))
        except (TypeError, ValueError):
            continue
    return values


def _slot_claimed_by_other_candidate(
    slot: Slot,
    *,
    candidate_id: Optional[str],
    candidate_tg_ids: set[int],
) -> bool:
    slot_candidate_id = getattr(slot, "candidate_id", None)
    slot_candidate_tg_id = getattr(slot, "candidate_tg_id", None)
    if slot_candidate_id is None and slot_candidate_tg_id is None:
        return False
    if candidate_id is not None and slot_candidate_id == candidate_id:
        return False
    if slot_candidate_tg_id is not None:
        try:
            if int(slot_candidate_tg_id) in candidate_tg_ids:
                return False
        except (TypeError, ValueError):
            pass
    return True


def _selection_requirements(
    *,
    candidate_choice_required: bool = False,
    owner_choice_required: bool = False,
    assignment_choice_required: bool = False,
    slot_choice_required: bool = False,
) -> dict[str, bool]:
    return {
        "candidate_choice_required": candidate_choice_required,
        "owner_choice_required": owner_choice_required,
        "assignment_choice_required": assignment_choice_required,
        "slot_choice_required": slot_choice_required,
    }


def _repair_action(
    *,
    action: str,
    label: str,
    resolution_kind: str,
    safe_outcome: str,
    audit_action: str,
    required_confirmations: Sequence[str] = (),
    selection_options: Optional[dict[str, list[dict[str, Any]]]] = None,
    candidate_choice_required: bool = False,
    owner_choice_required: bool = False,
    assignment_choice_required: bool = False,
    slot_choice_required: bool = False,
) -> dict[str, Any]:
    return {
        "action": action,
        "label": label,
        "resolution_kind": resolution_kind,
        "safe_outcome": safe_outcome,
        "audit_action": audit_action,
        "required_confirmations": list(required_confirmations),
        "selection_options": dict(selection_options or {}),
        "selection_requirements": _selection_requirements(
            candidate_choice_required=candidate_choice_required,
            owner_choice_required=owner_choice_required,
            assignment_choice_required=assignment_choice_required,
            slot_choice_required=slot_choice_required,
        ),
    }


def _repair_conflict_class(
    *,
    code: str,
    policy: str,
    label: str,
    supported: bool,
    preconditions: Sequence[str],
    affected_entities: Sequence[str],
    allowed_actions: Sequence[dict[str, Any]],
    forbidden_resolutions: Sequence[str],
    minimal_safe_result: str,
    required_audit_fields: Sequence[str],
    candidate_choice_required: bool = False,
    owner_choice_required: bool = False,
    assignment_choice_required: bool = False,
    slot_choice_required: bool = False,
) -> dict[str, Any]:
    return {
        "code": code,
        "policy": policy,
        "label": label,
        "supported": supported,
        "preconditions": list(preconditions),
        "affected_entities": list(affected_entities),
        "allowed_actions": list(allowed_actions),
        "forbidden_resolutions": list(forbidden_resolutions),
        "minimal_safe_result": minimal_safe_result,
        "required_audit_fields": list(required_audit_fields),
        "selection_requirements": _selection_requirements(
            candidate_choice_required=candidate_choice_required,
            owner_choice_required=owner_choice_required,
            assignment_choice_required=assignment_choice_required,
            slot_choice_required=slot_choice_required,
        ),
    }


def _dedupe_actions(actions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        key = str(action.get("action") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(dict(action))
    return unique


def _candidate_owned_active_slots(
    *,
    slots: Sequence[Slot],
    candidate_id: Optional[str],
    candidate_tg_ids: set[int],
    exclude_slot_ids: Sequence[int] = (),
) -> list[Slot]:
    excluded = {int(value) for value in exclude_slot_ids}
    result: list[Slot] = []
    for slot in slots:
        slot_id = getattr(slot, "id", None)
        if slot_id is None or int(slot_id) in excluded:
            continue
        if _normalize_slot_status(getattr(slot, "status", None)) not in ACTIVE_SLOT_STATUSES:
            continue
        if _slot_claimed_by_other_candidate(
            slot,
            candidate_id=candidate_id,
            candidate_tg_ids=candidate_tg_ids,
        ):
            continue
        result.append(slot)
    return result


def _single_purpose_slots(slots: Sequence[Slot]) -> bool:
    purposes = {
        str(getattr(slot, "purpose", None) or "interview").strip().lower()
        for slot in slots
    }
    return len(purposes) <= 1


def _slot_selection_option(slot: Slot) -> dict[str, Any]:
    return {
        "id": int(slot.id),
        "start_utc": _iso(getattr(slot, "start_utc", None)),
        "status": _normalize_slot_status(getattr(slot, "status", None)),
        "purpose": str(getattr(slot, "purpose", None) or "interview").strip().lower(),
        "recruiter_id": getattr(slot, "recruiter_id", None),
    }


def _assignment_selection_option(
    assignment: SlotAssignment,
    *,
    slot: Slot,
) -> dict[str, Any]:
    return {
        "id": int(assignment.id),
        "slot_id": getattr(slot, "id", None),
        "slot_status": _normalize_slot_status(getattr(slot, "status", None)),
        "status": _normalize_assignment_status(getattr(assignment, "status", None)),
        "start_utc": _iso(getattr(slot, "start_utc", None)),
        "purpose": str(getattr(slot, "purpose", None) or "interview").strip().lower(),
        "recruiter_id": getattr(assignment, "recruiter_id", None),
    }


def _taxonomy_result(
    *,
    repairability: str,
    repair_options: Sequence[dict[str, Any]],
    manual_repair_reasons: Sequence[str],
    conflict_classes: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    combined_actions = _dedupe_actions(
        [
            *list(repair_options),
            *[
                action
                for conflict_class in conflict_classes
                for action in (conflict_class.get("allowed_actions") or [])
                if isinstance(action, dict)
            ],
        ]
    )
    required_confirmations: list[str] = []
    seen_confirmations: set[str] = set()
    for action in combined_actions:
        for confirmation in action.get("required_confirmations") or []:
            code = str(confirmation or "").strip()
            if not code or code in seen_confirmations:
                continue
            seen_confirmations.add(code)
            required_confirmations.append(code)

    audit_actions: list[str] = []
    seen_audit_actions: set[str] = set()
    for action in combined_actions:
        audit_action = str(action.get("audit_action") or "").strip()
        if not audit_action or audit_action in seen_audit_actions:
            continue
        seen_audit_actions.add(audit_action)
        audit_actions.append(audit_action)

    return {
        "repairability": repairability,
        "repair_options": list(repair_options),
        "manual_repair_reasons": list(manual_repair_reasons),
        "repair_workflow": {
            "policy": repairability,
            "conflict_class": (
                next(iter(manual_repair_reasons), None)
                or next(
                    (
                        str(conflict_class.get("code") or "").strip() or None
                        for conflict_class in conflict_classes
                    ),
                    None,
                )
            ),
            "conflict_classes": list(conflict_classes),
            "allowed_actions": combined_actions,
            "required_confirmations": required_confirmations,
            "audit_metadata": {
                "required": repairability != REPAIRABILITY_NOT_NEEDED,
                "entity_type": "slot_assignment",
                "action_codes": audit_actions,
            },
        },
    }


def build_scheduling_repair_taxonomy(
    *,
    slots: Sequence[Slot],
    slot_assignments: Sequence[SlotAssignment],
    integrity: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    report = integrity or build_scheduling_integrity_report(
        slots=slots,
        slot_assignments=slot_assignments,
    )
    issues = list(report.get("issues") or [])
    if not issues:
        return _taxonomy_result(
            repairability=REPAIRABILITY_NOT_NEEDED,
            repair_options=[],
            manual_repair_reasons=[],
            conflict_classes=[],
        )

    active_assignment = report.get("active_assignment")
    candidate_tg_ids = _known_candidate_tg_ids(slots, slot_assignments, active_assignment)
    candidate_id = getattr(active_assignment, "candidate_id", None) if active_assignment is not None else None
    if active_assignment is None:
        return _taxonomy_result(
            repairability=REPAIRABILITY_MANUAL_ONLY,
            repair_options=[],
            manual_repair_reasons=["no_active_assignment_owner"],
            conflict_classes=[
                _repair_conflict_class(
                    code="no_active_assignment_owner",
                    policy=REPAIRABILITY_MANUAL_ONLY,
                    label="No active assignment owner",
                    supported=False,
                    preconditions=[
                        "Scheduling issues exist but no single active SlotAssignment owns the state.",
                    ],
                    affected_entities=["slot", "slot_assignment"],
                    allowed_actions=[],
                    forbidden_resolutions=[
                        "hidden_autofix",
                        "write_on_read",
                    ],
                    minimal_safe_result="operator_review_required",
                    required_audit_fields=[],
                )
            ],
        )

    active_assignment_status = _normalize_assignment_status(getattr(active_assignment, "status", None))
    slot_by_id = {
        int(getattr(slot, "id")): slot
        for slot in slots
        if getattr(slot, "id", None) is not None
    }
    assignment_slot = getattr(active_assignment, "slot", None)
    assignment_slot_id = getattr(assignment_slot, "id", None) or getattr(active_assignment, "slot_id", None)
    if assignment_slot is None and assignment_slot_id is not None:
        assignment_slot = slot_by_id.get(int(assignment_slot_id))

    active_assignments = [
        assignment
        for assignment in slot_assignments
        if _normalize_assignment_status(getattr(assignment, "status", None))
        in ACTIVE_ASSIGNMENT_STATUSES
    ]
    if len(active_assignments) > 1:
        selectable_owner_exists = False
        assignment_purposes: set[str] = set()
        recruiter_ids = {
            getattr(assignment, "recruiter_id", None)
            for assignment in active_assignments
        }
        for assignment in active_assignments:
            current_slot = getattr(assignment, "slot", None)
            if current_slot is None and getattr(assignment, "slot_id", None) is not None:
                current_slot = slot_by_id.get(int(assignment.slot_id))
            if current_slot is None:
                continue
            assignment_purposes.add(
                str(getattr(current_slot, "purpose", None) or "interview").strip().lower()
            )
            if _slot_claimed_by_other_candidate(
                current_slot,
                candidate_id=candidate_id,
                candidate_tg_ids=candidate_tg_ids,
            ):
                continue
            if _normalize_assignment_status(getattr(assignment, "status", None)) in _REPAIRABLE_ASSIGNMENT_STATUSES:
                selectable_owner_exists = True

        allowed_actions: list[dict[str, Any]] = []
        if len(recruiter_ids) == 1 and len(assignment_purposes) <= 1 and selectable_owner_exists:
            assignment_options = [
                _assignment_selection_option(assignment, slot=current_slot)
                for assignment in active_assignments
                if (current_slot := (
                    getattr(assignment, "slot", None)
                    or (
                        slot_by_id.get(int(assignment.slot_id))
                        if getattr(assignment, "slot_id", None) is not None
                        else None
                    )
                )) is not None
            ]
            allowed_actions.append(
                _repair_action(
                    action=REPAIR_ACTION_RESOLVE_TO_ACTIVE_ASSIGNMENT,
                    label="Resolve to selected active assignment",
                    resolution_kind="manual",
                    safe_outcome="single_active_assignment_owner",
                    audit_action=_MANUAL_REPAIR_AUDIT_ACTION,
                    required_confirmations=[
                        "selected_assignment_is_canonical",
                        "cancel_non_selected_active_assignments",
                    ],
                    selection_options={"assignments": assignment_options},
                    assignment_choice_required=True,
                )
            )

        return _taxonomy_result(
            repairability=REPAIRABILITY_MANUAL_ONLY,
            repair_options=[],
            manual_repair_reasons=["multiple_active_assignments"],
            conflict_classes=[
                _repair_conflict_class(
                    code="multiple_active_assignments",
                    policy=REPAIRABILITY_MANUAL_ONLY,
                    label="Multiple active assignments",
                    supported=bool(allowed_actions),
                    preconditions=[
                        "More than one active SlotAssignment exists for the same candidate.",
                    ],
                    affected_entities=["slot_assignment", "slot"],
                    allowed_actions=allowed_actions,
                    forbidden_resolutions=[
                        "hidden_autofix",
                        "keep_multiple_active_assignments",
                    ],
                    minimal_safe_result="single_active_assignment_owner",
                    required_audit_fields=[
                        *_AUDIT_FIELDS_COMMON,
                        "selected_assignment_id",
                        "cancelled_assignment_ids",
                        "released_slot_ids",
                    ],
                    assignment_choice_required=True,
                )
            ],
        )

    candidate_owned_active_slots = _candidate_owned_active_slots(
        slots=slots,
        candidate_id=candidate_id,
        candidate_tg_ids=candidate_tg_ids,
        exclude_slot_ids=[int(assignment_slot.id)] if getattr(assignment_slot, "id", None) is not None else (),
    )
    same_recruiter_candidate_slots = [
        slot
        for slot in candidate_owned_active_slots
        if getattr(slot, "recruiter_id", None) == getattr(active_assignment, "recruiter_id", None)
    ]

    if assignment_slot is None:
        allowed_actions = [
            _repair_action(
                action=REPAIR_ACTION_CANCEL_ACTIVE_ASSIGNMENT,
                label="Cancel broken active assignment",
                resolution_kind="manual",
                safe_outcome="no_active_assignment_owner",
                audit_action=_MANUAL_REPAIR_AUDIT_ACTION,
                required_confirmations=[
                    "cancel_active_assignment",
                    "candidate_loses_assignment_owned_schedule",
                ],
            )
        ]
        if same_recruiter_candidate_slots and _single_purpose_slots(same_recruiter_candidate_slots):
            allowed_actions.append(
                _repair_action(
                    action=REPAIR_ACTION_REBIND_ASSIGNMENT_SLOT,
                    label="Rebind assignment to selected slot",
                    resolution_kind="manual",
                    safe_outcome="assignment_slot_pair_rebound",
                    audit_action=_MANUAL_REPAIR_AUDIT_ACTION,
                    required_confirmations=[
                        "selected_slot_is_canonical",
                        "rebind_assignment_to_selected_slot",
                    ],
                    selection_options={
                        "slots": [
                            _slot_selection_option(slot)
                            for slot in same_recruiter_candidate_slots
                        ]
                    },
                    slot_choice_required=True,
                )
            )
        return _taxonomy_result(
            repairability=REPAIRABILITY_MANUAL_ONLY,
            repair_options=[],
            manual_repair_reasons=["assignment_slot_missing"],
            conflict_classes=[
                _repair_conflict_class(
                    code="assignment_slot_missing",
                    policy=REPAIRABILITY_MANUAL_ONLY,
                    label="Assignment slot missing",
                    supported=bool(allowed_actions),
                    preconditions=[
                        "The active SlotAssignment points to a missing Slot row.",
                    ],
                    affected_entities=["slot_assignment", "slot"],
                    allowed_actions=allowed_actions,
                    forbidden_resolutions=[
                        "hidden_autofix",
                        "create_new_slot_implicitly",
                    ],
                    minimal_safe_result="broken_assignment_removed_or_rebound",
                    required_audit_fields=[
                        *_AUDIT_FIELDS_COMMON,
                        "selected_slot_id",
                        "cancelled_assignment_ids",
                        "released_slot_ids",
                    ],
                    slot_choice_required=(
                        any(
                            str(action.get("action") or "").strip().lower() == REPAIR_ACTION_REBIND_ASSIGNMENT_SLOT
                            for action in allowed_actions
                        )
                    ),
                )
            ],
        )

    if active_assignment_status not in _REPAIRABLE_ASSIGNMENT_STATUSES:
        return _taxonomy_result(
            repairability=REPAIRABILITY_MANUAL_ONLY,
            repair_options=[],
            manual_repair_reasons=["assignment_status_not_repairable"],
            conflict_classes=[
                _repair_conflict_class(
                    code="assignment_status_not_repairable",
                    policy=REPAIRABILITY_MANUAL_ONLY,
                    label="Assignment status not repairable",
                    supported=False,
                    preconditions=[
                        "Active assignment status is transitional and not safe for backend repair.",
                    ],
                    affected_entities=["slot_assignment", "slot"],
                    allowed_actions=[],
                    forbidden_resolutions=[
                        "hidden_autofix",
                        "status_rewrite_without_follow_up",
                    ],
                    minimal_safe_result="operator_review_required",
                    required_audit_fields=[],
                )
            ],
        )

    if _slot_claimed_by_other_candidate(
        assignment_slot,
        candidate_id=candidate_id,
        candidate_tg_ids=candidate_tg_ids,
    ):
        allowed_actions = [
            _repair_action(
                action=REPAIR_ACTION_CANCEL_ACTIVE_ASSIGNMENT,
                label="Cancel broken active assignment",
                resolution_kind="manual",
                safe_outcome="no_active_assignment_owner",
                audit_action=_MANUAL_REPAIR_AUDIT_ACTION,
                required_confirmations=[
                    "cancel_active_assignment",
                    "candidate_loses_assignment_owned_schedule",
                ],
            )
        ]
        if same_recruiter_candidate_slots and _single_purpose_slots(same_recruiter_candidate_slots):
            allowed_actions.append(
                _repair_action(
                    action=REPAIR_ACTION_REBIND_ASSIGNMENT_SLOT,
                    label="Rebind assignment to selected slot",
                    resolution_kind="manual",
                    safe_outcome="assignment_slot_pair_rebound",
                    audit_action=_MANUAL_REPAIR_AUDIT_ACTION,
                    required_confirmations=[
                        "selected_slot_is_canonical",
                        "rebind_assignment_to_selected_slot",
                    ],
                    selection_options={
                        "slots": [
                            _slot_selection_option(slot)
                            for slot in same_recruiter_candidate_slots
                        ]
                    },
                    slot_choice_required=True,
                )
            )
        return _taxonomy_result(
            repairability=REPAIRABILITY_MANUAL_ONLY,
            repair_options=[],
            manual_repair_reasons=["assignment_slot_claimed_by_other_candidate"],
            conflict_classes=[
                _repair_conflict_class(
                    code="assignment_slot_claimed_by_other_candidate",
                    policy=REPAIRABILITY_MANUAL_ONLY,
                    label="Assignment slot claimed by another candidate",
                    supported=bool(allowed_actions),
                    preconditions=[
                        "The assignment points to a Slot already bound to another candidate.",
                    ],
                    affected_entities=["slot_assignment", "slot"],
                    allowed_actions=allowed_actions,
                    forbidden_resolutions=[
                        "hidden_autofix",
                        "overwrite_other_candidate_slot_claim",
                    ],
                    minimal_safe_result="broken_assignment_removed_or_rebound",
                    required_audit_fields=[
                        *_AUDIT_FIELDS_COMMON,
                        "selected_slot_id",
                        "cancelled_assignment_ids",
                    ],
                    slot_choice_required=(
                        any(
                            str(action.get("action") or "").strip().lower() == REPAIR_ACTION_REBIND_ASSIGNMENT_SLOT
                            for action in allowed_actions
                        )
                    ),
                )
            ],
        )

    issue_codes = {str(issue.get("code") or "").strip().lower() for issue in issues}
    if issue_codes - {
        "scheduling_split_brain",
        "scheduling_status_conflict",
        "scheduling_assignment_slot_claimed_by_other_candidate",
    }:
        return _taxonomy_result(
            repairability=REPAIRABILITY_MANUAL_ONLY,
            repair_options=[],
            manual_repair_reasons=["unsupported_conflict_class"],
            conflict_classes=[
                _repair_conflict_class(
                    code="unsupported_conflict_class",
                    policy=REPAIRABILITY_MANUAL_ONLY,
                    label="Unsupported conflict class",
                    supported=False,
                    preconditions=[
                        "Scheduling issues do not match a supported repair taxonomy branch.",
                    ],
                    affected_entities=["slot_assignment", "slot"],
                    allowed_actions=[],
                    forbidden_resolutions=[
                        "hidden_autofix",
                        "best_effort_mutation",
                    ],
                    minimal_safe_result="operator_review_required",
                    required_audit_fields=[],
                )
            ],
        )

    if "scheduling_split_brain" in issue_codes and active_assignment_status not in {
        SlotAssignmentStatus.CONFIRMED,
        SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
    }:
        return _taxonomy_result(
            repairability=REPAIRABILITY_MANUAL_ONLY,
            repair_options=[],
            manual_repair_reasons=["transitional_split_brain"],
            conflict_classes=[
                _repair_conflict_class(
                    code="transitional_split_brain",
                    policy=REPAIRABILITY_MANUAL_ONLY,
                    label="Transitional split brain",
                    supported=False,
                    preconditions=[
                        "Split-brain exists while candidate confirmation or recruiter follow-up is still in flight.",
                    ],
                    affected_entities=["slot_assignment", "slot"],
                    allowed_actions=[],
                    forbidden_resolutions=[
                        "assignment_authoritative",
                        "status_rewrite_without_business_follow_up",
                    ],
                    minimal_safe_result="operator_review_required",
                    required_audit_fields=[],
                )
            ],
        )

    active_slots = [
        slot
        for slot in slots
        if _normalize_slot_status(getattr(slot, "status", None)) in ACTIVE_SLOT_STATUSES
        and getattr(slot, "id", None) != getattr(assignment_slot, "id", None)
    ]
    assignment_purpose = str(getattr(assignment_slot, "purpose", None) or "interview").strip().lower()
    for slot in active_slots:
        slot_purpose = str(getattr(slot, "purpose", None) or "interview").strip().lower()
        if slot_purpose != assignment_purpose:
            return _taxonomy_result(
                repairability=REPAIRABILITY_MANUAL_ONLY,
                repair_options=[],
                manual_repair_reasons=["cross_purpose_active_slot"],
                conflict_classes=[
                    _repair_conflict_class(
                        code="cross_purpose_active_slot",
                        policy=REPAIRABILITY_MANUAL_ONLY,
                        label="Cross-purpose active slot conflict",
                        supported=False,
                        preconditions=[
                            "A stale active Slot exists for the same candidate but for another scheduling purpose.",
                        ],
                        affected_entities=["slot", "slot_assignment"],
                        allowed_actions=[],
                        forbidden_resolutions=[
                            "assignment_authoritative",
                            "detach_cross_purpose_slot_without_operator_review",
                        ],
                        minimal_safe_result="operator_review_required",
                        required_audit_fields=[],
                    )
                ],
            )
        if getattr(slot, "recruiter_id", None) != getattr(active_assignment, "recruiter_id", None):
            return _taxonomy_result(
                repairability=REPAIRABILITY_MANUAL_ONLY,
                repair_options=[],
                manual_repair_reasons=["cross_recruiter_active_slot"],
                conflict_classes=[
                    _repair_conflict_class(
                        code="cross_recruiter_active_slot",
                        policy=REPAIRABILITY_MANUAL_ONLY,
                        label="Cross-owner active slot conflict",
                        supported=False,
                        preconditions=[
                            "A stale active Slot belongs to another recruiter owner.",
                        ],
                        affected_entities=["slot", "slot_assignment"],
                        allowed_actions=[],
                        forbidden_resolutions=[
                            "assignment_authoritative",
                            "detach_cross_owner_slot_without_coordination",
                        ],
                        minimal_safe_result="operator_review_required",
                        required_audit_fields=[],
                        owner_choice_required=True,
                    )
                ],
            )
        slot_assignments_count = sum(
            1
            for assignment in slot_assignments
            if getattr(assignment, "id", None) != getattr(active_assignment, "id", None)
            and getattr(assignment, "slot_id", None) == getattr(slot, "id", None)
            and _normalize_assignment_status(getattr(assignment, "status", None)) in ACTIVE_ASSIGNMENT_STATUSES
        )
        if slot_assignments_count:
            return _taxonomy_result(
                repairability=REPAIRABILITY_MANUAL_ONLY,
                repair_options=[],
                manual_repair_reasons=["stale_slot_has_active_assignment"],
                conflict_classes=[
                    _repair_conflict_class(
                        code="stale_slot_has_active_assignment",
                        policy=REPAIRABILITY_MANUAL_ONLY,
                        label="Stale slot has active assignment",
                        supported=False,
                        preconditions=[
                            "A stale active Slot is still referenced by another active SlotAssignment.",
                        ],
                        affected_entities=["slot", "slot_assignment"],
                        allowed_actions=[],
                        forbidden_resolutions=[
                            "assignment_authoritative",
                            "detach_slot_with_competing_active_assignment",
                        ],
                        minimal_safe_result="operator_review_required",
                        required_audit_fields=[],
                        assignment_choice_required=True,
                    )
                ],
            )

    safe_outcome = "sync_assignment_slot"
    if active_slots:
        safe_outcome = "release_stale_slot_and_sync_assignment_slot"

    repair_option = _repair_action(
        action=REPAIR_ACTION_ASSIGNMENT_AUTHORITATIVE,
        label="Use SlotAssignment as source of truth",
        resolution_kind="controlled",
        safe_outcome=safe_outcome,
        audit_action="scheduling_repair.assignment_authoritative",
    )
    conflict_classes = [
        _repair_conflict_class(
            code=issue_code,
            policy=REPAIRABILITY_REPAIRABLE,
            label=(
                "Scheduling split brain"
                if issue_code == "scheduling_split_brain"
                else "Scheduling status conflict"
            ),
            supported=True,
            preconditions=[
                "Exactly one active SlotAssignment is the clear owner of the scheduling state.",
            ],
            affected_entities=["slot", "slot_assignment"],
            allowed_actions=[repair_option],
            forbidden_resolutions=[
                "hidden_autofix",
                "write_on_read",
            ],
            minimal_safe_result=safe_outcome,
            required_audit_fields=[
                *_AUDIT_FIELDS_COMMON,
                "released_slot_ids",
                "slot_status_before",
                "slot_status_after",
            ],
        )
        for issue_code in sorted(issue_codes)
    ]

    return _taxonomy_result(
        repairability=REPAIRABILITY_REPAIRABLE,
        repair_options=[repair_option],
        manual_repair_reasons=[],
        conflict_classes=conflict_classes,
    )


def build_scheduling_integrity_report(
    *,
    slots: Sequence[Slot],
    slot_assignments: Sequence[SlotAssignment],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    slot_by_id = {
        int(getattr(slot, "id")): slot
        for slot in slots
        if getattr(slot, "id", None) is not None
    }

    active_assignments = [
        assignment
        for assignment in slot_assignments
        if _normalize_assignment_status(getattr(assignment, "status", None))
        in ACTIVE_ASSIGNMENT_STATUSES
    ]
    active_assignments = sorted(
        active_assignments,
        key=lambda item: (
            _comparable_dt(
                getattr(item, "updated_at", None)
                or getattr(item, "created_at", None)
            ),
            getattr(item, "id", 0),
        ),
        reverse=True,
    )
    active_assignment = active_assignments[0] if active_assignments else None
    latest_assignment = _pick_latest_assignment(slot_assignments)
    active_slot_pool = list(slots)
    if active_assignment is not None:
        candidate_tg_ids = _known_candidate_tg_ids(slots, slot_assignments, active_assignment)
        candidate_id = getattr(active_assignment, "candidate_id", None)
        active_slot_pool = [
            slot
            for slot in slots
            if not _slot_claimed_by_other_candidate(
                slot,
                candidate_id=candidate_id,
                candidate_tg_ids=candidate_tg_ids,
            )
        ]
    active_slot = _pick_active_slot(active_slot_pool, now=current_time)

    issues: list[dict[str, Any]] = []
    if len(active_assignments) > 1:
        issues.append(
            _issue(
                code="scheduling_multiple_active_assignments",
                message="У кандидата найдено несколько активных SlotAssignment.",
                write_behavior=WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
            )
        )

    write_owner = "none"
    if active_assignment is not None:
        write_owner = "slot_assignment"
    elif active_slot is not None:
        write_owner = "slot"

    if active_assignment is not None:
        assignment_status = _normalize_assignment_status(getattr(active_assignment, "status", None))
        assignment_slot = getattr(active_assignment, "slot", None)
        assignment_slot_id = getattr(assignment_slot, "id", None) or getattr(active_assignment, "slot_id", None)
        if assignment_slot is None and assignment_slot_id is not None:
            assignment_slot = slot_by_id.get(int(assignment_slot_id))
        assignment_slot_status = _normalize_slot_status(
            getattr(assignment_slot, "status", None) if assignment_slot is not None else None
        )
        candidate_tg_ids = _known_candidate_tg_ids(slots, slot_assignments, active_assignment)
        candidate_id = getattr(active_assignment, "candidate_id", None)

        if assignment_slot is None:
            issues.append(
                _issue(
                    code="scheduling_assignment_slot_missing",
                    message="Активный SlotAssignment не указывает на существующий Slot.",
                    write_behavior=WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
                )
            )
        elif _slot_claimed_by_other_candidate(
            assignment_slot,
            candidate_id=candidate_id,
            candidate_tg_ids=candidate_tg_ids,
        ):
            issues.append(
                _issue(
                    code="scheduling_assignment_slot_claimed_by_other_candidate",
                    message="Активный SlotAssignment указывает на Slot другого кандидата.",
                    write_behavior=WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
                )
            )
        elif active_slot is not None and getattr(active_slot, "id", None) != getattr(assignment_slot, "id", None):
            if assignment_status in {
                SlotAssignmentStatus.OFFERED,
                SlotAssignmentStatus.RESCHEDULE_REQUESTED,
            }:
                issues.append(
                    _issue(
                        code="scheduling_split_brain",
                        message="Активный Slot удерживает старое время, а SlotAssignment уже указывает на другой интервал.",
                        write_behavior=WRITE_BEHAVIOR_ALLOW_WITH_WARNING,
                    )
                )
            else:
                issues.append(
                    _issue(
                        code="scheduling_split_brain",
                        message="Активный Slot и SlotAssignment указывают на разные интервалы.",
                        write_behavior=WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
                    )
                )
        else:
            allowed_slot_statuses = _ALLOWED_SLOT_STATUSES_BY_ASSIGNMENT.get(assignment_status or "", set())
            if assignment_slot_status is None:
                issues.append(
                    _issue(
                        code="scheduling_assignment_slot_missing",
                        message="Для активного SlotAssignment не удалось определить status связанного Slot.",
                        write_behavior=WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
                    )
                )
            elif allowed_slot_statuses and assignment_slot_status not in allowed_slot_statuses:
                behavior = (
                    WRITE_BEHAVIOR_ALLOW_WITH_WARNING
                    if assignment_status == SlotAssignmentStatus.OFFERED
                    and assignment_slot_status == SlotStatus.FREE
                    else WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR
                )
                issues.append(
                    _issue(
                        code="scheduling_status_conflict",
                        message="Legacy Slot status расходится с активным SlotAssignment status.",
                        write_behavior=behavior,
                    )
                )

    write_behavior = WRITE_BEHAVIOR_ALLOW
    if any(
        issue.get("write_behavior") == WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR
        for issue in issues
    ):
        write_behavior = WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR
    elif issues:
        write_behavior = WRITE_BEHAVIOR_ALLOW_WITH_WARNING

    if write_behavior == WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR:
        integrity_state = INTEGRITY_STATE_NEEDS_MANUAL_REPAIR
    elif issues:
        integrity_state = INTEGRITY_STATE_TRANSITIONAL_WARNING
    else:
        integrity_state = INTEGRITY_STATE_CONSISTENT

    report = {
        "active_slot": active_slot,
        "active_assignment": active_assignment,
        "latest_assignment": latest_assignment,
        "issues": issues,
        "integrity_state": integrity_state,
        "write_behavior": write_behavior,
        "write_owner": write_owner,
        "assignment_owned": active_assignment is not None,
        "slot_only_writes_allowed": (
            active_assignment is None
            and write_behavior == WRITE_BEHAVIOR_ALLOW
        ),
    }
    repair = build_scheduling_repair_taxonomy(
        slots=slots,
        slot_assignments=slot_assignments,
        integrity=report,
    )
    report.update(repair)
    return report


async def load_candidate_scheduling_integrity(session, candidate: User) -> dict[str, Any]:
    telegram_ids = {
        int(value)
        for value in (candidate.telegram_id, candidate.telegram_user_id)
        if value is not None
    }

    slot_filters = []
    if candidate.candidate_id:
        slot_filters.append(Slot.candidate_id == candidate.candidate_id)
    if telegram_ids:
        slot_filters.append(Slot.candidate_tg_id.in_(sorted(telegram_ids)))
    slots = (
        await session.execute(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(or_(*slot_filters) if slot_filters else false())
            .order_by(Slot.start_utc.desc(), Slot.id.desc())
        )
    ).scalars().all()

    assignment_filters = []
    if candidate.candidate_id:
        assignment_filters.append(SlotAssignment.candidate_id == candidate.candidate_id)
    if telegram_ids:
        assignment_filters.append(SlotAssignment.candidate_tg_id.in_(sorted(telegram_ids)))
    assignments = (
        await session.execute(
            select(SlotAssignment)
            .options(selectinload(SlotAssignment.slot))
            .where(or_(*assignment_filters) if assignment_filters else false())
            .order_by(SlotAssignment.updated_at.desc(), SlotAssignment.id.desc())
        )
    ).scalars().all()

    report = build_scheduling_integrity_report(
        slots=slots,
        slot_assignments=assignments,
    )
    report["slots"] = list(slots)
    report["slot_assignments"] = list(assignments)
    return report


__all__ = [
    "ACTIVE_ASSIGNMENT_STATUSES",
    "ACTIVE_SLOT_STATUSES",
    "INTEGRITY_STATE_CONSISTENT",
    "INTEGRITY_STATE_NEEDS_MANUAL_REPAIR",
    "INTEGRITY_STATE_TRANSITIONAL_WARNING",
    "REPAIRABILITY_MANUAL_ONLY",
    "REPAIRABILITY_NOT_NEEDED",
    "REPAIRABILITY_REPAIRABLE",
    "REPAIR_ACTION_ASSIGNMENT_AUTHORITATIVE",
    "REPAIR_ACTION_CANCEL_ACTIVE_ASSIGNMENT",
    "REPAIR_ACTION_REBIND_ASSIGNMENT_SLOT",
    "REPAIR_ACTION_RESOLVE_TO_ACTIVE_ASSIGNMENT",
    "WRITE_BEHAVIOR_ALLOW",
    "WRITE_BEHAVIOR_ALLOW_WITH_WARNING",
    "WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR",
    "build_scheduling_integrity_report",
    "build_scheduling_repair_taxonomy",
    "load_candidate_scheduling_integrity",
]
