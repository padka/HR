from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy import func, or_, select

from backend.apps.admin_ui.security import Principal
from backend.apps.admin_ui.services.candidates.helpers import (
    get_candidate_detail,
    update_candidate_status,
)
from backend.apps.admin_ui.services.candidates.lifecycle_use_cases import (
    LifecycleUseCaseResult,
    execute_finalize_hired,
    execute_finalize_not_hired,
    execute_mark_test2_completed,
    execute_send_to_test2,
)
from backend.apps.admin_ui.services.slots import approve_slot_booking
from backend.core.db import async_session
from backend.domain.candidates.write_contract import (
    INTERVIEW_SCHEDULING_REQUIRED_COLUMNS,
    INTRO_DAY_SCHEDULING_REQUIRED_COLUMNS,
    SCHEDULING_SENSITIVE_ACTION_KEYS,
    is_supported_kanban_move_column,
    resolve_action_intent_key,
    resolve_action_target_status,
    resolve_kanban_move_intent,
    resolve_kanban_target_status,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import Slot, SlotStatus

BLOCKING_STATE_META: dict[str, dict[str, Any]] = {
    "scheduling_conflict": {
        "category": "scheduling",
        "severity": "warning",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": True,
    },
    "unsupported_kanban_move": {
        "category": "kanban_constraint",
        "severity": "error",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
    },
    "missing_interview_scheduling": {
        "category": "scheduling",
        "severity": "warning",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
    },
    "missing_intro_day_scheduling": {
        "category": "scheduling",
        "severity": "warning",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
    },
    "invalid_kanban_transition": {
        "category": "invariant",
        "severity": "error",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
    },
    "action_not_allowed": {
        "category": "invariant",
        "severity": "error",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
    },
    "invalid_transition": {
        "category": "invariant",
        "severity": "error",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
    },
    "test2_not_passed": {
        "category": "invariant",
        "severity": "error",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
    },
    "partial_transition_requires_repair": {
        "category": "reconciliation",
        "severity": "warning",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": True,
    },
}


def _action_field(action: object, key: str) -> Optional[object]:
    if isinstance(action, Mapping):
        return action.get(key)
    return getattr(action, key, None)


def _serialize_candidate_actions(candidate_id: int, candidate_actions: Sequence[object]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for action in candidate_actions:
        url_pattern = _action_field(action, "url_pattern")
        resolved_url = None
        if isinstance(url_pattern, str):
            resolved_url = url_pattern.replace("{id}", str(candidate_id))
        payload.append(
            {
                "key": _action_field(action, "key"),
                "label": _action_field(action, "label"),
                "url_pattern": url_pattern,
                "url": resolved_url,
                "icon": _action_field(action, "icon"),
                "variant": _action_field(action, "variant"),
                "method": _action_field(action, "method") or "GET",
                "target_status": _action_field(action, "target_status"),
                "confirmation": _action_field(action, "confirmation"),
                "requires_slot": bool(_action_field(action, "requires_slot")),
                "requires_test2_passed": bool(_action_field(action, "requires_test2_passed")),
            }
        )
    return payload


def _candidate_state_payload(detail: Mapping[str, Any]) -> dict[str, Any]:
    user = detail.get("user")
    candidate_id = getattr(user, "id", None)
    return {
        "id": candidate_id,
        "candidate_status_slug": detail.get("candidate_status_slug"),
        "candidate_status_display": detail.get("candidate_status_display"),
        "candidate_status_color": detail.get("candidate_status_color"),
        "lifecycle_summary": detail.get("lifecycle_summary"),
        "scheduling_summary": detail.get("scheduling_summary"),
        "candidate_next_action": detail.get("candidate_next_action"),
        "operational_summary": detail.get("operational_summary"),
        "state_reconciliation": detail.get("state_reconciliation"),
        "candidate_actions": _serialize_candidate_actions(
            int(candidate_id or 0),
            detail.get("candidate_actions", []) or [],
        ),
        "allowed_next_statuses": detail.get("allowed_next_statuses", []),
        "status_is_terminal": detail.get("status_is_terminal", False),
    }


def _candidate_issue_codes(candidate_state: Optional[Mapping[str, Any]]) -> list[str]:
    if not candidate_state:
        return []
    reconciliation = candidate_state.get("state_reconciliation") or {}
    issues = reconciliation.get("issues") or []
    seen: set[str] = set()
    codes: list[str] = []
    for issue in issues:
        if not isinstance(issue, Mapping):
            continue
        code = str(issue.get("code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def _blocking_state_payload(
    error: Optional[str],
    candidate_state: Optional[Mapping[str, Any]],
) -> Optional[dict[str, Any]]:
    normalized = str(error or "").strip().lower()
    if not normalized:
        return None
    meta = BLOCKING_STATE_META.get(normalized)
    if meta is None:
        return None
    return {
        "code": normalized,
        "category": meta["category"],
        "severity": meta["severity"],
        "retryable": meta["retryable"],
        "recoverable": meta["recoverable"],
        "manual_resolution_required": meta["manual_resolution_required"],
        "issue_codes": _candidate_issue_codes(candidate_state),
    }


def _has_issue(detail: Mapping[str, Any], issue_code: str) -> bool:
    reconciliation = detail.get("state_reconciliation") or {}
    issues = reconciliation.get("issues") or []
    normalized = str(issue_code or "").strip().lower()
    return any(str(issue.get("code") or "").strip().lower() == normalized for issue in issues)


def _has_scheduling_conflict(detail: Mapping[str, Any]) -> bool:
    operational_summary = detail.get("operational_summary") or {}
    if operational_summary.get("has_scheduling_conflict"):
        return True
    reconciliation = detail.get("state_reconciliation") or {}
    issues = reconciliation.get("issues") or []
    return any(
        str(issue.get("code") or "").strip().lower().startswith("scheduling_")
        for issue in issues
    )


def _has_active_scheduling(detail: Mapping[str, Any], stage: str) -> bool:
    scheduling_summary = detail.get("scheduling_summary") or {}
    return (
        bool(scheduling_summary.get("active"))
        and str(scheduling_summary.get("stage") or "").strip().lower() == stage
    )


def _allowed_next_status_slugs(detail: Mapping[str, Any]) -> set[str]:
    values = detail.get("allowed_next_statuses", []) or []
    slugs: set[str] = set()
    for item in values:
        if isinstance(item, Mapping):
            slug = str(item.get("slug") or "").strip().lower()
        else:
            slug = str(item or "").strip().lower()
        if slug:
            slugs.add(slug)
    return slugs


async def _refresh_candidate_state(candidate_id: int, principal: Optional[Principal]) -> Optional[dict[str, Any]]:
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return None
    return _candidate_state_payload(detail)


async def _find_pending_interview_slot_id(detail: Mapping[str, Any]) -> Optional[int]:
    user = detail.get("user")
    telegram_id = getattr(user, "telegram_id", None)
    candidate_uuid = getattr(user, "candidate_id", None)
    filters = []
    if candidate_uuid is not None:
        filters.append(Slot.candidate_id == candidate_uuid)
    if telegram_id is not None:
        filters.append(Slot.candidate_tg_id == telegram_id)
    if not filters:
        return None
    async with async_session() as session:
        pending_slot = await session.scalar(
            select(Slot)
            .where(
                or_(*filters),
                func.lower(Slot.status) == SlotStatus.PENDING,
                Slot.start_utc >= datetime.now(timezone.utc),
            )
            .order_by(Slot.start_utc.asc(), Slot.id.asc())
            .limit(1)
        )
    return getattr(pending_slot, "id", None)


@dataclass
class RecruiterWriteIntentResult:
    ok: bool
    message: str
    status_code: int
    error: Optional[str] = None
    status: Optional[str] = None
    action: Optional[str] = None
    candidate_id: Optional[int] = None
    dispatch: Optional[object] = None
    intent: Optional[dict[str, Any]] = None
    candidate_state: Optional[dict[str, Any]] = None
    blocking_state: Optional[dict[str, Any]] = None

    def as_payload(self) -> dict[str, Any]:
        payload = {
            "ok": self.ok,
            "message": self.message,
            "status": self.status,
            "action": self.action,
            "candidate_id": self.candidate_id,
            "error": self.error,
            "intent": self.intent,
            "candidate_state": self.candidate_state,
            "blocking_state": self.blocking_state,
        }
        return {key: value for key, value in payload.items() if value is not None}


def _from_lifecycle_use_case_result(
    result: LifecycleUseCaseResult,
    *,
    action: Optional[str] = None,
    candidate_id: Optional[int] = None,
    intent: Optional[dict[str, Any]] = None,
) -> RecruiterWriteIntentResult:
    candidate_state = _candidate_state_payload(result.detail) if result.detail else None
    blocking_state = _blocking_state_payload(result.error, candidate_state)
    return RecruiterWriteIntentResult(
        ok=result.ok,
        message=result.message,
        status_code=result.status_code,
        error=result.error,
        status=result.status,
        action=action,
        candidate_id=candidate_id,
        dispatch=result.dispatch,
        candidate_state=candidate_state,
        blocking_state=blocking_state,
        intent=intent,
    )


async def execute_candidate_action_intent(
    candidate_id: int,
    action_key: str,
    *,
    principal: Optional[Principal],
    bot_service: Optional[object],
    reason: Optional[str] = None,
    comment: Optional[str] = None,
) -> RecruiterWriteIntentResult:
    intent_key = resolve_action_intent_key(action_key)
    dedicated_targets = {
        "interview_outcome_passed": CandidateStatus.TEST2_SENT.value,
        "interview_passed": CandidateStatus.TEST2_SENT.value,
        "mark_hired": CandidateStatus.HIRED.value,
        "mark_not_hired": CandidateStatus.NOT_HIRED.value,
    }
    if action_key in {"interview_outcome_passed", "interview_passed"}:
        result = await execute_send_to_test2(
            candidate_id,
            principal=principal,
            bot_service=bot_service,
            action_key=action_key,
        )
        return _from_lifecycle_use_case_result(
            result,
            action=action_key,
            candidate_id=candidate_id,
            intent={
                "kind": "candidate_action",
                "action_key": action_key,
                "intent_key": intent_key,
                "resolved_status": dedicated_targets[action_key],
                "resolution": "dedicated_lifecycle_use_case",
            },
        )
    if action_key == "mark_hired":
        result = await execute_finalize_hired(
            candidate_id,
            principal=principal,
            action_key=action_key,
        )
        return _from_lifecycle_use_case_result(
            result,
            action=action_key,
            candidate_id=candidate_id,
            intent={
                "kind": "candidate_action",
                "action_key": action_key,
                "intent_key": intent_key,
                "resolved_status": dedicated_targets[action_key],
                "resolution": "dedicated_lifecycle_use_case",
            },
        )
    if action_key == "mark_not_hired":
        result = await execute_finalize_not_hired(
            candidate_id,
            principal=principal,
            reason=reason,
            comment=comment,
            action_key=action_key,
        )
        return _from_lifecycle_use_case_result(
            result,
            action=action_key,
            candidate_id=candidate_id,
            intent={
                "kind": "candidate_action",
                "action_key": action_key,
                "intent_key": intent_key,
                "resolved_status": dedicated_targets[action_key],
                "resolution": "dedicated_lifecycle_use_case",
            },
        )

    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return RecruiterWriteIntentResult(
            ok=False,
            message="Candidate not found",
            status_code=404,
            error="candidate_not_found",
            action=action_key,
            candidate_id=candidate_id,
        )

    candidate_state = _candidate_state_payload(detail)
    actions = detail.get("candidate_actions", []) or []
    action_def = next((action for action in actions if _action_field(action, "key") == action_key), None)
    if not action_def:
        return RecruiterWriteIntentResult(
            ok=False,
            message="Действие недоступно в текущем статусе",
            status_code=400,
            error="action_not_allowed",
            action=action_key,
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "candidate_action",
                "action_key": action_key,
                "intent_key": resolve_action_intent_key(action_key),
                "resolution": "current_state_validation",
            },
            blocking_state=_blocking_state_payload("action_not_allowed", candidate_state),
        )

    if action_key in SCHEDULING_SENSITIVE_ACTION_KEYS and _has_scheduling_conflict(detail):
        return RecruiterWriteIntentResult(
            ok=False,
            message="Нельзя выполнить действие: Slot и SlotAssignment расходятся. Сначала проверьте scheduling.",
            status_code=409,
            error="scheduling_conflict",
            action=action_key,
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "candidate_action",
                "action_key": action_key,
                "intent_key": intent_key,
                "resolution": "blocked_by_reconciliation",
            },
            blocking_state=_blocking_state_payload("scheduling_conflict", candidate_state),
        )

    if action_key == "approve_upcoming_slot":
        pending_slot_id = await _find_pending_interview_slot_id(detail)
        if pending_slot_id is None:
            return RecruiterWriteIntentResult(
                ok=False,
                message="Нет слотов, ожидающих подтверждения",
                status_code=400,
                error="pending_slot_not_found",
                action=action_key,
                candidate_id=candidate_id,
                candidate_state=candidate_state,
                intent={
                    "kind": "candidate_action",
                    "action_key": action_key,
                    "intent_key": intent_key,
                    "resolution": "slot_lookup",
                },
            )
        ok, message, _notified = await approve_slot_booking(pending_slot_id, principal=principal)
        refreshed_state = await _refresh_candidate_state(candidate_id, principal)
        return RecruiterWriteIntentResult(
            ok=ok,
            message=message,
            status_code=200 if ok else 400,
            error=None if ok else "approve_slot_failed",
            status=(refreshed_state or {}).get("candidate_status_slug"),
            action=action_key,
            candidate_id=candidate_id,
            candidate_state=refreshed_state,
            intent={
                "kind": "candidate_action",
                "action_key": action_key,
                "intent_key": intent_key,
                "resolved_status": (refreshed_state or {}).get("candidate_status_slug"),
                "resolution": "canonical_action",
            },
            blocking_state=None if ok else _blocking_state_payload("approve_slot_failed", refreshed_state),
        )

    target_status, resolution = resolve_action_target_status(
        action_key,
        current_status_slug=detail.get("candidate_status_slug"),
        fallback_target_status=_action_field(action_def, "target_status"),
    )
    if not target_status:
        return RecruiterWriteIntentResult(
            ok=False,
            message="Для действия не найден допустимый lifecycle transition",
            status_code=400,
            error="unresolved_action_transition",
            action=action_key,
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "candidate_action",
                "action_key": action_key,
                "intent_key": intent_key,
                "resolution": resolution,
            },
            blocking_state=_blocking_state_payload("unresolved_action_transition", candidate_state),
        )

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id,
        target_status,
        bot_service=bot_service,
        principal=principal,
        reason=reason,
        comment=comment,
    )
    refreshed_state = await _refresh_candidate_state(candidate_id, principal) if ok else candidate_state
    return RecruiterWriteIntentResult(
        ok=ok,
        message=message or "",
        status_code=200 if ok else 400,
        error=None if ok else "action_execution_failed",
        status=stored_status or target_status,
        action=action_key,
        candidate_id=candidate_id,
        dispatch=dispatch,
        candidate_state=refreshed_state,
        intent={
            "kind": "candidate_action",
            "action_key": action_key,
            "intent_key": intent_key,
            "resolved_status": target_status,
            "resolution": resolution,
        },
        blocking_state=None if ok else _blocking_state_payload("action_execution_failed", refreshed_state),
    )


