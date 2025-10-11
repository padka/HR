"""Public API for admin UI slot services."""

from .core import (
    BotDispatch,
    BotDispatchPlan,
    api_slots_payload,
    bulk_create_slots,
    create_slot,
    delete_all_slots,
    delete_slot,
    execute_bot_dispatch,
    get_state_manager,
    list_slots,
    recruiters_for_slot_form,
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
