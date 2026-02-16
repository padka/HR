"""Read-through cache helpers for hot read endpoints.

This module centralizes:
- process-local microcache reads/writes
- Redis cache reads/writes (best-effort)
- request-scoped cache markers (HIT/MISS + STALE) for metrics/diagnostics

Security note:
- Keys must be built so that *personalized* responses are scoped by principal/role.
- This module does not attempt to infer scoping automatically.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, TypeVar

from backend.apps.admin_ui.perf.metrics.context import add_cache_event, get_context
from backend.core.cache import get_cache
from backend.core.microcache import get as micro_get
from backend.core.microcache import set as micro_set

T = TypeVar("T")

_LOCKS_GUARD = asyncio.Lock()
_LOCKS: dict[str, asyncio.Lock] = {}
_LOCKS_MAX = 1024


def _freshness() -> str:
    ctx = get_context()
    return "stale" if (ctx and ctx.degraded_reason) else "fresh"


def microcache_get(key: str, *, expected_type: type[T]) -> T | None:
    value = micro_get(key)
    if isinstance(value, expected_type):
        add_cache_event(backend="microcache", state="hit", freshness=_freshness())
        return value
    add_cache_event(backend="microcache", state="miss", freshness=_freshness())
    return None


def microcache_set(key: str, value: Any, *, ttl_seconds: float) -> None:
    micro_set(key, value, ttl_seconds=ttl_seconds)


async def redis_get(key: str, *, expected_type: type[T]) -> T | None:
    try:
        cache = get_cache()
    except RuntimeError:
        add_cache_event(backend="redis", state="miss", freshness=_freshness())
        return None

    try:
        cached = await cache.get(key, default=None)
        value = cached.unwrap_or(None)
    except Exception:
        add_cache_event(backend="redis", state="miss", freshness=_freshness())
        return None

    if isinstance(value, expected_type):
        add_cache_event(backend="redis", state="hit", freshness=_freshness())
        return value
    add_cache_event(backend="redis", state="miss", freshness=_freshness())
    return None


async def redis_set(key: str, value: Any, *, ttl_seconds: float) -> None:
    try:
        cache = get_cache()
    except RuntimeError:
        return
    try:
        await cache.set(key, value, ttl=timedelta(seconds=ttl_seconds))
    except Exception:
        return


async def get_cached(key: str, *, expected_type: type[T], ttl_seconds: float) -> T | None:
    """Try microcache, then Redis, then return None."""

    value = microcache_get(key, expected_type=expected_type)
    if value is not None:
        return value

    value = await redis_get(key, expected_type=expected_type)
    if value is not None:
        # Warm microcache for subsequent ultra-hot reads.
        microcache_set(key, value, ttl_seconds=ttl_seconds)
        return value
    return None


async def set_cached(key: str, value: Any, *, ttl_seconds: float) -> None:
    """Write-through to microcache + Redis (best-effort)."""

    microcache_set(key, value, ttl_seconds=ttl_seconds)
    await redis_set(key, value, ttl_seconds=ttl_seconds)


async def _lock_for(key: str) -> asyncio.Lock:
    # Best-effort eviction: avoid unbounded growth on untrusted/unbounded keys.
    async with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is not None:
            return lock
        if len(_LOCKS) >= _LOCKS_MAX:
            _LOCKS.clear()
        lock = asyncio.Lock()
        _LOCKS[key] = lock
        return lock


async def get_or_compute(
    key: str,
    *,
    expected_type: type[T],
    ttl_seconds: float,
    compute: Callable[[], Awaitable[T]],
) -> T:
    """Read-through cache with single-flight fill to prevent stampedes."""

    cached = await get_cached(key, expected_type=expected_type, ttl_seconds=ttl_seconds)
    if isinstance(cached, expected_type):
        return cached

    lock = await _lock_for(key)
    async with lock:
        cached = await get_cached(key, expected_type=expected_type, ttl_seconds=ttl_seconds)
        if isinstance(cached, expected_type):
            return cached
        value = await compute()
        await set_cached(key, value, ttl_seconds=ttl_seconds)
        return value
