from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .dashboard import dashboard_counts
from .kpis import (
    get_weekly_kpis,
    list_weekly_history,
    get_week_window,
    compute_weekly_snapshot,
    store_weekly_snapshot,
)
from .candidates import (
    CandidateRow,
    candidate_filter_options,
    get_candidate_detail,
    list_candidates,
    delete_candidate,
    toggle_candidate_activity,
    upsert_candidate,
    update_candidate,
)
from .recruiters import (
    api_recruiters_payload,
    build_recruiter_payload,
    create_recruiter,
    delete_recruiter,
    get_recruiter_detail,
    list_recruiters,
    update_recruiter,
)
from .cities import (
    api_cities_payload,
    api_city_owners_payload,
    city_owner_field_name,
    create_city,
    list_cities,
    update_city_settings,
)
from .templates import (
    api_templates_payload,
    create_template,
    delete_template,
    get_stage_templates,
    get_template,
    list_templates,
    stage_payload_for_ui,
    templates_overview,
    update_template,
    update_templates_for_city,
)
from .questions import (
    get_test_question_detail,
    list_test_questions,
    update_test_question,
)

if TYPE_CHECKING:  # pragma: no cover - assist static analysis only
    from .slots import (
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

_SLOT_EXPORTS = {
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
}

__all__ = [
    "dashboard_counts",
    "get_weekly_kpis",
    "list_weekly_history",
    "get_week_window",
    "compute_weekly_snapshot",
    "store_weekly_snapshot",
    "CandidateRow",
    "candidate_filter_options",
    "list_candidates",
    "get_candidate_detail",
    "upsert_candidate",
    "toggle_candidate_activity",
    "update_candidate",
    "delete_candidate",
    "list_recruiters",
    "create_recruiter",
    "get_recruiter_detail",
    "update_recruiter",
    "delete_recruiter",
    "build_recruiter_payload",
    "list_cities",
    "create_city",
    "update_city_settings",
    "city_owner_field_name",
    "get_stage_templates",
    "stage_payload_for_ui",
    "templates_overview",
    "update_templates_for_city",
    "list_templates",
    "create_template",
    "get_template",
    "update_template",
    "delete_template",
    "api_recruiters_payload",
    "api_cities_payload",
    "api_slots_payload",
    "api_templates_payload",
    "api_city_owners_payload",
    "list_slots",
    "recruiters_for_slot_form",
    "create_slot",
    "set_slot_outcome",
    "bulk_create_slots",
    "delete_slot",
    "delete_all_slots",
    "execute_bot_dispatch",
    "get_state_manager",
    "reject_slot_booking",
    "reschedule_slot_booking",
    "list_test_questions",
    "get_test_question_detail",
    "update_test_question",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - module attribute proxy
    if name not in _SLOT_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name}")

    module = import_module("backend.apps.admin_ui.services.slots")
    value = getattr(module, name)
    globals()[name] = value
    return value
