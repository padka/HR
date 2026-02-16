"""Tiny in-process TTL cache for ultra-hot paths.

This is intentionally small and simple:
- process-local (no cross-worker coherence)
- short TTLs (seconds)
- best-effort eviction (clear-on-pressure)

Use it for high-RPS read endpoints where Redis/DB roundtrips become the bottleneck.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from time import monotonic
from typing import Any, Optional

_MAX_ITEMS = 2048


@dataclass
class _Entry:
    expires_at: float
    value: Any


_CACHE: dict[str, _Entry] = {}


def _enabled() -> bool:
    # Tests rebuild/clean DB frequently; process-local caches cause flaky assertions.
    return not (os.getenv("PYTEST_CURRENT_TEST") or os.getenv("ENVIRONMENT") == "test")


def get(key: str) -> Optional[Any]:
    if not _enabled():
        return None
    entry = _CACHE.get(key)
    if entry is None:
        return None
    if entry.expires_at <= monotonic():
        _CACHE.pop(key, None)
        return None
    return entry.value


def set(key: str, value: Any, *, ttl_seconds: float) -> None:
    if not _enabled():
        return
    if ttl_seconds <= 0:
        return
    if len(_CACHE) >= _MAX_ITEMS:
        # Evict everything: cheap and deterministic.
        _CACHE.clear()
    _CACHE[key] = _Entry(expires_at=monotonic() + ttl_seconds, value=value)


def clear() -> None:
    _CACHE.clear()
