"""Slot-related services split into focused modules."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .bulk import bulk_create_slots
from .crud import (
    api_slots_payload,
    create_slot,
    delete_all_slots,
    delete_slot,
    list_slots,
    recruiters_for_slot_form,
)

if TYPE_CHECKING:  # pragma: no cover - used only for static analysis
    from .bot import (
        BotDispatch,
        BotDispatchPlan,
        execute_bot_dispatch,
        get_state_manager,
        reject_slot_booking,
        reschedule_slot_booking,
        set_slot_outcome,
    )

_BOT_EXPORTS = {
    "BotDispatch",
    "BotDispatchPlan",
    "execute_bot_dispatch",
    "get_state_manager",
    "reject_slot_booking",
    "reschedule_slot_booking",
    "set_slot_outcome",
}

__all__ = [
    "api_slots_payload",
    "bulk_create_slots",
    "create_slot",
    "delete_all_slots",
    "delete_slot",
    "list_slots",
    "recruiters_for_slot_form",
    *_BOT_EXPORTS,
]


def __getattr__(name: str) -> Any:  # pragma: no cover - simple passthrough
    if name not in _BOT_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name}")

    try:
        module = import_module("backend.apps.admin_ui.services.slots.bot")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError(
            "Bot integration dependencies are not installed; access to bot-related "
            "slot helpers is unavailable."
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging surface
        raise RuntimeError(
            "Bot integration failed to initialize; see nested exception for details."
        ) from exc

    value = getattr(module, name)
    globals()[name] = value
    return value
