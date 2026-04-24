from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from backend.domain.candidates.scheduling_integrity import (
    ACTIVE_SLOT_STATUSES,
    WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
    build_scheduling_integrity_report,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.workflow import (
    workflow_status_for_candidate_status,
    workflow_status_from_raw_value,
)
from backend.domain.models import Slot, SlotAssignment, SlotAssignmentStatus, SlotStatus

STATE_CONTRACT_VERSION = 1

RECORD_STATE_ACTIVE = "active"
RECORD_STATE_CLOSED = "closed"

LIFECYCLE_STAGE_LEAD = "lead"
LIFECYCLE_STAGE_SCREENING = "screening"
LIFECYCLE_STAGE_WAITING_INTERVIEW_SLOT = "waiting_interview_slot"
LIFECYCLE_STAGE_INTERVIEW = "interview"
LIFECYCLE_STAGE_TEST2 = "test2"
LIFECYCLE_STAGE_WAITING_INTRO_DAY = "waiting_intro_day"
LIFECYCLE_STAGE_INTRO_DAY = "intro_day"
LIFECYCLE_STAGE_CLOSED = "closed"

LIFECYCLE_STAGE_LABELS = {
    LIFECYCLE_STAGE_LEAD: "Лид",
    LIFECYCLE_STAGE_SCREENING: "Скрининг",
    LIFECYCLE_STAGE_WAITING_INTERVIEW_SLOT: "Ожидает слот на интервью",
    LIFECYCLE_STAGE_INTERVIEW: "Интервью",
    LIFECYCLE_STAGE_TEST2: "Тест 2",
    LIFECYCLE_STAGE_WAITING_INTRO_DAY: "Ожидает ознакомительный день",
    LIFECYCLE_STAGE_INTRO_DAY: "Ознакомительный день",
    LIFECYCLE_STAGE_CLOSED: "Закрыт",
}

FINAL_OUTCOME_HIRED = "hired"
FINAL_OUTCOME_NOT_HIRED = "not_hired"
FINAL_OUTCOME_NOT_COUNTED = "not_counted"

FINAL_OUTCOME_LABELS = {
    FINAL_OUTCOME_HIRED: "Нанят",
    FINAL_OUTCOME_NOT_HIRED: "Не нанят",
    FINAL_OUTCOME_NOT_COUNTED: "Не засчитан",
}

SCHEDULING_STAGE_INTERVIEW = "interview"
SCHEDULING_STAGE_INTRO_DAY = "intro_day"

SCHEDULING_STATUS_OFFERED = "offered"
SCHEDULING_STATUS_SELECTED = "selected"
SCHEDULING_STATUS_SCHEDULED = "scheduled"
SCHEDULING_STATUS_CONFIRMED = "confirmed"
SCHEDULING_STATUS_RESCHEDULE_REQUESTED = "reschedule_requested"
SCHEDULING_STATUS_CANCELLED = "cancelled"
SCHEDULING_STATUS_COMPLETED = "completed"
SCHEDULING_STATUS_NO_SHOW = "no_show"

SCHEDULING_STATUS_LABELS = {
    SCHEDULING_STATUS_OFFERED: "Предложен слот",
    SCHEDULING_STATUS_SELECTED: "Слот выбран",
    SCHEDULING_STATUS_SCHEDULED: "Интервью назначено",
    SCHEDULING_STATUS_CONFIRMED: "Участие подтверждено",
    SCHEDULING_STATUS_RESCHEDULE_REQUESTED: "Запрошен перенос",
    SCHEDULING_STATUS_CANCELLED: "Отменено",
    SCHEDULING_STATUS_COMPLETED: "Завершено",
    SCHEDULING_STATUS_NO_SHOW: "Неявка",
}

WORKLIST_BUCKET_LABELS = {
    "incoming": "Входящие",
    "today": "Сегодня",
    "awaiting_candidate": "Ждем кандидата",
    "awaiting_recruiter": "Ждет рекрутера",
    "blocked": "Требует разбор",
    "closed": "Закрыто",
}

KANBAN_COLUMN_LABELS = {
    "incoming": "Входящие",
    "slot_pending": "На согласовании",
    "interview_scheduled": "Назначено собеседование",
    "interview_confirmed": "Подтвердил собеседование",
    "test2_sent": "Отправлен тест 2",
    "test2_completed": "Прошел тест 2",
    "intro_day_scheduled": "Ознакомительный день назначен",
    "intro_day_confirmed_preliminary": "Предварительно подтвердил ОД",
    "intro_day_confirmed_day_of": "Подтвердил ОД",
}

KANBAN_COLUMN_ICONS = {
    "incoming": "📥",
    "slot_pending": "🕐",
    "interview_scheduled": "📅",
    "interview_confirmed": "✅",
    "test2_sent": "📨",
    "test2_completed": "🧪",
    "intro_day_scheduled": "📆",
    "intro_day_confirmed_preliminary": "👍",
    "intro_day_confirmed_day_of": "🎯",
}

KANBAN_COLUMN_TARGET_STATUSES = {
    "incoming": "waiting_slot",
    "slot_pending": "slot_pending",
    "interview_scheduled": "interview_scheduled",
    "interview_confirmed": "interview_confirmed",
    "test2_sent": "test2_sent",
    "test2_completed": "test2_completed",
    "intro_day_scheduled": "intro_day_scheduled",
    "intro_day_confirmed_preliminary": "intro_day_confirmed_preliminary",
    "intro_day_confirmed_day_of": "intro_day_confirmed_day_of",
}

KANBAN_PIPELINE_COLUMNS = {
    "main": [
        "incoming",
        "slot_pending",
        "interview_scheduled",
        "interview_confirmed",
        "test2_sent",
        "test2_completed",
        "intro_day_scheduled",
        "intro_day_confirmed_preliminary",
        "intro_day_confirmed_day_of",
    ],
    "interview": [
        "incoming",
        "slot_pending",
        "interview_scheduled",
        "interview_confirmed",
        "test2_sent",
    ],
    "intro_day": [
        "test2_completed",
        "intro_day_scheduled",
        "intro_day_confirmed_preliminary",
        "intro_day_confirmed_day_of",
    ],
}

QUEUE_STATE_LABELS = {
    "requested_other_time": "Запросил другое время",
    "awaiting_candidate_confirmation": "Ожидает подтверждения кандидата",
    "stalled_waiting_slot": "Долго ждет слот",
    "waiting_slot": "Ждет слот",
    "scheduled": "Назначена встреча",
    "waiting_candidate": "Ожидаем ответ кандидата",
    "waiting_recruiter": "Ждет решения рекрутера",
    "needs_attention": "Требует разбор",
    "closed": "Закрыт",
}

LEGACY_KANBAN_COLUMN_BY_STATUS = {
    CandidateStatus.LEAD.value: "incoming",
    CandidateStatus.CONTACTED.value: "incoming",
    CandidateStatus.INVITED.value: "incoming",
    CandidateStatus.TEST1_COMPLETED.value: "incoming",
    CandidateStatus.WAITING_SLOT.value: "incoming",
    CandidateStatus.STALLED_WAITING_SLOT.value: "incoming",
    CandidateStatus.SLOT_PENDING.value: "slot_pending",
    CandidateStatus.INTERVIEW_SCHEDULED.value: "interview_scheduled",
    CandidateStatus.INTERVIEW_CONFIRMED.value: "interview_confirmed",
    CandidateStatus.TEST2_SENT.value: "test2_sent",
    CandidateStatus.TEST2_COMPLETED.value: "test2_completed",
    CandidateStatus.INTRO_DAY_SCHEDULED.value: "intro_day_scheduled",
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY.value: "intro_day_confirmed_preliminary",
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF.value: "intro_day_confirmed_day_of",
}

TERMINAL_STATUS_SLUGS = {
    CandidateStatus.INTERVIEW_DECLINED.value,
    CandidateStatus.TEST2_FAILED.value,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION.value,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF.value,
    CandidateStatus.HIRED.value,
    CandidateStatus.NOT_HIRED.value,
}

ACTION_PRIORITY = (
    "approve_upcoming_slot",
    "schedule_interview",
    "reschedule_interview",
    "interview_outcome_passed",
    "interview_passed",
    "resend_test2",
    "schedule_intro_day",
    "reschedule_intro_day",
    "mark_hired",
    "mark_not_hired",
    "decline_after_intro",
    "invite_bot",
    "contact",
)

ACTION_TYPE_BY_KEY = {
    "contact": "contact_candidate",
    "invite_bot": "invite_to_portal",
    "schedule_interview": "offer_interview_slot",
    "reschedule_interview": "resolve_reschedule",
    "approve_upcoming_slot": "approve_selected_slot",
    "interview_outcome_passed": "send_test2",
    "interview_passed": "send_test2",
    "resend_test2": "send_test2",
    "schedule_intro_day": "schedule_intro_day",
    "reschedule_intro_day": "confirm_intro_day",
    "mark_hired": "finalize_hired",
    "mark_not_hired": "finalize_not_hired",
    "decline_after_intro": "finalize_not_hired",
}

UI_ACTION_BY_KEY = {
    "schedule_interview": "open_schedule_slot_modal",
    "reschedule_interview": "open_schedule_slot_modal",
    "schedule_intro_day": "open_schedule_intro_day_modal",
    "reschedule_intro_day": "open_schedule_intro_day_modal",
    "contact": "open_chat",
}


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_utc_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _status_slug(value: Any) -> Optional[str]:
    if isinstance(value, CandidateStatus):
        return value.value
    normalized = str(value or "").strip().lower()
    return normalized or None


def _normalize_final_outcome(value: Any, *, status_slug: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    if normalized == "attached":
        return FINAL_OUTCOME_HIRED
    if normalized == "not_attached":
        return FINAL_OUTCOME_NOT_HIRED
    if normalized == FINAL_OUTCOME_NOT_COUNTED:
        return FINAL_OUTCOME_NOT_COUNTED
    if normalized in {
        FINAL_OUTCOME_HIRED,
        FINAL_OUTCOME_NOT_HIRED,
        FINAL_OUTCOME_NOT_COUNTED,
    }:
        return normalized
    if status_slug == CandidateStatus.HIRED.value:
        return FINAL_OUTCOME_HIRED
    if status_slug in TERMINAL_STATUS_SLUGS:
        return FINAL_OUTCOME_NOT_HIRED
    return None


def _normalize_archive_reason(candidate: Any, *, status_slug: Optional[str]) -> Optional[str]:
    raw_reason = (
        getattr(candidate, "archive_reason", None)
        or getattr(candidate, "rejection_reason", None)
        or getattr(candidate, "intro_decline_reason", None)
        or getattr(candidate, "final_outcome_reason", None)
    )
    text = str(raw_reason or "").strip().lower()
    if status_slug == CandidateStatus.INTERVIEW_DECLINED.value:
        return "candidate_declined"
    if status_slug == CandidateStatus.TEST2_FAILED.value:
        return "failed_test2"
    if status_slug in {
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION.value,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF.value,
    }:
        return "intro_day_declined"
    if "no show" in text or "no_show" in text or "не яв" in text or "не приш" in text:
        return "no_show"
    if "technical" in text or "техничес" in text:
        return "technical_failure"
    if "duplicate" in text or "дубл" in text:
        return "duplicate"
    if "invalid" in text or "некорр" in text:
        return "invalid_contact"
    if "merged" in text or "объедин" in text:
        return "merged"
    if "manual" in text or "вручн" in text:
        return "manual_removal"
    if "reject" in text or "отказ" in text:
        return "recruiter_declined"
    return "other" if text else None


def _slot_purpose(slot: Optional[Slot]) -> str:
    if slot is None:
        return SCHEDULING_STAGE_INTERVIEW
    return (
        SCHEDULING_STAGE_INTRO_DAY
        if str(getattr(slot, "purpose", "") or "").strip().lower() == "intro_day"
        else SCHEDULING_STAGE_INTERVIEW
    )


def _normalize_slot_status(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _map_slot_status_to_target(slot_status: Optional[str]) -> Optional[str]:
    if slot_status == SlotStatus.PENDING:
        return SCHEDULING_STATUS_SELECTED
    if slot_status == SlotStatus.BOOKED:
        return SCHEDULING_STATUS_SCHEDULED
    if slot_status in {SlotStatus.CONFIRMED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
        return SCHEDULING_STATUS_CONFIRMED
    if slot_status in {SlotStatus.CANCELED, SlotStatus.CANCELLED}:
        return SCHEDULING_STATUS_CANCELLED
    return None


def _map_assignment_status_to_target(raw_status: Optional[str]) -> Optional[str]:
    if raw_status == SlotAssignmentStatus.OFFERED:
        return SCHEDULING_STATUS_OFFERED
    if raw_status == SlotAssignmentStatus.CONFIRMED:
        return SCHEDULING_STATUS_CONFIRMED
    if raw_status == SlotAssignmentStatus.RESCHEDULE_REQUESTED:
        return SCHEDULING_STATUS_RESCHEDULE_REQUESTED
    if raw_status == SlotAssignmentStatus.RESCHEDULE_CONFIRMED:
        return SCHEDULING_STATUS_SCHEDULED
    if raw_status in {SlotAssignmentStatus.REJECTED, SlotAssignmentStatus.CANCELLED}:
        return SCHEDULING_STATUS_CANCELLED
    if raw_status == SlotAssignmentStatus.COMPLETED:
        return SCHEDULING_STATUS_COMPLETED
    if raw_status == SlotAssignmentStatus.NO_SHOW:
        return SCHEDULING_STATUS_NO_SHOW
    return None


def _pick_latest_assignment(slot_assignments: Sequence[SlotAssignment]) -> Optional[SlotAssignment]:
    if not slot_assignments:
        return None
    return max(
        slot_assignments,
        key=lambda item: (
            getattr(item, "updated_at", None) or getattr(item, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc),
            getattr(item, "id", 0),
        ),
    )


def _pick_active_slot(slots: Sequence[Slot], now: datetime) -> Optional[Slot]:
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
        if getattr(slot, "start_utc", None) is None or getattr(slot, "start_utc", None) >= now - timedelta(hours=1)
    ]
    pool = upcoming or active_slots
    return min(
        pool,
        key=lambda item: (
            getattr(item, "start_utc", None) or datetime.max.replace(tzinfo=timezone.utc),
            getattr(item, "id", 0),
        ),
    )


def _action_field(action: object, key: str) -> Optional[object]:
    if isinstance(action, Mapping):
        return action.get(key)
    return getattr(action, key, None)


def _choose_primary_legacy_action(actions: Sequence[object]) -> Optional[object]:
    indexed = {str(_action_field(action, "key") or ""): action for action in actions}
    for key in ACTION_PRIORITY:
        if key in indexed:
            return indexed[key]
    return actions[0] if actions else None


def build_scheduling_summary(
    *,
    slots: Sequence[Slot],
    slot_assignments: Sequence[SlotAssignment],
    pending_slot_request: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    integrity = build_scheduling_integrity_report(
        slots=slots,
        slot_assignments=slot_assignments,
        now=current_time,
    )
    latest_assignment = integrity.get("latest_assignment")
    active_assignment = integrity.get("active_assignment")
    active_slot = integrity.get("active_slot")

    source = "none"
    stage = None
    status = None
    slot_id = None
    slot_assignment_id = None
    slot_status = None
    assignment_status = None
    start_utc = None
    candidate_tz = None

    if active_assignment is not None or latest_assignment is not None:
        source = "slot_assignment"
        assignment = active_assignment or latest_assignment
        slot = getattr(assignment, "slot", None)
        stage = _slot_purpose(slot)
        assignment_status = str(getattr(assignment, "status", "") or "").strip().lower() or None
        status = _map_assignment_status_to_target(assignment_status)
        slot_assignment_id = getattr(assignment, "id", None)
        slot_id = getattr(assignment, "slot_id", None) or getattr(slot, "id", None)
        slot_status = _normalize_slot_status(getattr(slot, "status", None))
        start_utc = getattr(slot, "start_utc", None)
        candidate_tz = getattr(assignment, "candidate_tz", None) or getattr(slot, "candidate_tz", None)
    elif active_slot is not None:
        source = "legacy_slot"
        stage = _slot_purpose(active_slot)
        slot_status = _normalize_slot_status(getattr(active_slot, "status", None))
        status = _map_slot_status_to_target(slot_status)
        slot_id = getattr(active_slot, "id", None)
        start_utc = getattr(active_slot, "start_utc", None)
        candidate_tz = getattr(active_slot, "candidate_tz", None)

    requested_reschedule = bool(
        (pending_slot_request or {}).get("requested")
        or status == SCHEDULING_STATUS_RESCHEDULE_REQUESTED
    )
    active = status in {
        SCHEDULING_STATUS_OFFERED,
        SCHEDULING_STATUS_SELECTED,
        SCHEDULING_STATUS_SCHEDULED,
        SCHEDULING_STATUS_CONFIRMED,
        SCHEDULING_STATUS_RESCHEDULE_REQUESTED,
    }

    issues: list[dict[str, Any]] = []
    issues = [dict(issue) for issue in (integrity.get("issues") or [])]

    return {
        "source": source,
        "stage": stage,
        "status": status,
        "status_label": SCHEDULING_STATUS_LABELS.get(status),
        "active": active,
        "requested_reschedule": requested_reschedule,
        "slot_id": slot_id,
        "slot_assignment_id": slot_assignment_id,
        "slot_status": slot_status,
        "slot_assignment_status": assignment_status,
        "start_utc": _iso(start_utc),
        "candidate_tz": candidate_tz,
        "issues": issues,
        "integrity_state": integrity.get("integrity_state"),
        "write_behavior": integrity.get("write_behavior"),
        "write_owner": integrity.get("write_owner"),
        "assignment_owned": bool(integrity.get("assignment_owned")),
        "slot_only_writes_allowed": bool(integrity.get("slot_only_writes_allowed")),
        "repairability": integrity.get("repairability"),
        "repair_options": list(integrity.get("repair_options") or []),
        "manual_repair_reasons": list(integrity.get("manual_repair_reasons") or []),
        "repair_workflow": dict(integrity.get("repair_workflow") or {}),
    }


def build_lifecycle_summary(
    *,
    candidate: Any,
    scheduling_summary: Mapping[str, Any],
    legacy_status_slug: Optional[str] = None,
    test2_status: Optional[str] = None,
    has_intro_day_slot: bool = False,
) -> dict[str, Any]:
    status_slug = legacy_status_slug or _status_slug(getattr(candidate, "candidate_status", None))
    final_outcome = _normalize_final_outcome(
        getattr(candidate, "final_outcome", None),
        status_slug=status_slug,
    )
    archive_reason = _normalize_archive_reason(candidate, status_slug=status_slug)
    raw_lifecycle_state = str(getattr(candidate, "lifecycle_state", "") or "").strip().lower()
    record_state = RECORD_STATE_ACTIVE
    if raw_lifecycle_state == "archived" or status_slug in TERMINAL_STATUS_SLUGS or final_outcome is not None:
        record_state = RECORD_STATE_CLOSED

    scheduling_stage = str(scheduling_summary.get("stage") or "").strip().lower() or None
    scheduling_active = bool(scheduling_summary.get("active"))

    if record_state == RECORD_STATE_CLOSED:
        stage = LIFECYCLE_STAGE_CLOSED
    elif scheduling_stage == SCHEDULING_STAGE_INTRO_DAY and scheduling_active:
        stage = LIFECYCLE_STAGE_INTRO_DAY
    elif status_slug in {
        CandidateStatus.INTRO_DAY_SCHEDULED.value,
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY.value,
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF.value,
    }:
        stage = LIFECYCLE_STAGE_INTRO_DAY if has_intro_day_slot else LIFECYCLE_STAGE_WAITING_INTRO_DAY
    elif status_slug in {
        CandidateStatus.TEST2_SENT.value,
        CandidateStatus.TEST2_COMPLETED.value,
    }:
        stage = LIFECYCLE_STAGE_WAITING_INTRO_DAY if test2_status == "passed" and not has_intro_day_slot else LIFECYCLE_STAGE_TEST2
    elif scheduling_stage == SCHEDULING_STAGE_INTERVIEW and scheduling_active:
        stage = LIFECYCLE_STAGE_INTERVIEW
    elif status_slug in {
        CandidateStatus.SLOT_PENDING.value,
        CandidateStatus.INTERVIEW_SCHEDULED.value,
        CandidateStatus.INTERVIEW_CONFIRMED.value,
    }:
        stage = LIFECYCLE_STAGE_INTERVIEW
    elif status_slug in {
        CandidateStatus.WAITING_SLOT.value,
        CandidateStatus.STALLED_WAITING_SLOT.value,
    }:
        stage = LIFECYCLE_STAGE_WAITING_INTERVIEW_SLOT
    elif status_slug in {
        CandidateStatus.CONTACTED.value,
        CandidateStatus.INVITED.value,
        CandidateStatus.TEST1_COMPLETED.value,
    }:
        stage = LIFECYCLE_STAGE_SCREENING
    else:
        stage = LIFECYCLE_STAGE_LEAD

    return {
        "stage": stage,
        "stage_label": LIFECYCLE_STAGE_LABELS.get(stage, stage),
        "record_state": record_state,
        "final_outcome": final_outcome,
        "final_outcome_label": FINAL_OUTCOME_LABELS.get(final_outcome),
        "archive_reason": archive_reason,
        "legacy_status_slug": status_slug,
        "updated_at": _iso(getattr(candidate, "status_changed_at", None)),
    }


def build_reconciliation_issues(
    *,
    candidate: Any,
    lifecycle_summary: Mapping[str, Any],
    scheduling_summary: Mapping[str, Any],
    test2_status: Optional[str] = None,
) -> list[dict[str, Any]]:
    issues = list(scheduling_summary.get("issues") or [])
    status_slug = str(lifecycle_summary.get("legacy_status_slug") or "").strip().lower() or None
    workflow_status = workflow_status_from_raw_value(getattr(candidate, "workflow_status", None))
    canonical_status = (
        CandidateStatus(status_slug)
        if status_slug in {item.value for item in CandidateStatus}
        else None
    )
    derived_workflow = workflow_status_for_candidate_status(canonical_status) if canonical_status else None
    if test2_status == "passed" and status_slug in {None, CandidateStatus.TEST2_SENT.value}:
        issues.append(
            {
                "code": "candidate_status_stale_after_test2_pass",
                "severity": "warning",
                "message": "Тест 2 пройден, но legacy candidate_status еще не синхронизирован.",
            }
        )
    if (
        workflow_status is not None
        and derived_workflow is not None
        and workflow_status != derived_workflow
    ):
        issues.append(
            {
                "code": "workflow_status_drift",
                "severity": "warning",
                "message": "workflow_status расходится с canonical candidate_status.",
            }
        )
    if (
        lifecycle_summary.get("record_state") == RECORD_STATE_CLOSED
        and lifecycle_summary.get("final_outcome") != FINAL_OUTCOME_HIRED
        and not lifecycle_summary.get("archive_reason")
    ):
        issues.append(
            {
                "code": "closed_candidate_missing_archive_reason",
                "severity": "warning",
                "message": "Закрытый кандидат не имеет нормализованной archive reason.",
            }
        )
    if (
        lifecycle_summary.get("stage") == LIFECYCLE_STAGE_INTERVIEW
        and not scheduling_summary.get("active")
        and status_slug in {
            CandidateStatus.INTERVIEW_SCHEDULED.value,
            CandidateStatus.INTERVIEW_CONFIRMED.value,
        }
    ):
        issues.append(
            {
                "code": "interview_stage_without_active_scheduling",
                "severity": "warning",
                "message": "Кандидат находится на интервью-этапе без активного scheduling summary.",
            }
        )
    return issues


def _build_primary_action(
    *,
    candidate: Any,
    lifecycle_summary: Mapping[str, Any],
    scheduling_summary: Mapping[str, Any],
    candidate_actions: Sequence[object],
    issues: Sequence[Mapping[str, Any]],
) -> tuple[Optional[dict[str, Any]], list[str], str]:
    stage = str(lifecycle_summary.get("stage") or "").strip().lower()
    record_state = str(lifecycle_summary.get("record_state") or "").strip().lower()
    requested_reschedule = bool(scheduling_summary.get("requested_reschedule"))
    has_contact_channel = bool(
        getattr(candidate, "telegram_id", None)
        or getattr(candidate, "max_user_id", None)
        or getattr(candidate, "phone", None)
    )
    blocking_reasons: list[str] = []

    if any(
        str(issue.get("code") or "").strip().lower().startswith("scheduling_")
        and str(issue.get("write_behavior") or "").strip().lower() == WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR
        for issue in issues
    ):
        return (
            {
                "type": "repair_inconsistency",
                "label": "Проверить состояние кандидата",
                "enabled": False,
                "owner_role": "recruiter",
                "blocking_reasons": ["data_inconsistency"],
                "deadline_at": None,
                "source_ref": None,
                "ui_action": None,
                "legacy_action_key": None,
            },
            ["data_inconsistency"],
            "Найдены конфликты между Slot и SlotAssignment. Нужна ручная проверка.",
        )

    if record_state == RECORD_STATE_CLOSED:
        return (None, [], "Кандидат закрыт. Новых действий не требуется.")

    if requested_reschedule:
        return (
            {
                "type": "resolve_reschedule",
                "label": "Обработать перенос",
                "enabled": has_contact_channel,
                "owner_role": "recruiter",
                "blocking_reasons": [] if has_contact_channel else ["missing_contact_channel"],
                "deadline_at": None,
                "source_ref": {
                    "kind": "slot_assignment" if scheduling_summary.get("slot_assignment_id") else "slot",
                    "id": scheduling_summary.get("slot_assignment_id") or scheduling_summary.get("slot_id"),
                },
                "ui_action": "open_schedule_slot_modal",
                "legacy_action_key": "reschedule_interview",
            },
            [] if has_contact_channel else ["missing_contact_channel"],
            "Кандидат запросил перенос времени. Требуется новый слот.",
        )

    if stage == LIFECYCLE_STAGE_WAITING_INTERVIEW_SLOT:
        enabled = has_contact_channel
        if not enabled:
            blocking_reasons.append("missing_contact_channel")
        return (
            {
                "type": "offer_interview_slot",
                "label": "Предложить время",
                "enabled": enabled,
                "owner_role": "recruiter",
                "blocking_reasons": blocking_reasons,
                "deadline_at": None,
                "source_ref": None,
                "ui_action": "open_schedule_slot_modal",
                "legacy_action_key": "schedule_interview",
            },
            blocking_reasons,
            "Кандидат готов к назначению интервью и ждет слот.",
        )

    if stage == LIFECYCLE_STAGE_WAITING_INTRO_DAY:
        return (
            {
                "type": "schedule_intro_day",
                "label": "Назначить ознакомительный день",
                "enabled": True,
                "owner_role": "recruiter",
                "blocking_reasons": [],
                "deadline_at": None,
                "source_ref": None,
                "ui_action": "open_schedule_intro_day_modal",
                "legacy_action_key": "schedule_intro_day",
            },
            [],
            "Интервью и Test 2 завершены. Нужно назначить ознакомительный день.",
        )

    primary_legacy_action = _choose_primary_legacy_action(candidate_actions)
    primary_legacy_action_key = (
        str(_action_field(primary_legacy_action, "key") or "").strip().lower()
        if primary_legacy_action is not None
        else ""
    )
    scheduling_status = str(scheduling_summary.get("status") or "").strip().lower()
    scheduling_start = _parse_utc_datetime(scheduling_summary.get("start_utc"))
    interview_window_started = bool(
        stage == LIFECYCLE_STAGE_INTERVIEW
        and scheduling_status in {SCHEDULING_STATUS_SCHEDULED, SCHEDULING_STATUS_CONFIRMED}
        and scheduling_start is not None
        and scheduling_start <= datetime.now(timezone.utc)
    )
    if interview_window_started:
        for candidate_action in candidate_actions:
            candidate_action_key = str(_action_field(candidate_action, "key") or "").strip().lower()
            if candidate_action_key in {"interview_outcome_passed", "interview_passed", "resend_test2"}:
                primary_legacy_action = candidate_action
                primary_legacy_action_key = candidate_action_key
                break
    if primary_legacy_action_key in {"interview_outcome_passed", "interview_passed", "resend_test2"} and stage in {
        LIFECYCLE_STAGE_LEAD,
        LIFECYCLE_STAGE_SCREENING,
        LIFECYCLE_STAGE_WAITING_INTERVIEW_SLOT,
    }:
        primary_legacy_action = None
        primary_legacy_action_key = ""
    elif interview_window_started and primary_legacy_action is not None and primary_legacy_action_key in {
        "interview_outcome_passed",
        "interview_passed",
        "resend_test2",
    }:
        action_key = str(_action_field(primary_legacy_action, "key") or "").strip()
        action_label = str(_action_field(primary_legacy_action, "label") or "").strip() or action_key
        return (
            {
                "type": ACTION_TYPE_BY_KEY.get(action_key, action_key or "wait_for_candidate"),
                "label": action_label,
                "enabled": True,
                "owner_role": "recruiter",
                "blocking_reasons": [],
                "deadline_at": None,
                "source_ref": {
                    "kind": "slot_assignment" if scheduling_summary.get("slot_assignment_id") else "slot",
                    "id": scheduling_summary.get("slot_assignment_id") or scheduling_summary.get("slot_id"),
                },
                "ui_action": UI_ACTION_BY_KEY.get(action_key, "invoke_candidate_action"),
                "legacy_action_key": action_key or None,
            },
            [],
            "Время интервью прошло. Можно отправить кандидату Тест 2.",
        )
    if primary_legacy_action is None:
        if stage == LIFECYCLE_STAGE_INTERVIEW and scheduling_status in {
            SCHEDULING_STATUS_OFFERED,
            SCHEDULING_STATUS_SCHEDULED,
        }:
            return (
                {
                    "type": "follow_up_confirmation",
                    "label": "Напомнить о подтверждении",
                    "enabled": has_contact_channel,
                    "owner_role": "recruiter",
                    "blocking_reasons": [] if has_contact_channel else ["missing_contact_channel"],
                    "deadline_at": None,
                    "source_ref": {
                        "kind": "slot_assignment" if scheduling_summary.get("slot_assignment_id") else "slot",
                        "id": scheduling_summary.get("slot_assignment_id") or scheduling_summary.get("slot_id"),
                    },
                    "ui_action": "open_chat",
                    "legacy_action_key": None,
                },
                [] if has_contact_channel else ["missing_contact_channel"],
                "Слот предложен, ожидаем подтверждение кандидата.",
            )
        return (
            {
                "type": "wait_for_candidate",
                "label": "Ожидаем ответ кандидата",
                "enabled": False,
                "owner_role": "candidate",
                "blocking_reasons": ["waiting_candidate_response"],
                "deadline_at": None,
                "source_ref": None,
                "ui_action": None,
                "legacy_action_key": None,
            },
            ["waiting_candidate_response"],
            "Следующее действие со стороны кандидата или внешнего канала.",
        )

    action_key = str(_action_field(primary_legacy_action, "key") or "").strip()
    action_label = str(_action_field(primary_legacy_action, "label") or "").strip() or action_key
    return (
        {
            "type": ACTION_TYPE_BY_KEY.get(action_key, action_key or "wait_for_candidate"),
            "label": action_label,
            "enabled": True,
            "owner_role": "recruiter",
            "blocking_reasons": [],
            "deadline_at": None,
            "source_ref": None,
            "ui_action": UI_ACTION_BY_KEY.get(action_key, "invoke_candidate_action"),
            "legacy_action_key": action_key or None,
        },
        [],
        action_label,
    )


def build_candidate_next_action(
    *,
    candidate: Any,
    lifecycle_summary: Mapping[str, Any],
    scheduling_summary: Mapping[str, Any],
    candidate_actions: Sequence[object],
    issues: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    primary_action, blocking_reasons, explanation = _build_primary_action(
        candidate=candidate,
        lifecycle_summary=lifecycle_summary,
        scheduling_summary=scheduling_summary,
        candidate_actions=candidate_actions,
        issues=issues,
    )
    stage = str(lifecycle_summary.get("stage") or "").strip().lower()
    record_state = str(lifecycle_summary.get("record_state") or "").strip().lower()
    updated_at = lifecycle_summary.get("updated_at")
    scheduling_start = scheduling_summary.get("start_utc")

    if record_state == RECORD_STATE_CLOSED:
        worklist_bucket = "closed"
        urgency = "normal"
    elif primary_action and primary_action.get("type") == "wait_for_candidate":
        worklist_bucket = "awaiting_candidate"
        urgency = "normal"
    elif blocking_reasons:
        worklist_bucket = "blocked"
        urgency = "blocked"
    elif stage in {LIFECYCLE_STAGE_INTERVIEW, LIFECYCLE_STAGE_INTRO_DAY} and scheduling_start:
        worklist_bucket = "today"
        urgency = "attention"
    elif stage in {
        LIFECYCLE_STAGE_LEAD,
        LIFECYCLE_STAGE_SCREENING,
        LIFECYCLE_STAGE_WAITING_INTERVIEW_SLOT,
        LIFECYCLE_STAGE_WAITING_INTRO_DAY,
    }:
        worklist_bucket = "incoming"
        urgency = "attention"
    else:
        worklist_bucket = "awaiting_recruiter"
        urgency = "normal"

    return {
        "version": STATE_CONTRACT_VERSION,
        "candidate_id": getattr(candidate, "candidate_id", None),
        "lifecycle_stage": lifecycle_summary.get("stage"),
        "record_state": lifecycle_summary.get("record_state"),
        "worklist_bucket": worklist_bucket,
        "worklist_bucket_label": WORKLIST_BUCKET_LABELS.get(worklist_bucket, worklist_bucket),
        "urgency": urgency,
        "stale_since": updated_at or scheduling_start,
        "primary_action": primary_action,
        "secondary_actions": [],
        "blocking_reasons": blocking_reasons,
        "explanation": explanation,
    }


def _resolve_kanban_column(
    *,
    lifecycle_summary: Mapping[str, Any],
    scheduling_summary: Mapping[str, Any],
    candidate_next_action: Mapping[str, Any],
) -> Optional[str]:
    stage = str(lifecycle_summary.get("stage") or "").strip().lower()
    record_state = str(lifecycle_summary.get("record_state") or "").strip().lower()
    if record_state == RECORD_STATE_CLOSED:
        legacy_status_slug = str(lifecycle_summary.get("legacy_status_slug") or "").strip().lower() or None
        return LEGACY_KANBAN_COLUMN_BY_STATUS.get(legacy_status_slug)

    scheduling_status = str(scheduling_summary.get("status") or "").strip().lower() or None
    primary_action = candidate_next_action.get("primary_action") if isinstance(candidate_next_action, Mapping) else None
    primary_action_type = (
        str(primary_action.get("type") or "").strip().lower()
        if isinstance(primary_action, Mapping)
        else None
    )

    if stage in {
        LIFECYCLE_STAGE_LEAD,
        LIFECYCLE_STAGE_SCREENING,
        LIFECYCLE_STAGE_WAITING_INTERVIEW_SLOT,
    }:
        return "incoming"
    if stage == LIFECYCLE_STAGE_INTERVIEW:
        if scheduling_status == SCHEDULING_STATUS_SELECTED:
            return "slot_pending"
        if scheduling_status == SCHEDULING_STATUS_CONFIRMED:
            return "interview_confirmed"
        return "interview_scheduled"
    if stage == LIFECYCLE_STAGE_TEST2:
        return "test2_completed" if primary_action_type == "schedule_intro_day" else "test2_sent"
    if stage == LIFECYCLE_STAGE_WAITING_INTRO_DAY:
        return "test2_completed"
    if stage == LIFECYCLE_STAGE_INTRO_DAY:
        if scheduling_status == SCHEDULING_STATUS_CONFIRMED:
            if primary_action_type in {"finalize_hired", "finalize_not_hired"}:
                return "intro_day_confirmed_day_of"
            return "intro_day_confirmed_preliminary"
        return "intro_day_scheduled"
    legacy_status_slug = str(lifecycle_summary.get("legacy_status_slug") or "").strip().lower() or None
    return LEGACY_KANBAN_COLUMN_BY_STATUS.get(legacy_status_slug)


def build_operational_summary(
    *,
    lifecycle_summary: Mapping[str, Any],
    scheduling_summary: Mapping[str, Any],
    candidate_next_action: Mapping[str, Any],
    issues: Sequence[Mapping[str, Any]],
    waiting_hours: Optional[int] = None,
    incoming_substatus: Optional[str] = None,
) -> dict[str, Any]:
    primary_action = candidate_next_action.get("primary_action") if isinstance(candidate_next_action, Mapping) else None
    primary_action_type = (
        str(primary_action.get("type") or "").strip().lower()
        if isinstance(primary_action, Mapping)
        else None
    )
    worklist_bucket = str(candidate_next_action.get("worklist_bucket") or "").strip().lower() or "incoming"
    worklist_bucket_label = (
        str(candidate_next_action.get("worklist_bucket_label") or "").strip()
        or WORKLIST_BUCKET_LABELS.get(worklist_bucket, worklist_bucket)
    )
    legacy_status_slug = str(lifecycle_summary.get("legacy_status_slug") or "").strip().lower() or None
    requested_reschedule = bool(
        scheduling_summary.get("requested_reschedule")
        or incoming_substatus == "requested_other_time"
        or primary_action_type == "resolve_reschedule"
    )
    pending_approval = bool(
        scheduling_summary.get("status") == SCHEDULING_STATUS_SELECTED
        or incoming_substatus == "awaiting_candidate_confirmation"
        or legacy_status_slug == CandidateStatus.SLOT_PENDING.value
        or primary_action_type == "approve_selected_slot"
    )
    stalled = bool(
        lifecycle_summary.get("stage") == LIFECYCLE_STAGE_WAITING_INTERVIEW_SLOT
        and (
            (waiting_hours or 0) >= 24
            or incoming_substatus == "stalled_waiting_slot"
            or legacy_status_slug == CandidateStatus.STALLED_WAITING_SLOT.value
        )
    )
    has_reconciliation_issues = bool(issues)
    has_scheduling_conflict = any(
        str(issue.get("code") or "").strip().lower().startswith("scheduling_")
        for issue in issues
    )

    if requested_reschedule:
        queue_state = "requested_other_time"
    elif pending_approval:
        queue_state = "awaiting_candidate_confirmation"
    elif stalled:
        queue_state = "stalled_waiting_slot"
    elif worklist_bucket == "today":
        queue_state = "scheduled"
    elif worklist_bucket == "awaiting_candidate":
        queue_state = "waiting_candidate"
    elif worklist_bucket == "awaiting_recruiter":
        queue_state = "waiting_recruiter"
    elif worklist_bucket == "closed":
        queue_state = "closed"
    else:
        queue_state = "waiting_slot"

    kanban_column = _resolve_kanban_column(
        lifecycle_summary=lifecycle_summary,
        scheduling_summary=scheduling_summary,
        candidate_next_action=candidate_next_action,
    )
    dominant_signal = (
        "needs_attention"
        if has_reconciliation_issues
        else "requested_other_time"
        if requested_reschedule
        else "awaiting_candidate_confirmation"
        if pending_approval
        else "stalled_waiting_slot"
        if stalled
        else queue_state
    )

    return {
        "worklist_bucket": worklist_bucket,
        "worklist_bucket_label": worklist_bucket_label,
        "kanban_column": kanban_column,
        "kanban_column_label": KANBAN_COLUMN_LABELS.get(kanban_column),
        "kanban_column_icon": KANBAN_COLUMN_ICONS.get(kanban_column),
        "kanban_target_status": KANBAN_COLUMN_TARGET_STATUSES.get(kanban_column),
        "queue_state": queue_state,
        "queue_state_label": QUEUE_STATE_LABELS.get(queue_state, queue_state),
        "dominant_signal": dominant_signal,
        "dominant_signal_label": QUEUE_STATE_LABELS.get(dominant_signal, dominant_signal),
        "requested_reschedule": requested_reschedule,
        "pending_approval": pending_approval,
        "stalled": stalled,
        "has_reconciliation_issues": has_reconciliation_issues,
        "has_scheduling_conflict": has_scheduling_conflict,
    }


def build_candidate_state_contract(
    *,
    candidate: Any,
    candidate_actions: Sequence[object],
    slots: Sequence[Slot],
    slot_assignments: Sequence[SlotAssignment],
    pending_slot_request: Optional[dict[str, Any]] = None,
    legacy_status_slug: Optional[str] = None,
    test2_status: Optional[str] = None,
    has_intro_day_slot: bool = False,
    now: Optional[datetime] = None,
    waiting_hours: Optional[int] = None,
    incoming_substatus: Optional[str] = None,
) -> dict[str, Any]:
    scheduling_summary = build_scheduling_summary(
        slots=slots,
        slot_assignments=slot_assignments,
        pending_slot_request=pending_slot_request,
        now=now,
    )
    lifecycle_summary = build_lifecycle_summary(
        candidate=candidate,
        scheduling_summary=scheduling_summary,
        legacy_status_slug=legacy_status_slug,
        test2_status=test2_status,
        has_intro_day_slot=has_intro_day_slot,
    )
    issues = build_reconciliation_issues(
        candidate=candidate,
        lifecycle_summary=lifecycle_summary,
        scheduling_summary=scheduling_summary,
        test2_status=test2_status,
    )
    candidate_next_action = build_candidate_next_action(
        candidate=candidate,
        lifecycle_summary=lifecycle_summary,
        scheduling_summary=scheduling_summary,
        candidate_actions=candidate_actions,
        issues=issues,
    )
    operational_summary = build_operational_summary(
        lifecycle_summary=lifecycle_summary,
        scheduling_summary=scheduling_summary,
        candidate_next_action=candidate_next_action,
        issues=issues,
        waiting_hours=waiting_hours,
        incoming_substatus=incoming_substatus,
    )
    return {
        "version": STATE_CONTRACT_VERSION,
        "lifecycle_summary": lifecycle_summary,
        "scheduling_summary": scheduling_summary,
        "candidate_next_action": candidate_next_action,
        "operational_summary": operational_summary,
        "reconciliation": {
            "issues": issues,
            "has_blockers": any(
                str(issue.get("severity") or "").strip().lower() in {"warning", "error", "critical"}
                for issue in issues
            ),
        },
    }


__all__ = [
    "KANBAN_COLUMN_ICONS",
    "KANBAN_COLUMN_LABELS",
    "KANBAN_COLUMN_TARGET_STATUSES",
    "KANBAN_PIPELINE_COLUMNS",
    "STATE_CONTRACT_VERSION",
    "build_candidate_state_contract",
]
