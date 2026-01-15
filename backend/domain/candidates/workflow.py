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


__all__ = [
    "WorkflowStatus",
    "WorkflowAction",
    "TRANSITIONS",
    "CandidateWorkflowService",
    "CandidateStateDTO",
    "WorkflowConflict",
]
