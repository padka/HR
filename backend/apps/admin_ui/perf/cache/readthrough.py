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
import time
from typing import Any, TypeVar

from backend.apps.admin_ui.perf.metrics.context import add_cache_event, get_context
from backend.apps.admin_ui.perf.cache.microcache import get_value as microcache_get_value
from backend.apps.admin_ui.perf.cache.microcache import set_value as microcache_set_value
from backend.core.cache import get_cache

T = TypeVar("T")

_LOCKS_GUARD = asyncio.Lock()
_LOCKS: dict[str, asyncio.Lock] = {}
_LOCKS_MAX = 1024


def _freshness() -> str:
    ctx = get_context()
    return "stale" if (ctx and ctx.degraded_reason) else "fresh"


def microcache_get(key: str, *, expected_type: type[T]) -> tuple[T, bool] | None:
    return microcache_get_value(key, expected_type=expected_type)


def microcache_set(key: str, value: Any, *, ttl_seconds: float, stale_seconds: float = 0.0) -> None:
    microcache_set_value(key, value, ttl_seconds=ttl_seconds, stale_seconds=stale_seconds)


async def redis_get(key: str, *, expected_type: type[T]) -> tuple[T, bool] | None:
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
        return value, (_freshness() == "stale")
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


async def get_cached(
    key: str,
    *,
    expected_type: type[T],
    ttl_seconds: float,
    stale_seconds: float = 0.0,
) -> tuple[T, bool] | None:
    """Try microcache, then Redis.

    Returns:
        (value, is_stale) or None.
    """

    value = microcache_get(key, expected_type=expected_type)
    if value is not None:
        return value

    value = await redis_get(key, expected_type=expected_type)
    if value is not None:
        # Warm microcache for subsequent ultra-hot reads.
        microcache_set(key, value[0], ttl_seconds=ttl_seconds, stale_seconds=stale_seconds)
        return value
    return None


async def set_cached(
    key: str,
    value: Any,
    *,
    ttl_seconds: float,
    stale_seconds: float = 0.0,
) -> None:
    """Write-through to microcache + Redis (best-effort)."""

    microcache_set(key, value, ttl_seconds=ttl_seconds, stale_seconds=stale_seconds)
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
    stale_seconds: float = 0.0,
    compute: Callable[[], Awaitable[T]],
) -> T:
    """Read-through cache with single-flight fill to prevent stampedes.

    If `stale_seconds>0`, enables stale-while-revalidate for microcache:
    - after TTL expiry but before `TTL+stale_seconds`, return cached value
      immediately (marked stale) and refresh in background (single-flight).
    """

    cached = await get_cached(
        key,
        expected_type=expected_type,
        ttl_seconds=ttl_seconds,
        stale_seconds=stale_seconds,
    )
    if cached is not None:
        value, is_stale = cached
        if not is_stale:
            return value

        # Stale hit: if we're in degraded mode, don't attempt background refresh.
        ctx = get_context()
        if ctx and ctx.degraded_reason:
            return value

        if stale_seconds and stale_seconds > 0:
            lock = await _lock_for(key)
            if not lock.locked():
                async def _refresh() -> None:
                    async with lock:
                        cached2 = await get_cached(
                            key,
                            expected_type=expected_type,
                            ttl_seconds=ttl_seconds,
                            stale_seconds=stale_seconds,
                        )
                        if cached2 is not None and not cached2[1]:
                            return
                        try:
                            new_value = await compute()
                        except Exception:
                            return
                        await set_cached(
                            key,
                            new_value,
                            ttl_seconds=ttl_seconds,
                            stale_seconds=stale_seconds,
                        )

                asyncio.create_task(_refresh(), name="perf_cache_refresh")
            return value

        return value

    lock = await _lock_for(key)
    async with lock:
        cached = await get_cached(
            key,
            expected_type=expected_type,
            ttl_seconds=ttl_seconds,
            stale_seconds=stale_seconds,
        )
        if cached is not None and not cached[1]:
            return cached[0]
        value = await compute()
        await set_cached(key, value, ttl_seconds=ttl_seconds, stale_seconds=stale_seconds)
        return value
