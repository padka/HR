import pytest

from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.write_contract import (
    is_supported_kanban_move_column,
    resolve_action_intent_key,
    resolve_action_target_status,
    resolve_kanban_move_intent,
    resolve_kanban_target_status,
)


@pytest.mark.no_db_cleanup
def test_reject_action_resolves_to_stage_specific_status():
    target, resolution = resolve_action_target_status(
        "reject",
        current_status_slug=CandidateStatus.TEST2_COMPLETED.value,
    )
    assert target == CandidateStatus.TEST2_FAILED.value
    assert resolution == "action_intent"

    target, resolution = resolve_action_target_status(
        "reject",
        current_status_slug=CandidateStatus.WAITING_SLOT.value,
    )
    assert target == CandidateStatus.INTERVIEW_DECLINED.value
    assert resolution == "action_intent"


@pytest.mark.no_db_cleanup
def test_action_intent_keys_prefer_domain_language():
    assert resolve_action_intent_key("approve_upcoming_slot") == "approve_slot"
    assert resolve_action_intent_key("mark_hired") == "finalize_hired"
    assert resolve_action_intent_key("interview_outcome_passed") == "send_to_test2"


@pytest.mark.no_db_cleanup
def test_kanban_move_contract_exposes_only_safe_columns():
    assert is_supported_kanban_move_column("interview_confirmed") is True
    assert is_supported_kanban_move_column("test2_sent") is True
    assert is_supported_kanban_move_column("slot_pending") is False
    assert is_supported_kanban_move_column("incoming") is False

    assert resolve_kanban_move_intent("test2_completed") == "mark_test2_completed"
    assert resolve_kanban_move_intent("slot_pending") == "unsupported_kanban_move"
    assert resolve_kanban_target_status("test2_completed") == CandidateStatus.TEST2_COMPLETED.value

