from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from zoneinfo import ZoneInfo

from backend.domain.candidates.status import CandidateStatus
from sqlalchemy import inspect
from sqlalchemy.orm.attributes import NO_VALUE, set_committed_value

if TYPE_CHECKING:
    from backend.apps.admin_ui.services.reschedule_intents import RescheduleIntent
    from backend.domain.candidates.models import CandidateJourneyEvent, User
    from backend.domain.models import Recruiter, Slot

LIFECYCLE_ACTIVE = "active"
LIFECYCLE_DRAFT = "draft"
LIFECYCLE_ARCHIVED = "archived"

FINAL_OUTCOME_ATTACHED = "attached"
FINAL_OUTCOME_NOT_ATTACHED = "not_attached"
FINAL_OUTCOME_NOT_COUNTED = "not_counted"

FINAL_OUTCOME_LABELS = {
    FINAL_OUTCOME_ATTACHED: "Закреплен",
    FINAL_OUTCOME_NOT_ATTACHED: "Не закреплен",
    FINAL_OUTCOME_NOT_COUNTED: "Не засчитан",
}

LIFECYCLE_LABELS = {
    LIFECYCLE_ACTIVE: "Активен",
    LIFECYCLE_DRAFT: "Черновик intake",
    LIFECYCLE_ARCHIVED: "Архив",
}

ARCHIVE_STAGE_LABELS = {
    "lead": "Лид",
    "testing": "Тестирование",
    "interview": "Собеседование",
    "intro_day": "Ознакомительный день",
    "outcome": "Финальное решение",
}

JOURNEY_STATE_LABELS = {
    "lead": "Новый кандидат",
    "contacted": "Контакт установлен",
    "invited": "Приглашён",
    "test1_completed": "Тест 1 пройден",
    "waiting_slot": "Ожидает слот",
    "stalled_waiting_slot": "Нет слотов",
    "slot_pending": "Ожидает подтверждение слота",
    "slot_agreed": "Слот согласован",
    "time_proposed_waiting_candidate": "Предложено время, ожидаем ответа",
    "requested_other_slot": "Запросил другой слот",
    "interview_confirmed": "Собеседование подтверждено",
    "interview_declined": "Отказ от собеседования",
    "test2_sent": "Тест 2 отправлен",
    "test2_sent_waiting": "Тест 2 отправлен, ждём реакцию",
    "test2_completed": "Тест 2 пройден",
    "test2_failed": "Тест 2 не пройден",
    "intro_day_scheduled": "Ознакомительный день назначен",
    "intro_preconfirmed": "Предварительно подтвердился",
    "intro_day_confirmed_day_of": "Подтвердился в день ОД",
    "hired": "Закреплен",
    "not_hired": "Не закреплен",
    "archived_negative": "Архив",
}

NEGATIVE_ARCHIVE_STATUSES = {
    CandidateStatus.INTERVIEW_DECLINED,
    CandidateStatus.TEST2_FAILED,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
    CandidateStatus.NOT_HIRED,
}

ARCHIVE_STAGE_BY_STATUS = {
    CandidateStatus.INTERVIEW_DECLINED: "interview",
    CandidateStatus.TEST2_FAILED: "test2",
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION: "intro_day",
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: "intro_day",
    CandidateStatus.NOT_HIRED: "outcome",
}


def _normalized_reason(*parts: Optional[str]) -> Optional[str]:
    for part in parts:
        value = str(part or "").strip()
        if value:
            return value
    return None


def stage_for_status(status: Optional[CandidateStatus | str]) -> str:
    slug = status.value if isinstance(status, CandidateStatus) else str(status or "").strip().lower()
    if not slug:
        return "lead"
    if slug in {"lead", "contacted", "invited"}:
        return "lead"
    if slug in {"test1_completed", "waiting_slot", "stalled_waiting_slot", "test2_sent", "test2_completed", "test2_failed"}:
        return "testing"
    if slug in {"slot_pending", "interview_scheduled", "interview_confirmed", "interview_declined"}:
        return "interview"
    if slug.startswith("intro_day_"):
        return "intro_day"
    if slug in {"hired", "not_hired"}:
        return "outcome"
    return "lead"


