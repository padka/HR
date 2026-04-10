"""Canonical recruiter write-intent contract for candidate lifecycle operations.

This module defines read/write-aligned intent keys used by recruiter-facing UI.
It deliberately stays additive: legacy status fields still exist, but UI-facing
write semantics should go through these intent mappings instead of raw storage
statuses wherever safe.
"""

from __future__ import annotations

from typing import Optional, Tuple

from backend.domain.candidates.state_contract import KANBAN_COLUMN_TARGET_STATUSES
from backend.domain.candidates.status import CandidateStatus


ACTION_INTENT_BY_KEY = {
    "approve_upcoming_slot": "approve_slot",
    "interview_outcome_passed": "send_to_test2",
    "interview_passed": "send_to_test2",
    "interview_outcome_failed": "decline_after_interview",
    "interview_declined": "decline_after_interview",
    "reject": "reject_candidate",
    "mark_hired": "finalize_hired",
    "mark_not_hired": "finalize_not_hired",
    "decline_after_intro": "decline_intro_day",
}

KANBAN_MOVE_INTENT_BY_COLUMN = {
    "interview_confirmed": "mark_interview_confirmed",
    "test2_sent": "send_to_test2",
    "test2_completed": "mark_test2_completed",
    "intro_day_confirmed_preliminary": "confirm_intro_day_preliminary",
    "intro_day_confirmed_day_of": "confirm_intro_day_day_of",
}

KANBAN_CANONICAL_MOVE_COLUMNS = frozenset(KANBAN_MOVE_INTENT_BY_COLUMN.keys())

INTERVIEW_SCHEDULING_REQUIRED_COLUMNS = frozenset({
    "interview_confirmed",
    "test2_sent",
})

INTRO_DAY_SCHEDULING_REQUIRED_COLUMNS = frozenset({
    "intro_day_confirmed_preliminary",
    "intro_day_confirmed_day_of",
})

SCHEDULING_SENSITIVE_ACTION_KEYS = frozenset({
    "approve_upcoming_slot",
    "interview_outcome_passed",
    "interview_passed",
    "interview_outcome_failed",
    "interview_declined",
})


def resolve_action_intent_key(action_key: str) -> str:
    normalized = str(action_key or "").strip().lower()
    return ACTION_INTENT_BY_KEY.get(normalized, normalized or "legacy_status_bridge")


def resolve_action_target_status(
    action_key: str,
    *,
    current_status_slug: Optional[str],
    fallback_target_status: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    normalized_key = str(action_key or "").strip().lower()
    current_status = str(current_status_slug or "").strip().lower() or None
    fallback = str(fallback_target_status or "").strip().lower() or None

    if normalized_key in {"interview_outcome_passed", "interview_passed"}:
        return CandidateStatus.TEST2_SENT.value, "action_intent"
    if normalized_key in {"interview_outcome_failed", "interview_declined"}:
        return CandidateStatus.INTERVIEW_DECLINED.value, "action_intent"
    if normalized_key == "mark_hired":
        return CandidateStatus.HIRED.value, "action_intent"
    if normalized_key == "mark_not_hired":
        return CandidateStatus.NOT_HIRED.value, "action_intent"
    if normalized_key == "decline_after_intro":
        return CandidateStatus.INTRO_DAY_DECLINED_DAY_OF.value, "action_intent"
    if normalized_key == "reject":
        if current_status == CandidateStatus.TEST2_COMPLETED.value:
            return CandidateStatus.TEST2_FAILED.value, "action_intent"
        return CandidateStatus.INTERVIEW_DECLINED.value, "action_intent"
    if fallback:
        return fallback, "legacy_target_status"
    return None, "unresolved"


def resolve_kanban_move_intent(column_slug: str) -> str:
    normalized = str(column_slug or "").strip().lower()
    return KANBAN_MOVE_INTENT_BY_COLUMN.get(normalized, "unsupported_kanban_move")


def resolve_kanban_target_status(column_slug: str) -> Optional[str]:
    normalized = str(column_slug or "").strip().lower()
    return KANBAN_COLUMN_TARGET_STATUSES.get(normalized)


def is_supported_kanban_move_column(column_slug: str) -> bool:
    normalized = str(column_slug or "").strip().lower()
    return normalized in KANBAN_CANONICAL_MOVE_COLUMNS