async def execute_kanban_move_intent(
    candidate_id: int,
    *,
    target_column: str,
    principal: Optional[Principal],
    bot_service: Optional[object],
    compatibility_source: Optional[str] = None,
) -> RecruiterWriteIntentResult:
    normalized_column = str(target_column or "").strip().lower()
    if not normalized_column:
        return RecruiterWriteIntentResult(
            ok=False,
            message="Колонка канбана обязательна",
            status_code=400,
            error="missing_target_column",
            candidate_id=candidate_id,
        )

    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return RecruiterWriteIntentResult(
            ok=False,
            message="Кандидат не найден",
            status_code=404,
            error="candidate_not_found",
            candidate_id=candidate_id,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": resolve_kanban_move_intent(normalized_column),
            },
        )

    candidate_state = _candidate_state_payload(detail)
    current_column = str(
        ((detail.get("operational_summary") or {}).get("kanban_column") or "")
    ).strip().lower() or None
    intent_key = resolve_kanban_move_intent(normalized_column)
    resolved_status = resolve_kanban_target_status(normalized_column)
    current_status_slug = str(detail.get("candidate_status_slug") or "").strip().lower() or None

    if current_column == normalized_column and current_status_slug == resolved_status:
        return RecruiterWriteIntentResult(
            ok=True,
            message="Кандидат уже находится в выбранной колонке",
            status_code=200,
            status=detail.get("candidate_status_slug"),
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": intent_key,
                "resolved_status": resolved_status,
                "resolution": "no_op",
                "compatibility_source": compatibility_source,
            },
        )

    if not is_supported_kanban_move_column(normalized_column) or not resolved_status:
        return RecruiterWriteIntentResult(
            ok=False,
            message="Эта колонка не поддерживает прямой drag/drop переход. Используйте слот или явное действие.",
            status_code=409,
            error="unsupported_kanban_move",
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": intent_key,
                "resolved_status": resolved_status,
                "resolution": "unsupported_column",
                "compatibility_source": compatibility_source,
            },
            blocking_state=_blocking_state_payload("unsupported_kanban_move", candidate_state),
        )

    if normalized_column == "test2_sent":
        result = await execute_send_to_test2(
            candidate_id,
            principal=principal,
            bot_service=bot_service,
        )
        return _from_lifecycle_use_case_result(
            result,
            candidate_id=candidate_id,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": intent_key,
                "resolved_status": resolved_status,
                "resolution": "dedicated_lifecycle_use_case",
                "compatibility_source": compatibility_source,
            },
        )

    if normalized_column == "test2_completed":
        result = await execute_mark_test2_completed(
            candidate_id,
            principal=principal,
        )
        return _from_lifecycle_use_case_result(
            result,
            candidate_id=candidate_id,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": intent_key,
                "resolved_status": resolved_status,
                "resolution": "dedicated_lifecycle_use_case",
                "compatibility_source": compatibility_source,
            },
        )

    if _has_scheduling_conflict(detail):
        return RecruiterWriteIntentResult(
            ok=False,
            message="Нельзя двигать карточку: Slot и SlotAssignment расходятся. Нужна ручная проверка scheduling.",
            status_code=409,
            error="scheduling_conflict",
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": intent_key,
                "resolved_status": resolved_status,
                "resolution": "blocked_by_reconciliation",
                "compatibility_source": compatibility_source,
            },
            blocking_state=_blocking_state_payload("scheduling_conflict", candidate_state),
        )

    if normalized_column in INTERVIEW_SCHEDULING_REQUIRED_COLUMNS and not _has_active_scheduling(detail, "interview"):
        return RecruiterWriteIntentResult(
            ok=False,
            message="Для этого перехода нужно активное интервью в scheduling contract.",
            status_code=409,
            error="missing_interview_scheduling",
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": intent_key,
                "resolved_status": resolved_status,
                "resolution": "missing_scheduling_context",
                "compatibility_source": compatibility_source,
            },
            blocking_state=_blocking_state_payload("missing_interview_scheduling", candidate_state),
        )

    if normalized_column in INTRO_DAY_SCHEDULING_REQUIRED_COLUMNS and not _has_active_scheduling(detail, "intro_day"):
        return RecruiterWriteIntentResult(
            ok=False,
            message="Для этого перехода нужен активный ознакомительный день в scheduling contract.",
            status_code=409,
            error="missing_intro_day_scheduling",
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": intent_key,
                "resolved_status": resolved_status,
                "resolution": "missing_scheduling_context",
                "compatibility_source": compatibility_source,
            },
            blocking_state=_blocking_state_payload("missing_intro_day_scheduling", candidate_state),
        )

    allowed_next = _allowed_next_status_slugs(detail)
    current_status = str(detail.get("candidate_status_slug") or "").strip().lower() or None
    if current_status != resolved_status and resolved_status not in allowed_next:
        return RecruiterWriteIntentResult(
            ok=False,
            message="Переход недоступен для текущего состояния кандидата. Используйте доступное действие или scheduling flow.",
            status_code=409,
            error="invalid_kanban_transition",
            candidate_id=candidate_id,
            candidate_state=candidate_state,
            intent={
                "kind": "kanban_move",
                "target_column": normalized_column,
                "intent_key": intent_key,
                "resolved_status": resolved_status,
                "resolution": "transition_guard",
                "compatibility_source": compatibility_source,
            },
            blocking_state=_blocking_state_payload("invalid_kanban_transition", candidate_state),
        )

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id,
        resolved_status,
        bot_service=bot_service,
        principal=principal,
        reason=f"kanban move:{normalized_column}",
    )
    refreshed_state = await _refresh_candidate_state(candidate_id, principal) if ok else candidate_state
    return RecruiterWriteIntentResult(
        ok=ok,
        message=message or "",
        status_code=200 if ok else 400,
        error=None if ok else "kanban_move_failed",
        status=stored_status or resolved_status,
        candidate_id=candidate_id,
        dispatch=dispatch,
        candidate_state=refreshed_state,
        intent={
            "kind": "kanban_move",
            "target_column": normalized_column,
            "intent_key": intent_key,
            "resolved_status": resolved_status,
            "resolution": "canonical_column",
            "compatibility_source": compatibility_source,
        },
        blocking_state=None if ok else _blocking_state_payload("kanban_move_failed", refreshed_state),
    )
