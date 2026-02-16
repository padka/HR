"""Request-scoped performance context.

This module provides a lightweight ContextVar-backed container used by:
- HTTP metrics middleware (route/method)
- cache wrappers (HIT/MISS/STALE markers)
- degraded-mode logic (reason markers)
- DB instrumentation (attribute queries to the current route)

The goal is to avoid threading Starlette's Request object through deep layers.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Literal

CacheBackend = Literal["microcache", "redis"]
CacheState = Literal["hit", "miss"]
CacheFreshness = Literal["fresh", "stale"]


@dataclass
class CacheEvent:
    backend: CacheBackend
    state: CacheState
    freshness: CacheFreshness


@dataclass
class PerfContext:
    route: str
    method: str
    degraded_reason: str | None = None
    cache_events: list[CacheEvent] = field(default_factory=list)
    db_query_count: int = 0
    db_query_seconds: float = 0.0


_CTX: ContextVar[PerfContext | None] = ContextVar("admin_ui_perf_ctx", default=None)


def set_context(*, route: str, method: str) -> Token[PerfContext | None]:
    """Set request context for the current task.

    Args:
        route: Best-known route label at request start (may be refined later).
        method: HTTP method.

    Returns:
        A token to be used with reset_context().
    """

    return _CTX.set(PerfContext(route=route, method=method))


def get_context() -> PerfContext | None:
    """Return current request context if set."""

    return _CTX.get()


def reset_context(token: Token[PerfContext | None]) -> None:
    """Reset request context to previous value."""

    _CTX.reset(token)


def mark_degraded(reason: str) -> None:
    """Mark current request as served in degraded mode.

    The first reason wins to avoid noisy reassignments.
    """

    ctx = _CTX.get()
    if ctx is None:
        return
    if ctx.degraded_reason is None:
        ctx.degraded_reason = reason


def add_cache_event(*, backend: CacheBackend, state: CacheState, freshness: CacheFreshness) -> None:
    """Record a cache observation for the current request."""

    ctx = _CTX.get()
    if ctx is None:
        return
    ctx.cache_events.append(CacheEvent(backend=backend, state=state, freshness=freshness))


def add_db_query(*, duration_seconds: float) -> None:
    """Record a single DB query for the current request (best-effort)."""

    ctx = _CTX.get()
    if ctx is None:
        return
    ctx.db_query_count += 1
    ctx.db_query_seconds += float(duration_seconds)
