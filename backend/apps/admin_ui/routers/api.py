from __future__ import annotations

import sys
from types import ModuleType
from fastapi import APIRouter

from . import api_ai as _api_ai
from . import api_candidates as _api_candidates
from . import api_chat as _api_chat
from . import api_cities as _api_cities
from . import api_dashboard as _api_dashboard
from . import api_misc as _api_misc
from . import api_misc_routes as _api_misc_routes
from . import api_recruiters as _api_recruiters
from . import api_slots as _api_slots
from . import api_templates as _api_templates
from .directory import router as directory_router
from .profile_api import router as profile_api_router
router = APIRouter()
router.include_router(directory_router, prefix="/api")
router.include_router(profile_api_router, prefix="/api")
router.include_router(_api_templates.router, prefix="/api")
router.include_router(_api_dashboard.router)
router.include_router(_api_chat.router)
router.include_router(_api_slots.router)
router.include_router(_api_recruiters.router)
router.include_router(_api_cities.router)
router.include_router(_api_candidates.router)
router.include_router(_api_ai.router)
router.include_router(_api_misc_routes.router)

_MODULES = (
    _api_misc,
    _api_templates,
    _api_dashboard,
    _api_chat,
    _api_slots,
    _api_recruiters,
    _api_cities,
    _api_candidates,
    _api_ai,
    _api_misc_routes,
)

__all__: list[str] = ["router"]

for _module in _MODULES:
    module_all = getattr(_module, "__all__", None)
    if module_all is None:
        module_all = [
            name
            for name in dir(_module)
            if not (name.startswith("__") and name.endswith("__"))
        ]
    for _name in module_all:
        if _name == "router":
            continue
        globals()[_name] = getattr(_module, _name)
        if _name not in __all__:
            __all__.append(_name)

for _module in _MODULES:
    for _name in dir(_module):
        if _name.startswith("__") and _name.endswith("__"):
            continue
        if _name == "router":
            continue
        globals()[_name] = getattr(_module, _name)
list_known_template_keys = _api_misc.list_known_template_keys
known_template_presets = _api_misc.known_template_presets
api_template_keys = _api_misc.api_template_keys
api_template_presets = _api_misc.api_template_presets
class _ApiModule(ModuleType):
    def __getattr__(self, name: str):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        try:
            return globals()[name]
        except KeyError as exc:
            try:
                return getattr(_api_misc, name)
            except AttributeError:
                raise exc

    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        if not (name.startswith("__") and name.endswith("__")):
            for _module in _MODULES:
                setattr(_module, name, value)

    def __delattr__(self, name: str) -> None:
        super().__delattr__(name)
        for _module in _MODULES:
            if hasattr(_module, name):
                delattr(_module, name)
sys.modules[__name__].__class__ = _ApiModule
