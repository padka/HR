"""Degraded-mode state helpers.

Today, admin_ui tracks DB availability via a simple process flag:
`app.state.db_available`.

This module is a small indirection layer so:
- middleware and services have a canonical place to read/write the flag
- future iterations can attach timings/reasons without changing all call sites
"""

from __future__ import annotations

from fastapi import FastAPI


def is_db_available(app: FastAPI) -> bool:
    """Return whether the database is considered available for this process."""

    return bool(getattr(getattr(app, "state", None), "db_available", True))


def set_db_available(app: FastAPI, available: bool) -> None:
    """Set DB availability for this process (best-effort)."""

    state = getattr(app, "state", None)
    if state is None:
        return
    state.db_available = bool(available)


__all__ = ["is_db_available", "set_db_available"]

