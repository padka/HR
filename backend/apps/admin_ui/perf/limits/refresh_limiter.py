"""Limiter for cache background refresh tasks.

Stale-while-revalidate can spawn background refresh tasks under load. This
limiter provides a single process-wide semaphore to prevent unbounded refresh
concurrency and DB stampedes.

This is intentionally best-effort and designed for local perf work.
"""

from __future__ import annotations

import asyncio
import os


class RefreshLimiter:
    """Process-wide limiter for background refresh concurrency."""

    def __init__(self, *, max_inflight: int = 10) -> None:
        self._sem = asyncio.Semaphore(max(1, int(max_inflight)))

    def locked(self) -> bool:
        """Return True when no additional refresh slots are available."""

        return self._sem.locked()

    async def __aenter__(self):
        await self._sem.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._sem.release()
        return False


_DEFAULT_MAX = int(os.getenv("PERF_CACHE_REFRESH_MAX_INFLIGHT", "10") or "10")
GLOBAL_REFRESH_LIMITER = RefreshLimiter(max_inflight=_DEFAULT_MAX)


__all__ = ["GLOBAL_REFRESH_LIMITER", "RefreshLimiter"]

