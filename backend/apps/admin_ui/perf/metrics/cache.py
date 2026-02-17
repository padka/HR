"""Cache-related helpers for perf instrumentation.

Today, cache HIT/STALE observations are exported by the HTTP metrics middleware
using request-scoped cache events recorded in `perf.metrics.context`.

This module provides small helpers to summarize cache behavior per request.
It intentionally keeps cardinality low: the goal is to answer "did we serve
from cache?" rather than "which key was used?".
"""

from __future__ import annotations

from typing import Literal

from backend.apps.admin_ui.perf.metrics.context import PerfContext

CacheSummary = Literal["none", "hit", "stale", "miss"]


def summarize_cache(ctx: PerfContext | None) -> CacheSummary:
    """Summarize request cache behavior.

    Rules:
    - no cache events -> "none"
    - any stale hit   -> "stale"
    - any hit         -> "hit"
    - otherwise       -> "miss" (only misses were observed)
    """

    if ctx is None or not ctx.cache_events:
        return "none"
    hits = [ev for ev in ctx.cache_events if ev.state == "hit"]
    if any(ev.freshness == "stale" for ev in hits):
        return "stale"
    if hits:
        return "hit"
    return "miss"


__all__ = ["summarize_cache", "CacheSummary"]

