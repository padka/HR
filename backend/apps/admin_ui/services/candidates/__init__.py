"""Backwards-compatible candidates services package."""

from __future__ import annotations

import sys
from types import ModuleType

from . import ai_operations as _ai_operations
from . import chat as _chat
from . import crud as _crud
from . import helpers as _helpers
from . import hh_sync as _hh_sync
from . import pipeline as _pipeline
from . import search as _search
from . import test_operations as _test_operations

_MODULES = (
    _helpers,
    _crud,
    _search,
    _ai_operations,
    _pipeline,
    _test_operations,
    _hh_sync,
    _chat,
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


class _CandidatesModule(ModuleType):
    def __getattr__(self, name: str):
        try:
            return globals()[name]
        except KeyError as exc:
            try:
                return getattr(_helpers, name)
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


sys.modules[__name__].__class__ = _CandidatesModule