def normalize_status_slug(status: Optional[CandidateStatus | str]) -> Optional[str]:
    if isinstance(status, CandidateStatus):
        return status.value
    value = str(status or "").strip().lower()
    return value or None


def is_not_counted_reason(reason: Optional[str]) -> bool:
    text = str(reason or "").strip().lower()
    if not text:
        return False
    keywords = (
        "не засчит",
        "не подлежит оплат",
        "не приш",
        "не яв",
        "no show",
        "no_show",
        "критер",
    )
    return any(keyword in text for keyword in keywords)


def final_outcome_for_status(
    status: Optional[CandidateStatus | str],
    *,
    reason: Optional[str] = None,
    existing: Optional[str] = None,
) -> Optional[str]:
    slug = status.value if isinstance(status, CandidateStatus) else str(status or "").strip().lower()
    if not slug:
        return existing
    if slug == CandidateStatus.HIRED.value:
        return FINAL_OUTCOME_ATTACHED
    if slug == CandidateStatus.NOT_HIRED.value:
        return FINAL_OUTCOME_NOT_COUNTED if is_not_counted_reason(reason) else FINAL_OUTCOME_NOT_ATTACHED
    if slug in {
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION.value,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF.value,
    }:
        return FINAL_OUTCOME_NOT_COUNTED if is_not_counted_reason(reason) else (existing or FINAL_OUTCOME_NOT_ATTACHED)
    return existing


