"""Candidate status tracking system.

This module defines the candidate status lifecycle from test completion to hiring.
Statuses help track the recruiting funnel and analyze conversion rates.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, List, Tuple


class CandidateStatus(str, Enum):
    """Candidate status in the recruiting pipeline."""

    # 1. Completed Test1, awaiting slot selection
    TEST1_COMPLETED = "test1_completed"

    # 1.1 Waiting for recruiter-proposed slot (no availability)
    WAITING_SLOT = "waiting_slot"

    # 1.2 Waiting for slot >24h (stalled, needs attention)
    STALLED_WAITING_SLOT = "stalled_waiting_slot"

    # 2. Interview scheduled (slot approved by recruiter)
    INTERVIEW_SCHEDULED = "interview_scheduled"

    # 3. Candidate confirmed interview attendance
    INTERVIEW_CONFIRMED = "interview_confirmed"

    # 4. Candidate declined interview
    INTERVIEW_DECLINED = "interview_declined"

    # 5. Passed interview, Test2 sent
    TEST2_SENT = "test2_sent"

    # 6. Completed Test2, awaiting intro day scheduling
    TEST2_COMPLETED = "test2_completed"

    # 7. Failed Test2
    TEST2_FAILED = "test2_failed"

    # 8. Intro day scheduled
    INTRO_DAY_SCHEDULED = "intro_day_scheduled"

    # 9. Preliminary confirmation for intro day
    INTRO_DAY_CONFIRMED_PRELIMINARY = "intro_day_confirmed_preliminary"

    # 10. Declined intro day invitation
    INTRO_DAY_DECLINED_INVITATION = "intro_day_declined_invitation"

    # 11. Confirmed attendance on intro day (2h before)
    INTRO_DAY_CONFIRMED_DAY_OF = "intro_day_confirmed_day_of"

    # 12. Declined on intro day (2h before)
    INTRO_DAY_DECLINED_DAY_OF = "intro_day_declined_day_of"

    # 13. Hired after intro day (set by recruiter)
    HIRED = "hired"

    # 14. Not hired after intro day (set by recruiter)
    NOT_HIRED = "not_hired"


# Human-readable status labels (Russian)
STATUS_LABELS: Dict[CandidateStatus, str] = {
    CandidateStatus.TEST1_COMPLETED: "Прошел тестирование",
    CandidateStatus.WAITING_SLOT: "Ждет назначения слота",
    CandidateStatus.STALLED_WAITING_SLOT: "Долго ждет слота (>24ч)",
    CandidateStatus.INTERVIEW_SCHEDULED: "Назначено собеседование",
    CandidateStatus.INTERVIEW_CONFIRMED: "Подтвердился (собес)",
    CandidateStatus.INTERVIEW_DECLINED: "Отказ на этапе собеседования",
    CandidateStatus.TEST2_SENT: "Прошел собес (Тест 2)",
    CandidateStatus.TEST2_COMPLETED: "Прошел Тест 2 (ожидает ОД)",
    CandidateStatus.TEST2_FAILED: "Не прошел Тест 2",
    CandidateStatus.INTRO_DAY_SCHEDULED: "Назначен ознакомительный день",
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY: "Предварительно подтвердился (ОД)",
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION: "Отказ на этапе ОД (приглашение)",
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF: "Подтвердился (ОД в день)",
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: "Отказ (ОД в день)",
    CandidateStatus.HIRED: "Закреплен на обучение",
    CandidateStatus.NOT_HIRED: "Не закреплен",
}


# Status categories for grouping and filtering
class StatusCategory(str, Enum):
    """High-level status categories for analytics."""

    TESTING = "testing"  # Test1 and Test2 phases
    INTERVIEW = "interview"  # Interview scheduling and execution
    INTRO_DAY = "intro_day"  # Intro day scheduling and execution
    HIRED = "hired"  # Final hiring decision
    DECLINED = "declined"  # Declined at any stage


# Map each status to its category
STATUS_CATEGORIES: Dict[CandidateStatus, StatusCategory] = {
    CandidateStatus.TEST1_COMPLETED: StatusCategory.TESTING,
    CandidateStatus.WAITING_SLOT: StatusCategory.TESTING,
    CandidateStatus.STALLED_WAITING_SLOT: StatusCategory.TESTING,
    CandidateStatus.INTERVIEW_SCHEDULED: StatusCategory.INTERVIEW,
    CandidateStatus.INTERVIEW_CONFIRMED: StatusCategory.INTERVIEW,
    CandidateStatus.INTERVIEW_DECLINED: StatusCategory.DECLINED,
    CandidateStatus.TEST2_SENT: StatusCategory.TESTING,
    CandidateStatus.TEST2_COMPLETED: StatusCategory.TESTING,
    CandidateStatus.TEST2_FAILED: StatusCategory.DECLINED,
    CandidateStatus.INTRO_DAY_SCHEDULED: StatusCategory.INTRO_DAY,
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY: StatusCategory.INTRO_DAY,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION: StatusCategory.DECLINED,
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF: StatusCategory.INTRO_DAY,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: StatusCategory.DECLINED,
    CandidateStatus.HIRED: StatusCategory.HIRED,
    CandidateStatus.NOT_HIRED: StatusCategory.DECLINED,
}


# Visual colors for UI representation
STATUS_COLORS: Dict[CandidateStatus, str] = {
    CandidateStatus.TEST1_COMPLETED: "info",  # Blue
    CandidateStatus.WAITING_SLOT: "warning",  # Amber
    CandidateStatus.STALLED_WAITING_SLOT: "danger",  # Red (needs attention)
    CandidateStatus.INTERVIEW_SCHEDULED: "primary",  # Blue
    CandidateStatus.INTERVIEW_CONFIRMED: "success",  # Green
    CandidateStatus.INTERVIEW_DECLINED: "danger",  # Red
    CandidateStatus.TEST2_SENT: "primary",  # Blue
    CandidateStatus.TEST2_COMPLETED: "info",  # Blue
    CandidateStatus.TEST2_FAILED: "danger",  # Red
    CandidateStatus.INTRO_DAY_SCHEDULED: "primary",  # Blue
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY: "success",  # Green
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION: "danger",  # Red
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF: "success",  # Green
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: "danger",  # Red
    CandidateStatus.HIRED: "success",  # Green
    CandidateStatus.NOT_HIRED: "warning",  # Yellow/Orange
}


# Valid status transitions
# Maps current status to list of allowed next statuses
STATUS_TRANSITIONS: Dict[CandidateStatus, List[CandidateStatus]] = {
    CandidateStatus.TEST1_COMPLETED: [
        CandidateStatus.WAITING_SLOT,
        CandidateStatus.INTERVIEW_SCHEDULED,
    ],
    CandidateStatus.WAITING_SLOT: [
        CandidateStatus.STALLED_WAITING_SLOT,
        CandidateStatus.INTERVIEW_SCHEDULED,
    ],
    CandidateStatus.STALLED_WAITING_SLOT: [
        CandidateStatus.INTERVIEW_SCHEDULED,
    ],
    CandidateStatus.INTERVIEW_SCHEDULED: [
        CandidateStatus.INTERVIEW_CONFIRMED,
        CandidateStatus.INTERVIEW_DECLINED,
        CandidateStatus.TEST2_SENT,  # If recruiter approves without confirmation
    ],
    CandidateStatus.INTERVIEW_CONFIRMED: [
        CandidateStatus.TEST2_SENT,
        CandidateStatus.INTERVIEW_DECLINED,  # No-show or cancellation
    ],
    CandidateStatus.INTERVIEW_DECLINED: [],  # Terminal state
    CandidateStatus.TEST2_SENT: [
        CandidateStatus.TEST2_COMPLETED,
        CandidateStatus.TEST2_FAILED,
    ],
    CandidateStatus.TEST2_COMPLETED: [
        CandidateStatus.INTRO_DAY_SCHEDULED,
    ],
    CandidateStatus.TEST2_FAILED: [],  # Terminal state
    CandidateStatus.INTRO_DAY_SCHEDULED: [
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
    ],
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY: [
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
        CandidateStatus.HIRED,  # Direct hire without day-of confirmation
        CandidateStatus.NOT_HIRED,
    ],
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION: [],  # Terminal state
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF: [
        CandidateStatus.HIRED,
        CandidateStatus.NOT_HIRED,
    ],
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: [],  # Terminal state
    CandidateStatus.HIRED: [],  # Terminal state
    CandidateStatus.NOT_HIRED: [],  # Terminal state
}

STATUS_PROGRESS_SEQUENCE: List[CandidateStatus] = [
    CandidateStatus.TEST1_COMPLETED,
    CandidateStatus.WAITING_SLOT,
    CandidateStatus.STALLED_WAITING_SLOT,
    CandidateStatus.INTERVIEW_SCHEDULED,
    CandidateStatus.INTERVIEW_CONFIRMED,
    CandidateStatus.INTERVIEW_DECLINED,
    CandidateStatus.TEST2_SENT,
    CandidateStatus.TEST2_COMPLETED,
    CandidateStatus.TEST2_FAILED,
    CandidateStatus.INTRO_DAY_SCHEDULED,
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
    CandidateStatus.HIRED,
    CandidateStatus.NOT_HIRED,
]

STATUS_PROGRESS_INDEX: Dict[CandidateStatus, int] = {
    status: idx for idx, status in enumerate(STATUS_PROGRESS_SEQUENCE)
}


def get_status_label(status: Optional[CandidateStatus]) -> str:
    """Get human-readable label for status."""
    if status is None:
        return "Нет статуса"
    return STATUS_LABELS.get(status, str(status))


def get_status_color(status: Optional[CandidateStatus]) -> str:
    """Get CSS color class for status."""
    if status is None:
        return "secondary"
    return STATUS_COLORS.get(status, "secondary")


def get_status_category(status: CandidateStatus) -> StatusCategory:
    """Get category for status."""
    return STATUS_CATEGORIES.get(status, StatusCategory.TESTING)


def can_transition(from_status: Optional[CandidateStatus], to_status: CandidateStatus) -> bool:
    """Check if status transition is valid."""
    if from_status is None:
        # New candidate can only start from TEST1_COMPLETED
        return to_status == CandidateStatus.TEST1_COMPLETED

    allowed = STATUS_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def get_next_statuses(current_status: Optional[CandidateStatus]) -> List[Tuple[CandidateStatus, str]]:
    """Get list of allowed next statuses with labels."""
    if current_status is None:
        return [(CandidateStatus.TEST1_COMPLETED, STATUS_LABELS[CandidateStatus.TEST1_COMPLETED])]

    allowed = STATUS_TRANSITIONS.get(current_status, [])
    return [(status, STATUS_LABELS[status]) for status in allowed]


def is_terminal_status(status: CandidateStatus) -> bool:
    """Check if status is terminal (no further transitions)."""
    return len(STATUS_TRANSITIONS.get(status, [])) == 0


def is_status_retreat(current: Optional[CandidateStatus], target: CandidateStatus) -> bool:
    """Return True if target is behind the current status in the linear pipeline."""
    if current is None:
        return False
    return STATUS_PROGRESS_INDEX.get(current, -1) > STATUS_PROGRESS_INDEX.get(target, -1)


def get_funnel_stages() -> List[Tuple[str, List[CandidateStatus]]]:
    """Get recruiting funnel stages with their statuses."""
    return [
        ("Тестирование", [
            CandidateStatus.TEST1_COMPLETED,
            CandidateStatus.TEST2_SENT,
            CandidateStatus.TEST2_COMPLETED,
            CandidateStatus.TEST2_FAILED,
        ]),
        ("Собеседование", [
            CandidateStatus.INTERVIEW_SCHEDULED,
            CandidateStatus.INTERVIEW_CONFIRMED,
            CandidateStatus.INTERVIEW_DECLINED,
        ]),
        ("Ознакомительный день", [
            CandidateStatus.INTRO_DAY_SCHEDULED,
            CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
            CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
            CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
            CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
        ]),
        ("Итог", [
            CandidateStatus.HIRED,
            CandidateStatus.NOT_HIRED,
        ]),
    ]


__all__ = [
    "CandidateStatus",
    "StatusCategory",
    "STATUS_LABELS",
    "STATUS_CATEGORIES",
    "STATUS_COLORS",
    "STATUS_TRANSITIONS",
    "STATUS_PROGRESS_SEQUENCE",
    "STATUS_PROGRESS_INDEX",
    "get_status_label",
    "get_status_color",
    "get_status_category",
    "can_transition",
    "is_status_retreat",
    "get_next_statuses",
    "is_terminal_status",
    "get_funnel_stages",
]
