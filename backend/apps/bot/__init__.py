"""Bot application package exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "create_application",
    "create_bot",
    "create_dispatcher",
    "main",
    "StateManager",
]


def __getattr__(name: str) -> Any:
    if name == "StateManager":
        from .services import StateManager as _StateManager

        return _StateManager

    if name in {"create_application", "create_bot", "create_dispatcher", "main"}:
        app_module = import_module(".app", __name__)
        attr = getattr(app_module, name)
        globals()[name] = attr
        return attr

    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
