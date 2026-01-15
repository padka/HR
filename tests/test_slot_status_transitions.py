import pytest

from backend.domain.models import (
    SlotStatus,
    SlotStatusTransitionError,
    enforce_slot_transition,
)


@pytest.mark.parametrize(
    "current,target",
    [
        (SlotStatus.FREE, SlotStatus.PENDING),
        (SlotStatus.PENDING, SlotStatus.BOOKED),
        (SlotStatus.BOOKED, SlotStatus.CONFIRMED),
        (SlotStatus.CONFIRMED, SlotStatus.CANCELED),
        (SlotStatus.CONFIRMED_BY_CANDIDATE, SlotStatus.CANCELED),
        (SlotStatus.PENDING, SlotStatus.FREE),
        (SlotStatus.BOOKED, SlotStatus.FREE),
        (SlotStatus.CONFIRMED, SlotStatus.FREE),
        (SlotStatus.CONFIRMED_BY_CANDIDATE, SlotStatus.FREE),
        (SlotStatus.PENDING, SlotStatus.CANCELED),
        (SlotStatus.BOOKED, SlotStatus.CANCELED),
        (SlotStatus.CONFIRMED, SlotStatus.CANCELED),
        (SlotStatus.CONFIRMED_BY_CANDIDATE, SlotStatus.CANCELED),
        (SlotStatus.BOOKED, SlotStatus.BOOKED),  # idempotent
    ],
)
def test_enforce_slot_transition_allows_valid_paths(current, target):
    assert enforce_slot_transition(current, target) == target


@pytest.mark.parametrize(
    "current,target",
    [
        (SlotStatus.FREE, SlotStatus.BOOKED),
        (SlotStatus.FREE, SlotStatus.CONFIRMED),
        (SlotStatus.FREE, SlotStatus.CANCELED),
        (SlotStatus.BOOKED, SlotStatus.PENDING),
        (SlotStatus.CONFIRMED, SlotStatus.BOOKED),
        (SlotStatus.CANCELED, SlotStatus.FREE),
        (SlotStatus.CANCELED, SlotStatus.PENDING),
        (SlotStatus.CANCELED, SlotStatus.BOOKED),
        (None, SlotStatus.PENDING),
        ("legacy", SlotStatus.PENDING),
    ],
)
def test_enforce_slot_transition_blocks_invalid_paths(current, target):
    with pytest.raises(SlotStatusTransitionError):
        enforce_slot_transition(current, target)
