from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set

from backend.domain.candidates.models import User


class WorkflowStatus(str, Enum):
    WAITING_FOR_SLOT = "WAITING_FOR_SLOT"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    INTERVIEW_CONFIRMED = "INTERVIEW_CONFIRMED"
    INTERVIEW_COMPLETED = "INTERVIEW_COMPLETED"
    TEST_SENT = "TEST_SENT"
    ONBOARDING_DAY_SCHEDULED = "ONBOARDING_DAY_SCHEDULED"
    ONBOARDING_DAY_CONFIRMED = "ONBOARDING_DAY_CONFIRMED"
    REJECTED = "REJECTED"


class WorkflowAction(str, Enum):
    ASSIGN_SLOT = "assign-slot"
    CONFIRM_INTERVIEW = "confirm-interview"
    COMPLETE_INTERVIEW = "complete-interview"
    SEND_TEST = "send-test"
    SCHEDULE_ONBOARDING = "schedule-onboarding"
    CONFIRM_ONBOARDING = "confirm-onboarding"
    REJECT = "reject"


TRANSITIONS: Dict[WorkflowStatus, Set[WorkflowStatus]] = {
    WorkflowStatus.WAITING_FOR_SLOT: {
        WorkflowStatus.INTERVIEW_SCHEDULED,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.INTERVIEW_SCHEDULED: {
        WorkflowStatus.INTERVIEW_CONFIRMED,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.INTERVIEW_CONFIRMED: {
        WorkflowStatus.INTERVIEW_COMPLETED,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.INTERVIEW_COMPLETED: {
        WorkflowStatus.TEST_SENT,
        WorkflowStatus.ONBOARDING_DAY_SCHEDULED,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.TEST_SENT: {
        WorkflowStatus.ONBOARDING_DAY_SCHEDULED,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.ONBOARDING_DAY_SCHEDULED: {
        WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.ONBOARDING_DAY_CONFIRMED: {
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.REJECTED: set(),
}


ACTION_TARGETS: Dict[WorkflowAction, WorkflowStatus] = {
    WorkflowAction.ASSIGN_SLOT: WorkflowStatus.INTERVIEW_SCHEDULED,
    WorkflowAction.CONFIRM_INTERVIEW: WorkflowStatus.INTERVIEW_CONFIRMED,
    WorkflowAction.COMPLETE_INTERVIEW: WorkflowStatus.INTERVIEW_COMPLETED,
    WorkflowAction.SEND_TEST: WorkflowStatus.TEST_SENT,
    WorkflowAction.SCHEDULE_ONBOARDING: WorkflowStatus.ONBOARDING_DAY_SCHEDULED,
    WorkflowAction.CONFIRM_ONBOARDING: WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
    WorkflowAction.REJECT: WorkflowStatus.REJECTED,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CandidateStateDTO:
    status: WorkflowStatus
    allowed_actions: List[str]
    rejection_stage: Optional[WorkflowStatus] = None


class WorkflowConflict(Exception):
    """Raised when a transition is not allowed."""

    def __init__(self, message: str, *, current: WorkflowStatus, allowed: List[str]):
        super().__init__(message)
        self.current = current
        self.allowed = allowed


class CandidateWorkflowService:
    """Core state-machine for candidate workflow."""

    def __init__(self) -> None:
        self.default_status = WorkflowStatus.WAITING_FOR_SLOT

    def _allowed_actions(self, status: WorkflowStatus) -> List[str]:
        allowed_statuses = TRANSITIONS.get(status, set())
        actions = []
        for action, target in ACTION_TARGETS.items():
            if target in allowed_statuses:
                actions.append(action.value)
        return actions

    def describe(self, candidate: User) -> CandidateStateDTO:
        status = self._current(candidate)
        return CandidateStateDTO(
            status=status,
            allowed_actions=self._allowed_actions(status),
            rejection_stage=getattr(candidate, "rejection_stage", None),
        )

    def _current(self, candidate: User) -> WorkflowStatus:
        raw = getattr(candidate, "workflow_status", None)
        try:
            return WorkflowStatus(raw) if raw else self.default_status
        except Exception:
            return self.default_status

    def transition(
        self,
        candidate: User,
        action: WorkflowAction,
        *,
        actor: Optional[str] = None,
    ) -> CandidateStateDTO:
        current = self._current(candidate)
        target = ACTION_TARGETS[action]
        allowed = TRANSITIONS.get(current, set())

        if target not in allowed:
            raise WorkflowConflict(
                f"Недопустимый переход {current.value} -> {target.value}",
                current=current,
                allowed=self._allowed_actions(current),
            )

        if target == WorkflowStatus.REJECTED:
            candidate.rejection_stage = current.value
            candidate.rejected_at = _utcnow()
            candidate.rejected_by = actor or "admin"

        candidate.workflow_status = target.value
        candidate.status_changed_at = _utcnow()

        return self.describe(candidate)


@dataclass
class UnifiedStatus:
    """Unified status for UI display."""

    status: WorkflowStatus
    label: str
    badge_class: str  # CSS class for styling


# Human-readable labels for workflow statuses
WORKFLOW_STATUS_LABELS: Dict[WorkflowStatus, str] = {
    WorkflowStatus.WAITING_FOR_SLOT: "Ожидает слот",
    WorkflowStatus.INTERVIEW_SCHEDULED: "Интервью назначено",
    WorkflowStatus.INTERVIEW_CONFIRMED: "Интервью подтверждено",
    WorkflowStatus.INTERVIEW_COMPLETED: "Интервью завершено",
    WorkflowStatus.TEST_SENT: "Тест отправлен",
    WorkflowStatus.ONBOARDING_DAY_SCHEDULED: "ОД назначен",
    WorkflowStatus.ONBOARDING_DAY_CONFIRMED: "ОД подтверждён",
    WorkflowStatus.REJECTED: "Отклонён",
}


# CSS badge classes for status display
WORKFLOW_STATUS_BADGES: Dict[WorkflowStatus, str] = {
    WorkflowStatus.WAITING_FOR_SLOT: "badge-warning",
    WorkflowStatus.INTERVIEW_SCHEDULED: "badge-info",
    WorkflowStatus.INTERVIEW_CONFIRMED: "badge-primary",
    WorkflowStatus.INTERVIEW_COMPLETED: "badge-success",
    WorkflowStatus.TEST_SENT: "badge-info",
    WorkflowStatus.ONBOARDING_DAY_SCHEDULED: "badge-primary",
    WorkflowStatus.ONBOARDING_DAY_CONFIRMED: "badge-success",
    WorkflowStatus.REJECTED: "badge-danger",
}


# Legacy candidate_status to workflow_status mapping
LEGACY_STATUS_MAPPING: Dict[str, WorkflowStatus] = {
    "waiting_slot": WorkflowStatus.WAITING_FOR_SLOT,
    "stalled_waiting_slot": WorkflowStatus.WAITING_FOR_SLOT,
    "interview_scheduled": WorkflowStatus.INTERVIEW_SCHEDULED,
    "interview_confirmed": WorkflowStatus.INTERVIEW_CONFIRMED,
    "interview_declined": WorkflowStatus.REJECTED,
    "test2_sent": WorkflowStatus.TEST_SENT,
    "test2_completed": WorkflowStatus.ONBOARDING_DAY_SCHEDULED,
    "test2_failed": WorkflowStatus.REJECTED,
    "intro_day_scheduled": WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
    "intro_day_confirmed_preliminary": WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
    "intro_day_declined_invitation": WorkflowStatus.REJECTED,
    "intro_day_declined_day_of": WorkflowStatus.REJECTED,
    "hired": WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
    "not_hired": WorkflowStatus.REJECTED,
}


def unified_status(candidate: User) -> UnifiedStatus:
    """Get unified status for a candidate, preferring workflow_status over legacy.

    This is the single source of truth for status display in UI.
    Falls back to mapping from legacy candidate_status if workflow_status is not set.
    """
    # Try workflow_status first (new system)
    raw_workflow = getattr(candidate, "workflow_status", None)
    if raw_workflow:
        try:
            status = WorkflowStatus(raw_workflow)
            return UnifiedStatus(
                status=status,
                label=WORKFLOW_STATUS_LABELS.get(status, raw_workflow),
                badge_class=WORKFLOW_STATUS_BADGES.get(status, "badge-secondary"),
            )
        except ValueError:
            pass

    # Fall back to legacy candidate_status
    legacy = getattr(candidate, "candidate_status", None)
    if legacy:
        legacy_value = legacy.value if hasattr(legacy, "value") else str(legacy).lower()
        mapped = LEGACY_STATUS_MAPPING.get(legacy_value)
        if mapped:
            return UnifiedStatus(
                status=mapped,
                label=WORKFLOW_STATUS_LABELS.get(mapped, legacy_value),
                badge_class=WORKFLOW_STATUS_BADGES.get(mapped, "badge-secondary"),
            )

    # Default status
    default = WorkflowStatus.WAITING_FOR_SLOT
    return UnifiedStatus(
        status=default,
        label=WORKFLOW_STATUS_LABELS[default],
        badge_class=WORKFLOW_STATUS_BADGES[default],
    )


__all__ = [
    "CandidateStateDTO",
    "CandidateWorkflowService",
    "LEGACY_STATUS_MAPPING",
    "TRANSITIONS",
    "unified_status",
    "UnifiedStatus",
    "WorkflowAction",
    "WorkflowConflict",
    "WorkflowStatus",
    "WORKFLOW_STATUS_BADGES",
    "WORKFLOW_STATUS_LABELS",
]
