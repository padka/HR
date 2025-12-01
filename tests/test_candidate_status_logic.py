import pytest

from backend.domain.candidates.status import (
    CandidateStatus,
    can_transition,
    is_status_retreat,
    get_next_statuses,
)


def test_valid_forward_transitions():
    assert can_transition(CandidateStatus.TEST1_COMPLETED, CandidateStatus.INTERVIEW_SCHEDULED)
    assert can_transition(CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY, CandidateStatus.HIRED)
    assert not can_transition(CandidateStatus.HIRED, CandidateStatus.TEST1_COMPLETED)


def test_status_retreat_detection():
    assert is_status_retreat(CandidateStatus.INTERVIEW_CONFIRMED, CandidateStatus.WAITING_SLOT)
    assert not is_status_retreat(CandidateStatus.TEST2_SENT, CandidateStatus.INTRO_DAY_SCHEDULED)


@pytest.mark.parametrize(
    "current,expected_next",
    [
        (None, [CandidateStatus.TEST1_COMPLETED]),
        (CandidateStatus.TEST2_COMPLETED, [CandidateStatus.INTRO_DAY_SCHEDULED]),
        (CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF, [CandidateStatus.HIRED, CandidateStatus.NOT_HIRED]),
    ],
)
def test_next_statuses(current, expected_next):
    next_statuses = [item[0] for item in get_next_statuses(current)]
    assert next_statuses == expected_next
