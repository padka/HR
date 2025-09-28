"""Bot application package exports."""

from importlib import import_module
from typing import Any

__all__ = ["bot", "dp", "main"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module("bot")
        return getattr(module, name)
    raise AttributeError(name)
