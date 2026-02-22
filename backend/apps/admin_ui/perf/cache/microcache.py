"""Microcache wrapper with stale-while-revalidate support.

This module wraps `backend.core.microcache` and adds:
- a tiny envelope that tracks when a value becomes "fresh expired"
  (so we can continue serving it as stale during the SWR window)
- request-scoped cache markers for metrics/diagnostics

It intentionally remains process-local and best-effort.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, TypeVar

from backend.apps.admin_ui.perf.metrics.context import add_cache_event, get_context
from backend.core.microcache import get as _micro_get
from backend.core.microcache import set as _micro_set

T = TypeVar("T")


@dataclass(frozen=True)
class _MicroEntry:
    """Microcache value wrapper supporting stale-while-revalidate."""

    value: Any
    fresh_until_unix: float


def _freshness() -> str:
    ctx = get_context()
    return "stale" if (ctx and ctx.degraded_reason) else "fresh"


def get_value(key: str, *, expected_type: type[T]) -> tuple[T, bool] | None:
    """Read a value from microcache.

    Returns:
        (value, is_stale) or None.
    """

    raw = _micro_get(key)
    if raw is None:
        add_cache_event(backend="microcache", state="miss", freshness=_freshness())
        return None

    degraded = _freshness() == "stale"
    now = time.time()

    if isinstance(raw, _MicroEntry) and isinstance(raw.value, expected_type):
        is_stale = degraded or (now > float(raw.fresh_until_unix))
        add_cache_event(
            backend="microcache",
            state="hit",
            freshness=("stale" if is_stale else "fresh"),
        )
        return raw.value, is_stale

    if isinstance(raw, expected_type):
        add_cache_event(backend="microcache", state="hit", freshness=_freshness())
        return raw, degraded

    add_cache_event(backend="microcache", state="miss", freshness=_freshness())
    return None


def set_value(key: str, value: Any, *, ttl_seconds: float, stale_seconds: float = 0.0) -> None:
    """Write a value to microcache (optionally with SWR stale window)."""

    if stale_seconds and stale_seconds > 0:
        wrapped = _MicroEntry(value=value, fresh_until_unix=time.time() + float(ttl_seconds))
        _micro_set(key, wrapped, ttl_seconds=float(ttl_seconds) + float(stale_seconds))
        return
    _micro_set(key, value, ttl_seconds=ttl_seconds)


__all__ = ["get_value", "set_value"]

