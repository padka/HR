"""Tests for action URL patterns in actions.py.

These tests verify that all POST actions use the new API endpoint pattern
and don't require database access.
"""
import pytest

from backend.domain.candidates.actions import STATUS_ACTIONS


@pytest.mark.no_db_cleanup
def test_all_post_actions_use_new_api_pattern():
    """Verify that all POST actions use the new /api/candidates/{id}/actions/ pattern."""
    for status, actions in STATUS_ACTIONS.items():
        for action in actions:
            if action.method == "POST":
                assert "/api/candidates/{id}/actions/" in action.url_pattern, (
                    f"POST action '{action.key}' in status '{status}' should use "
                    f"new API pattern '/api/candidates/{{id}}/actions/...', "
                    f"got '{action.url_pattern}'"
                )


@pytest.mark.no_db_cleanup
def test_get_actions_use_ui_pattern():
    """Verify that GET actions use UI navigation patterns (not API)."""
    for status, actions in STATUS_ACTIONS.items():
        for action in actions:
            if action.method == "GET":
                assert "/api/" not in action.url_pattern, (
                    f"GET action '{action.key}' in status '{status}' should use "
                    f"UI navigation pattern, not API pattern. Got '{action.url_pattern}'"
                )
                assert "/candidates/{id}/" in action.url_pattern, (
                    f"GET action '{action.key}' should use UI route pattern"
                )


@pytest.mark.no_db_cleanup
def test_action_keys_are_unique_per_status():
    """Verify that action keys are unique within each status."""
    for status, actions in STATUS_ACTIONS.items():
        keys = [action.key for action in actions]
        assert len(keys) == len(set(keys)), (
            f"Duplicate action keys found in status '{status}': {keys}"
        )


@pytest.mark.no_db_cleanup
def test_post_actions_have_target_status():
    """Verify that POST actions define a target_status."""
    for status, actions in STATUS_ACTIONS.items():
        for action in actions:
            if action.method == "POST":
                assert action.target_status is not None, (
                    f"POST action '{action.key}' in status '{status}' "
                    f"should define target_status"
                )


@pytest.mark.no_db_cleanup
def test_dangerous_actions_have_confirmation():
    """Verify that dangerous actions (reject, decline, etc.) have confirmation messages."""
    dangerous_keywords = ["reject", "decline", "not_hired", "failed"]

    for status, actions in STATUS_ACTIONS.items():
        for action in actions:
            is_dangerous = any(kw in action.key.lower() for kw in dangerous_keywords)
            if is_dangerous and action.method == "POST":
                assert action.confirmation is not None, (
                    f"Dangerous action '{action.key}' in status '{status}' "
                    f"should have a confirmation message"
                )
