"""Admin UI application exports."""

from importlib import import_module
from typing import TYPE_CHECKING

__all__ = ["app", "create_app"]

if TYPE_CHECKING:  # pragma: no cover
    from .app import app, create_app


def __getattr__(name: str):
    if name in __all__:
        module = import_module(".app", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
