"""Compatibility package for the legacy :mod:`admin_server` import path.

The real implementation lives in :mod:`backend.apps.admin_ui.app`.  We expose
the same public interface through :mod:`admin_server.app` and lazily re-export
it at the package level so that ``import admin_server`` continues to behave as
expected even in environments where optional dependencies (such as
``fastapi``) are not installed.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

__all__ = ["app", "create_app", "lifespan"]

if TYPE_CHECKING:  # pragma: no cover - imported only for type checkers
    from .app import app, create_app, lifespan


def __getattr__(name: str):
    if name in __all__:
        module = import_module("admin_server.app")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
