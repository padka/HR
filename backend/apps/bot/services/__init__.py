"""Backwards-compatible bot services package."""

import sys
from types import ModuleType

from . import base as _base
from . import broadcast as _broadcast
from . import notification_flow as _notification_flow
from . import onboarding_flow as _onboarding_flow
from . import slot_flow as _slot_flow
from . import test1_flow as _test1_flow
from . import test2_flow as _test2_flow

_MODULES = (
    _base,
    _notification_flow,
    _test1_flow,
    _test2_flow,
    _onboarding_flow,
    _broadcast,
    _slot_flow,
)

__all__: list[str] = []

for _module in _MODULES:
    module_all = getattr(_module, "__all__", None)
    if module_all is None:
        module_all = [
            name
            for name in dir(_module)
            if not (name.startswith("__") and name.endswith("__"))
        ]
    for _name in module_all:
        globals()[_name] = getattr(_module, _name)
        if _name not in __all__:
            __all__.append(_name)

for _module in _MODULES:
    for _name in dir(_module):
        if _name.startswith("__") and _name.endswith("__"):
            continue
        globals()[_name] = getattr(_module, _name)


class _ServicesModule(ModuleType):
    def __getattr__(self, name: str):
        try:
            return globals()[name]
        except KeyError as exc:
            try:
                return getattr(_base, name)
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


sys.modules[__name__].__class__ = _ServicesModule
