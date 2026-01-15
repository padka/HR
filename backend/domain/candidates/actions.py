"""Candidate action configuration based on current status.

This module defines available actions for each candidate status.
UI should use this mapping instead of hardcoding action logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from backend.domain.candidates.status import CandidateStatus


@dataclass
class CandidateAction:
    """Represents an action available for a candidate."""

    key: str  # Unique action identifier
    label: str  # UI display text
    url_pattern: str  # URL pattern (/candidates/{id}/action) or status slug for POST
    icon: Optional[str] = None  # Optional icon/emoji
    variant: str = "primary"  # Button variant: primary, secondary, danger, ghost
    requires_slot: bool = False  # Action needs upcoming slot
    requires_test2_passed: bool = False  # Action needs test2 passed
    confirmation: Optional[str] = None  # Optional confirmation message
    method: str = "GET"  # HTTP method: GET (navigation) or POST (status update)
    target_status: Optional[str] = None  # Target status for POST actions


# Available actions mapped to statuses
STATUS_ACTIONS: Dict[CandidateStatus, List[CandidateAction]] = {
    # Lead stages
    CandidateStatus.LEAD: [
        CandidateAction(
            key="contact",
            label="Связаться",
            url_pattern="/candidates/{id}/contact",
            icon="📞",
            variant="primary",
        ),
    ],
    CandidateStatus.CONTACTED: [
        CandidateAction(
            key="invite_bot",
            label="Пригласить в бота",
            url_pattern="/candidates/{id}/invite",
            icon="💬",
            variant="primary",
        ),
    ],

    # Post-Test1 stages
    CandidateStatus.TEST1_COMPLETED: [
        CandidateAction(
            key="schedule_interview",
            label="Назначить собеседование",
            url_pattern="/candidates/{id}/schedule-slot",
            icon="🕒",
            variant="primary",
            method="GET",
        ),
        CandidateAction(
            key="reject",
            label="Отказ",
            url_pattern="/api/candidates/{id}/actions/reject",
            icon="🚫",
            variant="ghost",
            confirmation="Отклонить кандидата?",
            method="POST",
            target_status="interview_declined",
        ),
    ],

    CandidateStatus.WAITING_SLOT: [
        CandidateAction(
            key="schedule_interview",
            label="Предложить время собеседования",
            url_pattern="/candidates/{id}/schedule-slot",
            icon="🕒",
            variant="primary",
        ),
    ],

    CandidateStatus.STALLED_WAITING_SLOT: [
        CandidateAction(
            key="schedule_interview",
            label="СРОЧНО: Предложить время",
            url_pattern="/candidates/{id}/schedule-slot",
            icon="⚠️",
            variant="danger",
        ),
    ],

    # Interview stages
    CandidateStatus.INTERVIEW_SCHEDULED: [
        CandidateAction(
            key="reschedule_interview",
            label="Перенести собеседование",
            url_pattern="/candidates/{id}/schedule-slot",
            icon="🕒",
            variant="secondary",
        ),
        CandidateAction(
            key="interview_outcome_passed",
            label="Исход: прошел (отправить Тест 2)",
            url_pattern="/api/candidates/{id}/actions/interview_outcome_passed",
            icon="✅",
            variant="primary",
            method="POST",
            target_status="test2_sent",
            requires_slot=True,
            confirmation="Отправить кандидату Тест 2?",
        ),
        CandidateAction(
            key="interview_outcome_failed",
            label="Исход: не прошел",
            url_pattern="/api/candidates/{id}/actions/interview_outcome_failed",
            icon="⛔️",
            variant="ghost",
            method="POST",
            target_status="interview_declined",
            requires_slot=True,
            confirmation="Пометить как не прошедшего собеседование?",
        ),
    ],

    CandidateStatus.INTERVIEW_CONFIRMED: [
        CandidateAction(
            key="interview_passed",
            label="Прошел собеседование (отправить Тест 2)",
            url_pattern="/api/candidates/{id}/actions/interview_passed",
            icon="✅",
            variant="primary",
            method="POST",
            target_status="test2_sent",
            confirmation="Отправить кандидату Тест 2?",
        ),
        CandidateAction(
            key="interview_declined",
            label="Отклонить после собеседования",
            url_pattern="/api/candidates/{id}/actions/interview_declined",
            icon="⛔️",
            variant="danger",
            method="POST",
            target_status="interview_declined",
            confirmation="Подтвердите отказ после собеседования.",
        ),
        CandidateAction(
            key="reschedule_interview",
            label="Перенести время",
            url_pattern="/candidates/{id}/schedule-slot",
            icon="🕒",
            variant="ghost",
        ),
    ],

    # Test2 stages
    CandidateStatus.TEST2_SENT: [
        CandidateAction(
            key="resend_test2",
            label="Повторно отправить Тест 2",
            url_pattern="/candidates/{id}/resend-test2",
            icon="📤",
            variant="secondary",
        ),
    ],

    CandidateStatus.TEST2_COMPLETED: [
        CandidateAction(
            key="schedule_intro_day",
            label="Назначить ознакомительный день",
            url_pattern="/candidates/{id}/schedule-intro-day",
            icon="📆",
            variant="primary",
            method="GET",
        ),
        CandidateAction(
            key="reject",
            label="Отказ",
            url_pattern="/api/candidates/{id}/actions/reject",
            icon="🚫",
            variant="ghost",
            confirmation="Отклонить кандидата?",
            method="POST",
            target_status="test2_failed",
        ),
    ],

    # Intro day stages
    CandidateStatus.INTRO_DAY_SCHEDULED: [
        CandidateAction(
            key="reschedule_intro_day",
            label="Перенести ознакомительный день",
            url_pattern="/candidates/{id}/schedule-intro-day",
            icon="📆",
            variant="secondary",
        ),
    ],

    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY: [
        CandidateAction(
            key="mark_hired",
            label="Закреплен на обучение",
            url_pattern="/api/candidates/{id}/actions/mark_hired",
            icon="🎉",
            variant="primary",
            method="POST",
            target_status="hired",
        ),
        CandidateAction(
            key="mark_not_hired",
            label="Не закреплен",
            url_pattern="/api/candidates/{id}/actions/mark_not_hired",
            icon="⚠️",
            variant="ghost",
            confirmation="Пометить как не закрепленного?",
            method="POST",
            target_status="not_hired",
        ),
    ],

    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF: [
        CandidateAction(
            key="mark_hired",
            label="Закреплен на обучение",
            url_pattern="/api/candidates/{id}/actions/mark_hired",
            icon="🎉",
            variant="primary",
            method="POST",
            target_status="hired",
        ),
        CandidateAction(
            key="mark_not_hired",
            label="Не закреплен",
            url_pattern="/api/candidates/{id}/actions/mark_not_hired",
            icon="⚠️",
            variant="ghost",
            confirmation="Пометить как не закрепленного?",
            method="POST",
            target_status="not_hired",
        ),
        CandidateAction(
            key="decline_after_intro",
            label="Отказ",
            url_pattern="/api/candidates/{id}/actions/decline_after_intro",
            icon="⛔️",
            variant="ghost",
            confirmation="Отказать кандидату после ОД?",
            method="POST",
            target_status="intro_day_declined_day_of",
        ),
    ],

    # Terminal states - no actions
    CandidateStatus.INTERVIEW_DECLINED: [],
    CandidateStatus.TEST2_FAILED: [],
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION: [],
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: [],
    CandidateStatus.HIRED: [],
    CandidateStatus.NOT_HIRED: [],
}


def get_candidate_actions(
    status: Optional[CandidateStatus],
    *,
    has_upcoming_slot: bool = False,
    has_test2_passed: bool = False,
    has_intro_day_slot: bool = False,
) -> List[CandidateAction]:
    """Get list of available actions for candidate based on current state.

    Args:
        status: Current candidate status
        has_upcoming_slot: Whether candidate has an upcoming slot booked
        has_test2_passed: Whether candidate passed Test2
        has_intro_day_slot: Whether intro day slot already exists

    Returns:
        List of actions available in current state
    """
    if status is None:
        return []

    actions = STATUS_ACTIONS.get(status, [])

    # Filter actions based on additional conditions
    filtered_actions = []
    for action in actions:
        # Skip intro day scheduling if already scheduled
        if action.key == "schedule_intro_day" and has_intro_day_slot:
            continue

        # Skip actions requiring slot if no slot
        if action.requires_slot and not has_upcoming_slot:
            continue

        # Skip actions requiring test2 if not passed
        if action.requires_test2_passed and not has_test2_passed:
            continue

        filtered_actions.append(action)

    return filtered_actions


__all__ = [
    "CandidateAction",
    "STATUS_ACTIONS",
    "get_candidate_actions",
]