def final_outcome_label(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return FINAL_OUTCOME_LABELS.get(normalized)


def lifecycle_label(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return LIFECYCLE_LABELS.get(normalized)


def archive_stage_label(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return ARCHIVE_STAGE_LABELS.get(normalized)


def journey_state_label(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return JOURNEY_STATE_LABELS["lead"]
    return JOURNEY_STATE_LABELS.get(normalized, normalized.replace("_", " ").strip().capitalize())


def _safe_zone(tz: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(str(tz or "Europe/Moscow"))
    except Exception:
        return ZoneInfo("Europe/Moscow")


def _normalize_intro_day_status(
    status: Optional[CandidateStatus | str],
    upcoming_slot: Optional["Slot"],
) -> Optional[CandidateStatus | str]:
    if status != CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF or upcoming_slot is None:
        return status
    if str(getattr(upcoming_slot, "purpose", "") or "").strip().lower() != "intro_day":
        return status
    slot_start = getattr(upcoming_slot, "start_utc", None)
    if slot_start is None:
        return status
    tz_name = (
        getattr(upcoming_slot, "candidate_tz", None)
        or getattr(upcoming_slot, "tz_name", None)
        or "Europe/Moscow"
    )
    zone = _safe_zone(tz_name)
    if slot_start.astimezone(zone).date() > datetime.now(timezone.utc).astimezone(zone).date():
        return CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY
    return status


def manual_mode_for_candidate(candidate: "User") -> bool:
    source = str(getattr(candidate, "source", "") or "").strip().lower()
    return source in {"manual_silent", "manual_call"}


def append_journey_event(
    candidate: "User",
    *,
    event_key: str,
    stage: Optional[str] = None,
    status: Optional[CandidateStatus | str] = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[int] = None,
    summary: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    created_at: Optional[datetime] = None,
) -> "CandidateJourneyEvent":
    from backend.domain.candidates.models import CandidateJourneyEvent

    event_stage = (stage or stage_for_status(status or getattr(candidate, "candidate_status", None)) or "lead").strip().lower()
    status_slug = normalize_status_slug(status or getattr(candidate, "candidate_status", None))
    event = CandidateJourneyEvent(
        stage=event_stage,
        event_key=str(event_key or "").strip() or "event",
        status_slug=status_slug,
        actor_type=(str(actor_type).strip() or None) if actor_type is not None else None,
        actor_id=actor_id,
        summary=(str(summary).strip() or None) if summary is not None else None,
        payload_json=payload or None,
        created_at=created_at or datetime.now(timezone.utc),
    )
    state = inspect(candidate)
    attr_state = state.attrs.journey_events
    if attr_state.loaded_value is NO_VALUE:
        set_committed_value(candidate, "journey_events", [])
    candidate.journey_events.append(event)
    return event


def serialize_journey_event(event: "CandidateJourneyEvent") -> dict[str, Any]:
    return {
        "id": int(getattr(event, "id", 0) or 0),
        "event_key": getattr(event, "event_key", None),
        "stage": getattr(event, "stage", None),
        "status_slug": getattr(event, "status_slug", None),
        "actor_type": getattr(event, "actor_type", None),
        "actor_id": getattr(event, "actor_id", None),
        "summary": getattr(event, "summary", None),
        "payload": getattr(event, "payload_json", None),
        "created_at": getattr(event, "created_at", None).isoformat()
        if getattr(event, "created_at", None)
        else None,
    }


def serialize_pending_slot_request(
    request: Optional["RescheduleIntent"],
) -> Optional[dict[str, Any]]:
    if request is None or not getattr(request, "requested", False):
        return None
    return {
        "requested": True,
        "requested_at": getattr(request, "created_at", None),
        "requested_start_utc": getattr(request, "requested_start_utc", None),
        "requested_end_utc": getattr(request, "requested_end_utc", None),
        "requested_tz": getattr(request, "requested_tz", None),
        "candidate_comment": getattr(request, "candidate_comment", None),
        "source": getattr(request, "source", None),
    }


def sync_candidate_lifecycle(
    candidate,
    *,
    status: Optional[CandidateStatus | str] = None,
    archive_reason: Optional[str] = None,
    final_outcome: Optional[str] = None,
    final_outcome_reason: Optional[str] = None,
) -> None:
    current_status = status if status is not None else getattr(candidate, "candidate_status", None)
    normalized_status = current_status if isinstance(current_status, CandidateStatus) else (
        CandidateStatus(str(current_status))
        if str(current_status or "").strip()
        in {item.value for item in CandidateStatus}
        else None
    )
    resolved_reason = _normalized_reason(
        archive_reason,
        getattr(candidate, "archive_reason", None),
        getattr(candidate, "rejection_reason", None),
        getattr(candidate, "intro_decline_reason", None),
        getattr(candidate, "final_outcome_reason", None),
    )
    resolved_outcome = final_outcome or final_outcome_for_status(
        normalized_status,
        reason=final_outcome_reason or resolved_reason,
        existing=getattr(candidate, "final_outcome", None),
    )

    if normalized_status in NEGATIVE_ARCHIVE_STATUSES:
        candidate.lifecycle_state = LIFECYCLE_ARCHIVED
        candidate.archive_stage = ARCHIVE_STAGE_BY_STATUS.get(normalized_status, stage_for_status(normalized_status))
        candidate.archive_reason = resolved_reason
        candidate.archived_at = getattr(candidate, "archived_at", None) or datetime.now(timezone.utc)
    else:
        candidate.lifecycle_state = LIFECYCLE_ACTIVE
        candidate.archive_stage = None
        candidate.archive_reason = None
        candidate.archived_at = None

    if normalized_status == CandidateStatus.HIRED:
        candidate.final_outcome = FINAL_OUTCOME_ATTACHED
        candidate.final_outcome_reason = final_outcome_reason or None
    elif resolved_outcome in {
        FINAL_OUTCOME_ATTACHED,
        FINAL_OUTCOME_NOT_ATTACHED,
        FINAL_OUTCOME_NOT_COUNTED,
    }:
        candidate.final_outcome = resolved_outcome
        candidate.final_outcome_reason = final_outcome_reason or resolved_reason
    elif normalized_status not in {
        CandidateStatus.NOT_HIRED,
        CandidateStatus.HIRED,
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
    }:
        candidate.final_outcome = None
        candidate.final_outcome_reason = None


def derive_candidate_journey_state(
    *,
    candidate_status: Optional[CandidateStatus | str],
    lifecycle_state: Optional[str],
    reschedule_requested: bool = False,
) -> str:
    if lifecycle_state == LIFECYCLE_ARCHIVED:
        return "archived_negative"

    slug = candidate_status.value if isinstance(candidate_status, CandidateStatus) else str(candidate_status or "").strip().lower()
    if not slug:
        return "lead"
    if slug == CandidateStatus.INTERVIEW_SCHEDULED.value:
        return "slot_agreed"
    if slug == CandidateStatus.SLOT_PENDING.value and reschedule_requested:
        return "requested_other_slot"
    if slug == CandidateStatus.SLOT_PENDING.value:
        return "time_proposed_waiting_candidate"
    if slug == CandidateStatus.TEST2_SENT.value:
        return "test2_sent_waiting"
    if slug == CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY.value:
        return "intro_preconfirmed"
    if slug == CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF.value:
        return "intro_day_confirmed_day_of"
    return slug


def build_archive_payload(candidate: "User") -> Optional[dict[str, Any]]:
    lifecycle_state = str(getattr(candidate, "lifecycle_state", "") or "").strip().lower()
    if lifecycle_state != LIFECYCLE_ARCHIVED:
        return None
    return {
        "state": lifecycle_state,
        "label": lifecycle_label(lifecycle_state),
        "stage": getattr(candidate, "archive_stage", None),
        "stage_label": archive_stage_label(getattr(candidate, "archive_stage", None)),
        "reason": getattr(candidate, "archive_reason", None),
        "archived_at": getattr(candidate, "archived_at", None).isoformat()
        if getattr(candidate, "archived_at", None)
        else None,
    }


def build_candidate_journey(
    candidate: "User",
    *,
    reschedule_intent: Optional["RescheduleIntent"] = None,
    responsible_recruiter: Optional["Recruiter"] = None,
    upcoming_slot: Optional["Slot"] = None,
) -> dict[str, Any]:
    effective_status = _normalize_intro_day_status(
        getattr(candidate, "candidate_status", None),
        upcoming_slot,
    )
    state = derive_candidate_journey_state(
        candidate_status=effective_status,
        lifecycle_state=getattr(candidate, "lifecycle_state", None),
        reschedule_requested=bool(reschedule_intent and getattr(reschedule_intent, "requested", False)),
    )
    owner = None
    if responsible_recruiter is not None:
        owner = {
            "type": "recruiter",
            "id": getattr(responsible_recruiter, "id", None),
            "name": getattr(responsible_recruiter, "name", None),
        }

    events = [
        serialize_journey_event(event)
        for event in sorted(
            list(getattr(candidate, "journey_events", []) or []),
            key=lambda item: getattr(item, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
    ]
    final_outcome = str(getattr(candidate, "final_outcome", "") or "").strip().lower() or None
    payload = {
        "state": state,
        "state_label": journey_state_label(state),
        "lifecycle_state": getattr(candidate, "lifecycle_state", None),
        "lifecycle_label": lifecycle_label(getattr(candidate, "lifecycle_state", None)),
        "archive": build_archive_payload(candidate),
        "final_outcome": final_outcome,
        "final_outcome_label": final_outcome_label(final_outcome),
        "final_outcome_reason": getattr(candidate, "final_outcome_reason", None),
        "manual_mode": manual_mode_for_candidate(candidate),
        "pending_slot_request": serialize_pending_slot_request(reschedule_intent),
        "current_owner": owner,
        "next_slot_at": getattr(upcoming_slot, "start_utc", None).isoformat()
        if upcoming_slot is not None and getattr(upcoming_slot, "start_utc", None)
        else None,
        "events": events,
    }
    return payload
