"""Shared candidate-access API boundary for external candidate surfaces."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "CandidateAccessPrincipal",
    "get_max_candidate_access_principal",
    "router",
]


def __getattr__(name: str) -> Any:
    if name in {"CandidateAccessPrincipal", "get_max_candidate_access_principal"}:
        auth_module = import_module(".auth", __name__)
        attr = getattr(auth_module, name)
        globals()[name] = attr
        return attr
    if name == "router":
        router_module = import_module(".router", __name__)
        attr = getattr(router_module, name)
        globals()[name] = attr
        return attr
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
