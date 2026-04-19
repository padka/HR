"""Admin API application package exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["app", "create_app"]


def __getattr__(name: str) -> Any:
    if name in {"app", "create_app"}:
        main_module = import_module(".main", __name__)
        attr = getattr(main_module, name)
        globals()[name] = attr
        return attr
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
