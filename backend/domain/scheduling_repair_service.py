"""Explicit repair use cases for persisted scheduling conflicts."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.scheduling_integrity import (
    ACTIVE_ASSIGNMENT_STATUSES,
    ACTIVE_SLOT_STATUSES,
    REPAIRABILITY_REPAIRABLE,
    REPAIR_ACTION_ASSIGNMENT_AUTHORITATIVE,
    REPAIR_ACTION_CANCEL_ACTIVE_ASSIGNMENT,
    REPAIR_ACTION_REBIND_ASSIGNMENT_SLOT,
    REPAIR_ACTION_RESOLVE_TO_ACTIVE_ASSIGNMENT,
    WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
    build_scheduling_integrity_report,
)
from backend.domain.candidates.state_contract import build_scheduling_summary
from backend.domain.models import AuditLog, Slot, SlotAssignment, SlotAssignmentStatus, SlotStatus
from backend.domain.slot_assignment_service import ServiceResult

logger = logging.getLogger(__name__)

_SUPPORTED_REPAIR_ACTIONS = {
    REPAIR_ACTION_ASSIGNMENT_AUTHORITATIVE,
    REPAIR_ACTION_RESOLVE_TO_ACTIVE_ASSIGNMENT,
    REPAIR_ACTION_CANCEL_ACTIVE_ASSIGNMENT,
    REPAIR_ACTION_REBIND_ASSIGNMENT_SLOT,
}
_MANUAL_REPAIR_AUDIT_ACTION = "scheduling_repair.manual_resolution"


class _RepairAbort(Exception):
    def __init__(self, result: ServiceResult):
        super().__init__(result.message or result.status)
        self.result = result


@dataclass
class _RepairExecution:
    assignment: SlotAssignment
    assignment_slot: Optional[Slot]
    audit_action: str
    slot_status_before: Optional[str] = None
    released_slot_ids: list[int] = field(default_factory=list)
    cancelled_assignment_ids: list[int] = field(default_factory=list)
    selected_assignment_id: Optional[int] = None
    selected_slot_id: Optional[int] = None
    audit_changes: dict[str, Any] = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_assignment_status(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _normalize_slot_status(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


async def _resolve_candidate_for_assignment(session, assignment: SlotAssignment) -> User | None:
    candidate = None
    if assignment.candidate_id:
        candidate = await session.scalar(
            select(User).where(User.candidate_id == assignment.candidate_id)
        )
    if candidate is None and assignment.candidate_tg_id is not None:
        candidate = await session.scalar(
            select(User).where(
                or_(
                    User.telegram_id == assignment.candidate_tg_id,
                    User.telegram_user_id == assignment.candidate_tg_id,
                )
            )
        )
    return candidate


def _known_candidate_tg_ids(
    assignment: SlotAssignment,
    candidate: User | None,
) -> set[int]:
    ids: set[int] = set()
    for raw in (
        assignment.candidate_tg_id,
        getattr(candidate, "telegram_id", None),
        getattr(candidate, "telegram_user_id", None),
    ):
        if raw is None:
            continue
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


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


def _clear_slot_binding(slot: Slot) -> None:
    slot.status = SlotStatus.FREE
    slot.candidate_id = None
    slot.candidate_tg_id = None
    slot.candidate_fio = None
    slot.candidate_tz = None
    slot.candidate_city_id = None


def _bind_slot_to_assignment(
    slot: Slot,
    *,
    assignment: SlotAssignment,
    candidate: User | None,
    slot_status: str,
) -> None:
    slot.status = slot_status
    slot.candidate_id = assignment.candidate_id or slot.candidate_id
    slot.candidate_tg_id = assignment.candidate_tg_id
    if candidate is not None and getattr(candidate, "fio", None):
        slot.candidate_fio = candidate.fio
    slot.candidate_tz = assignment.candidate_tz or slot.candidate_tz or slot.tz_name
    slot.candidate_city_id = slot.candidate_city_id or slot.city_id


async def _load_repair_integrity(
    session,
    *,
    assignment: SlotAssignment,
    candidate: User | None,
) -> dict[str, Any]:
    candidate_tg_ids = _known_candidate_tg_ids(assignment, candidate)
    slot_filters = []
    if assignment.candidate_id:
        slot_filters.append(Slot.candidate_id == assignment.candidate_id)
    if candidate_tg_ids:
        slot_filters.append(Slot.candidate_tg_id.in_(sorted(candidate_tg_ids)))
    if getattr(assignment, "slot_id", None) is not None:
        slot_filters.append(Slot.id == assignment.slot_id)

    assignment_filters = [SlotAssignment.id == assignment.id]
    if assignment.candidate_id:
        assignment_filters.append(SlotAssignment.candidate_id == assignment.candidate_id)
    if candidate_tg_ids:
        assignment_filters.append(SlotAssignment.candidate_tg_id.in_(sorted(candidate_tg_ids)))

    slots = (
        await session.execute(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(or_(*slot_filters))
            .order_by(Slot.start_utc.desc(), Slot.id.desc())
            .with_for_update()
        )
    ).scalars().all()
    assignments = (
        await session.execute(
            select(SlotAssignment)
            .options(selectinload(SlotAssignment.slot))
            .where(or_(*assignment_filters))
            .order_by(SlotAssignment.updated_at.desc(), SlotAssignment.id.desc())
            .with_for_update()
        )
    ).scalars().all()

    report = build_scheduling_integrity_report(
        slots=slots,
        slot_assignments=assignments,
    )
    report["slots"] = list(slots)
    report["slot_assignments"] = list(assignments)
    return report


def _slot_by_id(slots: Sequence[Slot]) -> dict[int, Slot]:
    return {
        int(getattr(slot, "id")): slot
        for slot in slots
        if getattr(slot, "id", None) is not None
    }


def _slot_for_assignment(
    assignment: SlotAssignment,
    *,
    slot_by_id: dict[int, Slot],
) -> Slot | None:
    assignment_slot = getattr(assignment, "slot", None)
    if assignment_slot is None and getattr(assignment, "slot_id", None) is not None:
        assignment_slot = slot_by_id.get(int(assignment.slot_id))
    return assignment_slot


def _canonical_slot_status_for_assignment(
    assignment: SlotAssignment,
    slot: Slot,
) -> str:
    assignment_status = _normalize_assignment_status(getattr(assignment, "status", None))
    current_slot_status = _normalize_slot_status(getattr(slot, "status", None))
    if assignment_status == SlotAssignmentStatus.OFFERED:
        return SlotStatus.PENDING
    if assignment_status in {
        SlotAssignmentStatus.CONFIRMED,
        SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
    }:
        if current_slot_status == SlotStatus.CONFIRMED_BY_CANDIDATE:
            return SlotStatus.CONFIRMED_BY_CANDIDATE
        return SlotStatus.BOOKED
    raise _RepairAbort(
        ServiceResult(
            False,
            "repair_not_allowed",
            409,
            "Для этого статуса SlotAssignment repair path не поддерживается.",
        )
    )


def _issue_codes(report: dict[str, Any]) -> list[str]:
    return [
        str(issue.get("code") or "").strip().lower()
        for issue in (report.get("issues") or [])
        if str(issue.get("code") or "").strip()
    ]


def _candidate_filters(candidate: User) -> list[Any]:
    filters: list[Any] = []
    if candidate.candidate_id:
        filters.append(Slot.candidate_id == candidate.candidate_id)
    telegram_ids: set[int] = set()
    for raw in (candidate.telegram_id, candidate.telegram_user_id):
        if raw is None:
            continue
        try:
            telegram_ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    if telegram_ids:
        filters.append(Slot.candidate_tg_id.in_(sorted(telegram_ids)))
    return filters


def _candidate_assignment_filters(candidate: User) -> list[Any]:
    filters: list[Any] = []
    if candidate.candidate_id:
        filters.append(SlotAssignment.candidate_id == candidate.candidate_id)
    telegram_ids: set[int] = set()
    for raw in (candidate.telegram_id, candidate.telegram_user_id):
        if raw is None:
            continue
        try:
            telegram_ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    if telegram_ids:
        filters.append(SlotAssignment.candidate_tg_id.in_(sorted(telegram_ids)))
    return filters


async def repair_candidate_confirmed_offer_if_safe(
    candidate_id: int,
    *,
    performed_by_type: str,
    performed_by_id: Optional[int],
    note: Optional[str] = None,
) -> ServiceResult:
    """Promote legacy offered assignment after the candidate already confirmed.

    This is intentionally narrow: it only repairs the historical state where the
    Slot is already candidate-confirmed but the single active SlotAssignment was
    left in OFFERED. No slot ownership or time is changed.
    """

    try:
        async with async_session() as session:
            async with session.begin():
                candidate = await session.get(User, int(candidate_id), with_for_update=True)
                if candidate is None:
                    return ServiceResult(False, "candidate_not_found", 404, "Кандидат не найден.")

                slot_filters = _candidate_filters(candidate)
                assignment_filters = _candidate_assignment_filters(candidate)
                if not slot_filters or not assignment_filters:
                    return ServiceResult(
                        True,
                        "not_applicable",
                        200,
                        "Для кандидата нет scheduling identity для legacy repair.",
                    )

                slots = (
                    await session.execute(
                        select(Slot)
                        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                        .where(or_(*slot_filters))
                        .order_by(Slot.start_utc.desc(), Slot.id.desc())
                        .with_for_update()
                    )
                ).scalars().all()
                assignments = (
                    await session.execute(
                        select(SlotAssignment)
                        .options(selectinload(SlotAssignment.slot))
                        .where(or_(*assignment_filters))
                        .order_by(SlotAssignment.updated_at.desc(), SlotAssignment.id.desc())
                        .with_for_update()
                    )
                ).scalars().all()

                integrity = build_scheduling_integrity_report(
                    slots=slots,
                    slot_assignments=assignments,
                )
                issue_codes = _issue_codes(integrity)
                if issue_codes != ["scheduling_status_conflict"]:
                    return ServiceResult(
                        True,
                        "not_applicable",
                        200,
                        "Legacy repair не применим к текущему scheduling state.",
                        payload={"issue_codes": issue_codes},
                    )

                assignment = integrity.get("active_assignment")
                slot = integrity.get("active_slot")
                slot_by_id = _slot_by_id(slots)
                if assignment is None or slot is None:
                    return ServiceResult(True, "not_applicable", 200, "Нет активной пары Slot/SlotAssignment.")
                assignment_slot = _slot_for_assignment(assignment, slot_by_id=slot_by_id)
                if assignment_slot is None or getattr(assignment_slot, "id", None) != getattr(slot, "id", None):
                    return ServiceResult(
                        True,
                        "not_applicable",
                        200,
                        "Legacy repair не меняет split-brain между разными слотами.",
                    )
                if _normalize_assignment_status(getattr(assignment, "status", None)) != SlotAssignmentStatus.OFFERED:
                    return ServiceResult(True, "not_applicable", 200, "Assignment уже не в offered.")
                if _normalize_slot_status(getattr(slot, "status", None)) not in {
                    SlotStatus.CONFIRMED,
                    SlotStatus.CONFIRMED_BY_CANDIDATE,
                }:
                    return ServiceResult(True, "not_applicable", 200, "Slot ещё не подтверждён кандидатом.")

                assignment.status = SlotAssignmentStatus.CONFIRMED
                assignment.confirmed_at = assignment.confirmed_at or _now()
                await session.flush()

                post_integrity = build_scheduling_integrity_report(
                    slots=slots,
                    slot_assignments=assignments,
                )
                if post_integrity.get("write_behavior") == WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR:
                    raise _RepairAbort(
                        ServiceResult(
                            False,
                            "repair_failed",
                            409,
                            "Legacy repair не снял scheduling conflict.",
                            payload={"issue_codes_before": issue_codes, "issue_codes_after": _issue_codes(post_integrity)},
                        )
                    )

                session.add(
                    AuditLog(
                        username=f"{performed_by_type}:{performed_by_id if performed_by_id is not None else 0}",
                        action="scheduling_repair.legacy_candidate_confirmed_offer",
                        entity_type="slot_assignment",
                        entity_id=str(assignment.id),
                        created_at=_now(),
                        changes={
                            "performed_by_type": performed_by_type,
                            "performed_by_id": performed_by_id,
                            "candidate_row_id": int(candidate.id),
                            "slot_id": int(slot.id),
                            "slot_status": _normalize_slot_status(getattr(slot, "status", None)),
                            "assignment_status_before": SlotAssignmentStatus.OFFERED,
                            "assignment_status_after": SlotAssignmentStatus.CONFIRMED,
                            "issue_codes_before": issue_codes,
                            "issue_codes_after": _issue_codes(post_integrity),
                            "note": str(note or "").strip() or None,
                        },
                    )
                )
                return ServiceResult(
                    True,
                    "repaired",
                    200,
                    "Legacy scheduling state repaired.",
                    payload={
                        "slot_id": int(slot.id),
                        "slot_assignment_id": int(assignment.id),
                        "integrity_state": post_integrity.get("integrity_state"),
                    },
                )
    except _RepairAbort as exc:
        return exc.result
    except Exception:  # noqa: BLE001 - repair path must fail closed with context
        logger.exception(
            "legacy_candidate_confirmed_offer_repair_failed",
            extra={"candidate_id": candidate_id},
        )
        return ServiceResult(
            False,
            "repair_failed",
            500,
            "Не удалось выполнить legacy scheduling repair.",
        )


def _workflow(integrity: dict[str, Any]) -> dict[str, Any]:
    return dict(integrity.get("repair_workflow") or {})


def _allowed_action_map(integrity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    allowed: dict[str, dict[str, Any]] = {}
    for action in _workflow(integrity).get("allowed_actions") or []:
        if not isinstance(action, dict):
            continue
        key = str(action.get("action") or "").strip().lower()
        if key:
            allowed[key] = dict(action)
    return allowed


def _failure_payload(
    integrity: dict[str, Any],
    *,
    code: str,
    message: str,
) -> dict[str, Any]:
    workflow = _workflow(integrity)
    return {
        "repair_workflow": workflow,
        "failure_reason": {
            "code": code,
            "message": message,
            "conflict_class": workflow.get("conflict_class"),
            "conflict_classes": list(workflow.get("conflict_classes") or []),
            "allowed_actions": list(workflow.get("allowed_actions") or []),
            "required_confirmations": list(workflow.get("required_confirmations") or []),
        },
    }


def _abort_with_integrity(
    integrity: dict[str, Any],
    *,
    status: str,
    status_code: int,
    message: str,
    failure_code: Optional[str] = None,
) -> None:
    raise _RepairAbort(
        ServiceResult(
            False,
            status,
            status_code,
            message,
            payload=_failure_payload(
                integrity,
                code=failure_code or status,
                message=message,
            ),
        )
    )


def _normalize_confirmation_set(confirmations: Sequence[str] | None) -> set[str]:
    return {
        str(value or "").strip().lower()
        for value in (confirmations or [])
        if str(value or "").strip()
    }


def _require_confirmations(
    *,
    integrity: dict[str, Any],
    action_meta: dict[str, Any],
    confirmations: Sequence[str] | None,
) -> None:
    required = {
        str(value or "").strip().lower()
        for value in (action_meta.get("required_confirmations") or [])
        if str(value or "").strip()
    }
    if not required:
        return
    provided = _normalize_confirmation_set(confirmations)
    missing = sorted(required - provided)
    if missing:
        _abort_with_integrity(
            integrity,
            status="missing_required_confirmations",
            status_code=400,
            message="Для выбранного repair action не хватает обязательных подтверждений оператора.",
            failure_code="missing_required_confirmations",
        )


async def _active_other_assignments_count(
    session,
    *,
    slot_id: int,
    current_assignment_id: Optional[int] = None,
) -> int:
    query = (
        select(func.count())
        .select_from(SlotAssignment)
        .where(
            SlotAssignment.slot_id == slot_id,
            SlotAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        )
    )
    if current_assignment_id is not None:
        query = query.where(SlotAssignment.id != current_assignment_id)
    count = await session.scalar(query)
    return int(count or 0)


async def _execute_assignment_authoritative(
    session,
    *,
    assignment: SlotAssignment,
    candidate: User | None,
    integrity: dict[str, Any],
) -> _RepairExecution:
    repairability = str(integrity.get("repairability") or "").strip().lower()
    if repairability != REPAIRABILITY_REPAIRABLE:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Этот persisted scheduling conflict нельзя безопасно восстановить автоматически.",
        )

    active_assignment = integrity.get("active_assignment")
    if getattr(active_assignment, "id", None) != assignment.id:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Controlled repair разрешён только для активного SlotAssignment owner.",
        )

    slots = list(integrity.get("slots") or [])
    slot_by_id = _slot_by_id(slots)
    assignment_slot = _slot_for_assignment(assignment, slot_by_id=slot_by_id)
    if assignment_slot is None:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Не удалось загрузить Slot для controlled repair.",
            failure_code="assignment_slot_missing",
        )

    candidate_tg_ids = _known_candidate_tg_ids(assignment, candidate)
    if _slot_claimed_by_other_candidate(
        assignment_slot,
        candidate_id=assignment.candidate_id,
        candidate_tg_ids=candidate_tg_ids,
    ):
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Целевой Slot уже занят другим кандидатом. Нужен manual repair.",
            failure_code="assignment_slot_claimed_by_other_candidate",
        )

    released_slot_ids: list[int] = []
    for slot in slots:
        if getattr(slot, "id", None) == getattr(assignment_slot, "id", None):
            continue
        if _normalize_slot_status(getattr(slot, "status", None)) not in ACTIVE_SLOT_STATUSES:
            continue
        other_active_assignments = await _active_other_assignments_count(
            session,
            slot_id=int(slot.id),
            current_assignment_id=int(assignment.id),
        )
        if other_active_assignments:
            _abort_with_integrity(
                integrity,
                status="repair_not_allowed",
                status_code=409,
                message="Stale Slot связан с другим активным SlotAssignment. Нужен manual repair.",
                failure_code="stale_slot_has_active_assignment",
            )
        _clear_slot_binding(slot)
        released_slot_ids.append(int(slot.id))

    slot_status_before = _normalize_slot_status(getattr(assignment_slot, "status", None))
    _bind_slot_to_assignment(
        assignment_slot,
        assignment=assignment,
        candidate=candidate,
        slot_status=_canonical_slot_status_for_assignment(assignment, assignment_slot),
    )
    if (
        _normalize_assignment_status(getattr(assignment, "status", None))
        in {
            SlotAssignmentStatus.CONFIRMED,
            SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
        }
        and assignment.confirmed_at is None
    ):
        assignment.confirmed_at = _now()

    return _RepairExecution(
        assignment=assignment,
        assignment_slot=assignment_slot,
        audit_action="scheduling_repair.assignment_authoritative",
        slot_status_before=slot_status_before,
        released_slot_ids=released_slot_ids,
    )


async def _execute_resolve_to_active_assignment(
    session,
    *,
    assignment: SlotAssignment,
    chosen_assignment_id: Optional[int],
    candidate: User | None,
    integrity: dict[str, Any],
) -> _RepairExecution:
    if chosen_assignment_id is None:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=400,
            message="Для resolve_to_active_assignment нужен выбранный active assignment.",
            failure_code="assignment_choice_required",
        )

    assignments = list(integrity.get("slot_assignments") or [])
    active_assignments = [
        current
        for current in assignments
        if _normalize_assignment_status(getattr(current, "status", None)) in ACTIVE_ASSIGNMENT_STATUSES
    ]
    chosen_assignment = next(
        (current for current in active_assignments if getattr(current, "id", None) == chosen_assignment_id),
        None,
    )
    if chosen_assignment is None:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Выбранный SlotAssignment недоступен для manual repair.",
            failure_code="selected_assignment_not_available",
        )

    slot_by_id = _slot_by_id(list(integrity.get("slots") or []))
    recruiter_ids = {
        getattr(current, "recruiter_id", None)
        for current in active_assignments
    }
    assignment_purposes: set[str] = set()
    candidate_tg_ids = _known_candidate_tg_ids(assignment, candidate)
    for current in active_assignments:
        current_slot = _slot_for_assignment(current, slot_by_id=slot_by_id)
        if current_slot is None:
            _abort_with_integrity(
                integrity,
                status="repair_not_allowed",
                status_code=409,
                message="Нельзя свести несколько активных назначений: один из SlotAssignment не имеет валидного Slot.",
                failure_code="assignment_slot_missing",
            )
        assignment_purposes.add(
            str(getattr(current_slot, "purpose", None) or "interview").strip().lower()
        )
    if len(recruiter_ids) != 1 or len(assignment_purposes) != 1:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Нельзя свести конфликт: активные SlotAssignment относятся к разным owner/purpose.",
            failure_code="cross_owner_conflict",
        )

    chosen_slot = _slot_for_assignment(chosen_assignment, slot_by_id=slot_by_id)
    if chosen_slot is None:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Выбранный SlotAssignment не связан с валидным Slot.",
            failure_code="assignment_slot_missing",
        )
    if _slot_claimed_by_other_candidate(
        chosen_slot,
        candidate_id=chosen_assignment.candidate_id,
        candidate_tg_ids=candidate_tg_ids,
    ):
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Выбранный SlotAssignment указывает на Slot другого кандидата.",
            failure_code="assignment_slot_claimed_by_other_candidate",
        )

    cancelled_assignment_ids: list[int] = []
    cancelled_slots: list[Slot] = []
    for current in active_assignments:
        if current.id == chosen_assignment.id:
            continue
        current.status = SlotAssignmentStatus.CANCELLED
        current.cancelled_at = _now()
        cancelled_assignment_ids.append(int(current.id))
        current_slot = _slot_for_assignment(current, slot_by_id=slot_by_id)
        if current_slot is not None:
            cancelled_slots.append(current_slot)

    await session.flush()

    released_slot_ids: list[int] = []
    for slot in cancelled_slots:
        if getattr(slot, "id", None) == getattr(chosen_slot, "id", None):
            continue
        if _normalize_slot_status(getattr(slot, "status", None)) not in ACTIVE_SLOT_STATUSES:
            continue
        if _slot_claimed_by_other_candidate(
            slot,
            candidate_id=chosen_assignment.candidate_id,
            candidate_tg_ids=candidate_tg_ids,
        ):
            continue
        if await _active_other_assignments_count(session, slot_id=int(slot.id)) != 0:
            continue
        _clear_slot_binding(slot)
        released_slot_ids.append(int(slot.id))

    slot_status_before = _normalize_slot_status(getattr(chosen_slot, "status", None))
    _bind_slot_to_assignment(
        chosen_slot,
        assignment=chosen_assignment,
        candidate=candidate,
        slot_status=_canonical_slot_status_for_assignment(chosen_assignment, chosen_slot),
    )
    if (
        _normalize_assignment_status(getattr(chosen_assignment, "status", None))
        in {
            SlotAssignmentStatus.CONFIRMED,
            SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
        }
        and chosen_assignment.confirmed_at is None
    ):
        chosen_assignment.confirmed_at = _now()

    return _RepairExecution(
        assignment=chosen_assignment,
        assignment_slot=chosen_slot,
        audit_action=_MANUAL_REPAIR_AUDIT_ACTION,
        slot_status_before=slot_status_before,
        released_slot_ids=released_slot_ids,
        cancelled_assignment_ids=cancelled_assignment_ids,
        selected_assignment_id=int(chosen_assignment.id),
        audit_changes={
            "anchor_assignment_id": int(assignment.id),
        },
    )


async def _execute_cancel_active_assignment(
    session,
    *,
    assignment: SlotAssignment,
    chosen_assignment_id: Optional[int],
    candidate: User | None,
    integrity: dict[str, Any],
) -> _RepairExecution:
    active_assignment = integrity.get("active_assignment")
    target_assignment = active_assignment
    if chosen_assignment_id is not None and getattr(active_assignment, "id", None) != chosen_assignment_id:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Для этого repair action доступен только активный SlotAssignment owner.",
            failure_code="selected_assignment_not_available",
        )
    if target_assignment is None:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Активный SlotAssignment для отмены не найден.",
            failure_code="no_active_assignment_owner",
        )

    slot_by_id = _slot_by_id(list(integrity.get("slots") or []))
    target_slot = _slot_for_assignment(target_assignment, slot_by_id=slot_by_id)
    candidate_tg_ids = _known_candidate_tg_ids(target_assignment, candidate)

    slot_status_before = _normalize_slot_status(getattr(target_slot, "status", None))
    target_assignment.status = SlotAssignmentStatus.CANCELLED
    target_assignment.cancelled_at = _now()
    await session.flush()

    released_slot_ids: list[int] = []
    if (
        target_slot is not None
        and _normalize_slot_status(getattr(target_slot, "status", None)) in ACTIVE_SLOT_STATUSES
        and not _slot_claimed_by_other_candidate(
            target_slot,
            candidate_id=target_assignment.candidate_id,
            candidate_tg_ids=candidate_tg_ids,
        )
        and await _active_other_assignments_count(session, slot_id=int(target_slot.id)) == 0
    ):
        _clear_slot_binding(target_slot)
        released_slot_ids.append(int(target_slot.id))

    return _RepairExecution(
        assignment=target_assignment,
        assignment_slot=target_slot,
        audit_action=_MANUAL_REPAIR_AUDIT_ACTION,
        slot_status_before=slot_status_before,
        released_slot_ids=released_slot_ids,
        cancelled_assignment_ids=[int(target_assignment.id)],
        selected_assignment_id=int(target_assignment.id),
    )


async def _execute_rebind_assignment_slot(
    session,
    *,
    assignment: SlotAssignment,
    chosen_assignment_id: Optional[int],
    chosen_slot_id: Optional[int],
    candidate: User | None,
    integrity: dict[str, Any],
) -> _RepairExecution:
    if chosen_slot_id is None:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=400,
            message="Для rebind_assignment_slot нужно явно выбрать Slot.",
            failure_code="slot_choice_required",
        )

    active_assignment = integrity.get("active_assignment")
    target_assignment = active_assignment
    if chosen_assignment_id is not None and getattr(active_assignment, "id", None) != chosen_assignment_id:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Для этого repair action доступен только активный SlotAssignment owner.",
            failure_code="selected_assignment_not_available",
        )
    if target_assignment is None:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Активный SlotAssignment для rebind не найден.",
            failure_code="no_active_assignment_owner",
        )

    slot_by_id = _slot_by_id(list(integrity.get("slots") or []))
    target_slot = slot_by_id.get(int(chosen_slot_id))
    if target_slot is None:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=404,
            message="Выбранный Slot недоступен для repair workflow.",
            failure_code="selected_slot_not_available",
        )

    candidate_tg_ids = _known_candidate_tg_ids(target_assignment, candidate)
    if _normalize_slot_status(getattr(target_slot, "status", None)) not in ACTIVE_SLOT_STATUSES:
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Выбранный Slot не находится в активном candidate-held состоянии.",
            failure_code="selected_slot_not_active",
        )
    if _slot_claimed_by_other_candidate(
        target_slot,
        candidate_id=target_assignment.candidate_id,
        candidate_tg_ids=candidate_tg_ids,
    ):
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Выбранный Slot уже принадлежит другому кандидату.",
            failure_code="assignment_slot_claimed_by_other_candidate",
        )
    if getattr(target_slot, "recruiter_id", None) != getattr(target_assignment, "recruiter_id", None):
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Нельзя rebind SlotAssignment к Slot другого owner.",
            failure_code="cross_owner_conflict",
        )
    if await _active_other_assignments_count(
        session,
        slot_id=int(target_slot.id),
        current_assignment_id=int(target_assignment.id),
    ):
        _abort_with_integrity(
            integrity,
            status="repair_not_allowed",
            status_code=409,
            message="Выбранный Slot уже удерживается другим активным SlotAssignment.",
            failure_code="stale_slot_has_active_assignment",
        )

    slot_status_before = _normalize_slot_status(getattr(target_slot, "status", None))
    target_assignment.slot_id = int(target_slot.id)
    target_assignment.slot = target_slot
    _bind_slot_to_assignment(
        target_slot,
        assignment=target_assignment,
        candidate=candidate,
        slot_status=_canonical_slot_status_for_assignment(target_assignment, target_slot),
    )
    if (
        _normalize_assignment_status(getattr(target_assignment, "status", None))
        in {
            SlotAssignmentStatus.CONFIRMED,
            SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
        }
        and target_assignment.confirmed_at is None
    ):
        target_assignment.confirmed_at = _now()

    return _RepairExecution(
        assignment=target_assignment,
        assignment_slot=target_slot,
        audit_action=_MANUAL_REPAIR_AUDIT_ACTION,
        slot_status_before=slot_status_before,
        selected_assignment_id=int(target_assignment.id),
        selected_slot_id=int(target_slot.id),
    )


def _build_success_payload(
    *,
    execution: _RepairExecution,
    integrity_before: dict[str, Any],
    post_integrity: dict[str, Any],
    confirmations: Sequence[str] | None,
    note: Optional[str],
) -> dict[str, Any]:
    scheduling_summary = build_scheduling_summary(
        slots=list(post_integrity.get("slots") or []),
        slot_assignments=list(post_integrity.get("slot_assignments") or []),
    )
    return {
        "slot_assignment_id": execution.assignment.id,
        "slot_id": execution.assignment.slot_id,
        "released_slot_ids": list(execution.released_slot_ids),
        "cancelled_assignment_ids": list(execution.cancelled_assignment_ids),
        "selected_assignment_id": execution.selected_assignment_id,
        "selected_slot_id": execution.selected_slot_id,
        "integrity_state": post_integrity.get("integrity_state"),
        "write_behavior": post_integrity.get("write_behavior"),
        "repairability": post_integrity.get("repairability"),
        "repair_options": post_integrity.get("repair_options") or [],
        "manual_repair_reasons": post_integrity.get("manual_repair_reasons") or [],
        "repair_workflow": post_integrity.get("repair_workflow") or {},
        "result_state": {
            "scheduling_summary": scheduling_summary,
            "integrity_state": post_integrity.get("integrity_state"),
            "write_behavior": post_integrity.get("write_behavior"),
            "repairability": post_integrity.get("repairability"),
        },
        "audit_metadata": {
            "action": execution.audit_action,
            "entity_type": "slot_assignment",
            "entity_id": str(execution.assignment.id),
            "performed_confirmations": sorted(_normalize_confirmation_set(confirmations)),
            "note_present": bool(str(note or "").strip()),
        },
        "failure_reason": None,
        "issue_codes_before": _issue_codes(integrity_before),
        "issue_codes_after": _issue_codes(post_integrity),
    }


async def repair_slot_assignment_scheduling_conflict(
    *,
    assignment_id: int,
    repair_action: str,
    performed_by_type: str,
    performed_by_id: int,
    chosen_assignment_id: Optional[int] = None,
    chosen_slot_id: Optional[int] = None,
    confirmations: Sequence[str] | None = None,
    note: Optional[str] = None,
) -> ServiceResult:
    normalized_action = str(repair_action or "").strip().lower()
    if normalized_action not in _SUPPORTED_REPAIR_ACTIONS:
        return ServiceResult(
            False,
            "unsupported_repair_action",
            400,
            "Неподдерживаемый repair action.",
            payload={
                "failure_reason": {
                    "code": "unsupported_repair_action",
                    "message": "Неподдерживаемый repair action.",
                    "allowed_actions": sorted(_SUPPORTED_REPAIR_ACTIONS),
                }
            },
        )

    try:
        async with async_session() as session:
            async with session.begin():
                assignment = await session.scalar(
                    select(SlotAssignment)
                    .options(selectinload(SlotAssignment.slot))
                    .where(SlotAssignment.id == assignment_id)
                    .with_for_update()
                )
                if assignment is None:
                    raise _RepairAbort(
                        ServiceResult(False, "not_found", 404, "Назначение не найдено.")
                    )

                candidate = await _resolve_candidate_for_assignment(session, assignment)
                integrity = await _load_repair_integrity(
                    session,
                    assignment=assignment,
                    candidate=candidate,
                )
                action_meta = _allowed_action_map(integrity).get(normalized_action)
                if action_meta is None:
                    _abort_with_integrity(
                        integrity,
                        status="repair_not_allowed",
                        status_code=409,
                        message="Для текущего conflict class выбранный repair action недоступен.",
                    )
                _require_confirmations(
                    integrity=integrity,
                    action_meta=action_meta,
                    confirmations=confirmations,
                )

                if normalized_action == REPAIR_ACTION_ASSIGNMENT_AUTHORITATIVE:
                    execution = await _execute_assignment_authoritative(
                        session,
                        assignment=assignment,
                        candidate=candidate,
                        integrity=integrity,
                    )
                elif normalized_action == REPAIR_ACTION_RESOLVE_TO_ACTIVE_ASSIGNMENT:
                    execution = await _execute_resolve_to_active_assignment(
                        session,
                        assignment=assignment,
                        chosen_assignment_id=chosen_assignment_id,
                        candidate=candidate,
                        integrity=integrity,
                    )
                elif normalized_action == REPAIR_ACTION_CANCEL_ACTIVE_ASSIGNMENT:
                    execution = await _execute_cancel_active_assignment(
                        session,
                        assignment=assignment,
                        chosen_assignment_id=chosen_assignment_id,
                        candidate=candidate,
                        integrity=integrity,
                    )
                else:
                    execution = await _execute_rebind_assignment_slot(
                        session,
                        assignment=assignment,
                        chosen_assignment_id=chosen_assignment_id,
                        chosen_slot_id=chosen_slot_id,
                        candidate=candidate,
                        integrity=integrity,
                    )

                await session.flush()

                post_integrity = build_scheduling_integrity_report(
                    slots=list(integrity.get("slots") or []),
                    slot_assignments=list(integrity.get("slot_assignments") or []),
                )
                post_integrity["slots"] = list(integrity.get("slots") or [])
                post_integrity["slot_assignments"] = list(integrity.get("slot_assignments") or [])
                if post_integrity.get("write_behavior") == WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR:
                    _abort_with_integrity(
                        integrity,
                        status="repair_failed",
                        status_code=409,
                        message="После repair workflow конфликт не был снят. Состояние оставлено без изменений.",
                        failure_code="repair_did_not_clear_conflict",
                    )

                session.add(
                    AuditLog(
                        username=f"{performed_by_type}:{performed_by_id}",
                        action=execution.audit_action,
                        entity_type="slot_assignment",
                        entity_id=str(execution.assignment.id),
                        created_at=_now(),
                        changes={
                            "performed_by_type": performed_by_type,
                            "performed_by_id": performed_by_id,
                            "repair_action": normalized_action,
                            "anchor_assignment_id": assignment.id,
                            "selected_assignment_id": execution.selected_assignment_id,
                            "selected_slot_id": execution.selected_slot_id,
                            "cancelled_assignment_ids": execution.cancelled_assignment_ids,
                            "released_slot_ids": execution.released_slot_ids,
                            "required_confirmations": sorted(_normalize_confirmation_set(confirmations)),
                            "issue_codes_before": _issue_codes(integrity),
                            "issue_codes_after": _issue_codes(post_integrity),
                            "slot_id": execution.assignment.slot_id,
                            "slot_status_before": execution.slot_status_before,
                            "slot_status_after": _normalize_slot_status(
                                getattr(execution.assignment_slot, "status", None)
                            ),
                            "write_behavior_after": post_integrity.get("write_behavior"),
                            "note": str(note or "").strip() or None,
                            **execution.audit_changes,
                        },
                    )
                )

                return ServiceResult(
                    True,
                    "repaired",
                    200,
                    payload=_build_success_payload(
                        execution=execution,
                        integrity_before=integrity,
                        post_integrity=post_integrity,
                        confirmations=confirmations,
                        note=note,
                    ),
                )
    except _RepairAbort as exc:
        return exc.result
    except Exception:
        logger.exception("scheduling_repair_failed", extra={"assignment_id": assignment_id})
        return ServiceResult(
            False,
            "repair_failed",
            500,
            "Не удалось выполнить scheduling repair workflow.",
            payload={
                "failure_reason": {
                    "code": "repair_failed",
                    "message": "Не удалось выполнить scheduling repair workflow.",
                }
            },
        )


__all__ = [
    "repair_candidate_confirmed_offer_if_safe",
    "repair_slot_assignment_scheduling_conflict",
]
