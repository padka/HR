"""Public service helpers for the admin UI with lazy imports.

The previous implementation eagerly imported every service module at
package import time.  That worked in production where the full runtime
stack (SQLAlchemy, aiogram, etc.) is available, but it made our tests
very brittle: simply importing ``backend.apps.admin_ui.services`` tried
to import optional dependencies even when an individual test only needed
one lightweight helper.  In the execution environment used for the HR
UI kata we intentionally keep the dependency footprint small, so those
eager imports resulted in ``ModuleNotFoundError`` exceptions before the
tests even started running.

To keep the public API intact while avoiding those crashes we now expose
the same symbols via a tiny lazy-import shim.  ``__getattr__`` loads the
requested module on demand, caches the attribute on the package, and
then returns it.  This matches the previous behaviour for callers (all
exports are still available from ``backend.apps.admin_ui.services``) but
defers any heavy optional imports until they are actually needed.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Iterable, Tuple

# Map public attribute names to the modules that define them.  The
# mapping is flattened once on module load so that ``__getattr__`` can
# resolve lookups in O(1) time without scanning the dictionary on every
# access.
_MODULE_EXPORTS: Dict[str, Tuple[str, Iterable[str]]] = {
    "backend.apps.admin_ui.services.dashboard": ("dashboard_counts",),
    "backend.apps.admin_ui.services.candidates": (
        "CandidateRow",
        "candidate_filter_options",
        "get_candidate_detail",
        "list_candidates",
        "delete_candidate",
        "toggle_candidate_activity",
        "upsert_candidate",
        "update_candidate",
    ),
    "backend.apps.admin_ui.services.recruiters": (
        "api_recruiters_payload",
        "build_recruiter_payload",
        "create_recruiter",
        "delete_recruiter",
        "get_recruiter_detail",
        "list_recruiters",
        "update_recruiter",
    ),
    "backend.apps.admin_ui.services.cities": (
        "api_cities_payload",
        "api_city_owners_payload",
        "city_owner_field_name",
        "create_city",
        "get_city",
        "list_cities",
        "update_city_settings",
    ),
    "backend.apps.admin_ui.services.templates": (
        "api_templates_payload",
        "create_template",
        "delete_template",
        "get_stage_templates",
        "get_template",
        "list_templates",
        "stage_payload_for_ui",
        "templates_overview",
        "update_template",
        "update_templates_for_city",
    ),
    "backend.apps.admin_ui.services.slots": (
        "api_slots_payload",
        "create_slot",
        "list_slots",
        "recruiters_for_slot_form",
        "set_slot_outcome",
    ),
    "backend.apps.admin_ui.services.questions": (
        "get_test_question_detail",
        "list_test_questions",
        "update_test_question",
    ),
}

_ATTRIBUTE_MAP: Dict[str, str] = {}
for module_name, attrs in _MODULE_EXPORTS.items():
    for attr in attrs:
        _ATTRIBUTE_MAP[attr] = module_name

__all__ = sorted(_ATTRIBUTE_MAP.keys())


def __getattr__(name: str) -> Any:  # pragma: no cover - thin wrapper
    module_name = _ATTRIBUTE_MAP.get(name)
    if not module_name:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> Iterable[str]:  # pragma: no cover - trivial helper
    return sorted(set(globals()) | set(__all__))

