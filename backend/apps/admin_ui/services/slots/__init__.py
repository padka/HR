"""Public API for admin UI slot services with backward compatibility."""

from __future__ import annotations

import sys
import types

from . import core as _core
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


class _SlotsModule(types.ModuleType):
    """Module proxy keeping core aliases in sync for monkeypatching."""

    def __setattr__(self, name: str, value: object) -> None:  # pragma: no cover - trivial
        super().__setattr__(name, value)
        if name == "_trigger_test2":
            setattr(_core, "_trigger_test2", value)


module = sys.modules[__name__]
module.__class__ = _SlotsModule
module._trigger_test2 = _core._trigger_test2

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
    "_trigger_test2",
]
