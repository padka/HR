"""Slot-related services split into focused modules."""

from .bulk import bulk_create_slots
from .crud import (
    api_slots_payload,
    create_slot,
    delete_all_slots,
    delete_slot,
    list_slots,
    recruiters_for_slot_form,
)
from .bot import (
    BotDispatch,
    BotDispatchPlan,
    execute_bot_dispatch,
    get_state_manager,
    reject_slot_booking,
    reschedule_slot_booking,
    set_slot_outcome,
)

__all__ = [
    "api_slots_payload",
    "bulk_create_slots",
    "create_slot",
    "delete_all_slots",
    "delete_slot",
    "execute_bot_dispatch",
    "get_state_manager",
    "list_slots",
    "recruiters_for_slot_form",
    "reject_slot_booking",
    "reschedule_slot_booking",
    "set_slot_outcome",
    "BotDispatch",
    "BotDispatchPlan",
]
