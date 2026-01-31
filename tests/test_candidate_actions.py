"""Test candidate action system for simplified card."""
import pytest

from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.actions import (
    CandidateAction,
    STATUS_ACTIONS,
    get_candidate_actions,
)


def test_status_actions_mapping_complete():
    """Verify all statuses that need actions have them defined."""
    # Statuses that should have actions (not terminal states)
    active_statuses = [
        CandidateStatus.LEAD,
        CandidateStatus.CONTACTED,
        CandidateStatus.TEST1_COMPLETED,
        CandidateStatus.WAITING_SLOT,
        CandidateStatus.STALLED_WAITING_SLOT,
        CandidateStatus.INTERVIEW_SCHEDULED,
        CandidateStatus.INTERVIEW_CONFIRMED,
        CandidateStatus.TEST2_SENT,
        CandidateStatus.TEST2_COMPLETED,
        CandidateStatus.INTRO_DAY_SCHEDULED,
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
    ]

    for status in active_statuses:
        assert status in STATUS_ACTIONS, f"Status {status} missing actions"
        actions = STATUS_ACTIONS[status]
        assert len(actions) > 0, f"Status {status} has no actions"


def test_terminal_statuses_have_no_actions():
    """Terminal statuses should have empty action lists."""
    terminal_statuses = [
        CandidateStatus.INTERVIEW_DECLINED,
        CandidateStatus.TEST2_FAILED,
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
        CandidateStatus.HIRED,
        CandidateStatus.NOT_HIRED,
    ]

    for status in terminal_statuses:
        actions = STATUS_ACTIONS.get(status, [])
        assert len(actions) == 0, f"Terminal status {status} should have no actions"


def test_action_structure():
    """Verify all actions have required fields."""
    for status, actions in STATUS_ACTIONS.items():
        for action in actions:
            assert isinstance(action, CandidateAction)
            assert action.key, f"Action in {status} missing key"
            assert action.label, f"Action in {status} missing label"
            assert action.url_pattern, f"Action in {status} missing url_pattern"
            assert "{id}" in action.url_pattern, f"URL pattern should contain {{id}}: {action.url_pattern}"
            assert action.variant in ["primary", "secondary", "danger", "ghost"], \
                f"Invalid variant: {action.variant}"


def test_get_candidate_actions_test1_completed():
    """Test actions for TEST1_COMPLETED status."""
    actions = get_candidate_actions(
        CandidateStatus.TEST1_COMPLETED,
        has_upcoming_slot=False,
        has_test2_passed=False,
        has_intro_day_slot=False,
    )

    assert len(actions) == 2
    assert any(a.key == "schedule_interview" for a in actions)
    assert any(a.key == "reject" for a in actions)

    # Check schedule interview action
    schedule_action = next(a for a in actions if a.key == "schedule_interview")
    assert schedule_action.icon == "🕒"
    assert schedule_action.variant == "primary"
    assert "/schedule-slot" in schedule_action.url_pattern


def test_get_candidate_actions_test2_completed():
    """Test actions for TEST2_COMPLETED with intro day filtering."""
    # Without intro day slot - should show schedule intro day
    actions = get_candidate_actions(
        CandidateStatus.TEST2_COMPLETED,
        has_upcoming_slot=False,
        has_test2_passed=True,
        has_intro_day_slot=False,
    )

    assert len(actions) == 2
    assert any(a.key == "schedule_intro_day" for a in actions)
    assert any(a.key == "reject" for a in actions)

    # With intro day slot - should hide schedule intro day
    actions_with_slot = get_candidate_actions(
        CandidateStatus.TEST2_COMPLETED,
        has_upcoming_slot=False,
        has_test2_passed=True,
        has_intro_day_slot=True,
    )

    # Should only have reject action, schedule_intro_day filtered out
    assert len(actions_with_slot) == 1
    assert not any(a.key == "schedule_intro_day" for a in actions_with_slot)


def test_get_candidate_actions_stalled_waiting_slot():
    """Test urgent actions for stalled candidates."""
    actions = get_candidate_actions(
        CandidateStatus.STALLED_WAITING_SLOT,
        has_upcoming_slot=False,
        has_test2_passed=False,
        has_intro_day_slot=False,
    )

    assert len(actions) == 2
    schedule_action = next(a for a in actions if a.key == "schedule_interview")
    assert schedule_action.variant == "danger"  # Urgent!
    assert "СРОЧНО" in schedule_action.label
    assert schedule_action.icon == "⚠️"
    assert any(a.key == "reject" for a in actions)


def test_get_candidate_actions_intro_day_confirmed():
    """Test actions for intro day confirmation."""
    actions = get_candidate_actions(
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
        has_upcoming_slot=False,
        has_test2_passed=False,
        has_intro_day_slot=True,
    )

    assert len(actions) == 3
    assert any(a.key == "mark_hired" for a in actions)
    assert any(a.key == "mark_not_hired" for a in actions)
    assert any(a.key == "decline_after_intro" for a in actions)

    # Check that dangerous actions have confirmation
    decline_action = next(a for a in actions if a.key == "decline_after_intro")
    assert decline_action.confirmation is not None
    assert "?" in decline_action.confirmation


def test_get_candidate_actions_none_status():
    """Test that None status returns empty list."""
    actions = get_candidate_actions(None)
    assert actions == []


def test_get_candidate_actions_lead_status():
    """Test actions for LEAD status."""
    actions = get_candidate_actions(
        CandidateStatus.LEAD,
        has_upcoming_slot=False,
        has_test2_passed=False,
        has_intro_day_slot=False,
    )

    assert len(actions) == 1
    contact_action = actions[0]
    assert contact_action.key == "contact"
    assert contact_action.label == "Связаться"
    assert contact_action.icon == "📞"


def test_confirmation_messages():
    """Verify dangerous actions have confirmation messages."""
    dangerous_keys = ["reject", "decline_after_intro", "mark_not_hired"]

    for status, actions in STATUS_ACTIONS.items():
        for action in actions:
            if action.key in dangerous_keys:
                assert action.confirmation is not None, \
                    f"Dangerous action {action.key} in {status} should have confirmation"

            # Ghost/danger variants should have appropriate confirmations
            if action.variant in ["danger", "ghost"] and action.key in dangerous_keys:
                assert action.confirmation is not None


def test_url_patterns_correct():
    """Verify URL patterns are properly formatted."""
    expected_patterns = {
        "schedule_interview": "/candidates/{id}/schedule-slot",
        "schedule_intro_day": "/candidates/{id}/schedule-intro-day",
        "reschedule_interview": "/candidates/{id}/schedule-slot",
        "resend_test2": "/candidates/{id}/resend-test2",
    }

    for status, actions in STATUS_ACTIONS.items():
        for action in actions:
            if action.key in expected_patterns:
                assert action.url_pattern == expected_patterns[action.key], \
                    f"Action {action.key} has wrong URL pattern"
