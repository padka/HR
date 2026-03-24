from datetime import datetime, timezone

import pytest

from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.workflow import (
    CandidateWorkflowService,
    WorkflowAction,
    WorkflowConflict,
    WorkflowStatus,
)


def _candidate(status: WorkflowStatus) -> User:
    return User(
        fio="Test",
        city="Москва",
        workflow_status=status.value,
        status_changed_at=datetime.now(timezone.utc),
    )


def test_allowed_transitions_success():
    svc = CandidateWorkflowService()
    user = _candidate(WorkflowStatus.WAITING_FOR_SLOT)

    state = svc.transition(user, WorkflowAction.ASSIGN_SLOT)
    assert state.status == WorkflowStatus.INTERVIEW_SCHEDULED
    assert WorkflowAction.CONFIRM_INTERVIEW.value in state.allowed_actions


def test_reject_from_any_state_sets_stage_and_meta():
    svc = CandidateWorkflowService()
    user = _candidate(WorkflowStatus.INTERVIEW_COMPLETED)

    state = svc.transition(user, WorkflowAction.REJECT, actor="qa")
    assert state.status == WorkflowStatus.REJECTED
    assert user.rejection_stage == WorkflowStatus.INTERVIEW_COMPLETED.value
    assert user.rejected_at is not None
    assert user.rejected_by == "qa"
    assert state.allowed_actions == []


def test_invalid_transition_raises_conflict():
    svc = CandidateWorkflowService()
    user = _candidate(WorkflowStatus.WAITING_FOR_SLOT)

    with pytest.raises(WorkflowConflict) as exc:
        svc.transition(user, WorkflowAction.CONFIRM_INTERVIEW)

    assert exc.value.current == WorkflowStatus.WAITING_FOR_SLOT
    assert WorkflowAction.ASSIGN_SLOT.value in exc.value.allowed


def test_describe_prefers_candidate_status_when_requested():
    svc = CandidateWorkflowService()
    user = User(
        fio="Test",
        city="Москва",
        candidate_status=CandidateStatus.INTRO_DAY_SCHEDULED,
        workflow_status=WorkflowStatus.INTERVIEW_CONFIRMED.value,
        status_changed_at=datetime.now(timezone.utc),
    )

    state = svc.describe(user, prefer_candidate_status=True)

    assert state.status == WorkflowStatus.ONBOARDING_DAY_SCHEDULED
    assert WorkflowAction.CONFIRM_ONBOARDING.value in state.allowed_actions


def test_describe_accepts_legacy_lowercase_workflow_status():
    svc = CandidateWorkflowService()
    user = _candidate(WorkflowStatus.WAITING_FOR_SLOT)
    user.workflow_status = "waiting_for_slot"

    state = svc.describe(user)

    assert state.status == WorkflowStatus.WAITING_FOR_SLOT
