"""Simple in-memory metrics for bot flows."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import Dict


@dataclass
class Test1MetricsSnapshot:
    """Immutable view over Test 1 counters."""

    rejections_total: int
    completions_total: int
    rejection_breakdown: Dict[str, int]

    @property
    def total_seen(self) -> int:
        return self.rejections_total + self.completions_total

    @property
    def rejection_percent(self) -> float:
        total = self.total_seen
        if total == 0:
            return 0.0
        return round((self.rejections_total / total) * 100, 2)


class _Test1Metrics:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._rejections: Counter[str] = Counter()
        self._completions: int = 0

    async def record_rejection(self, reason: str) -> None:
        async with self._lock:
            self._rejections[reason] += 1

    async def record_completion(self) -> None:
        async with self._lock:
            self._completions += 1

    async def snapshot(self) -> Test1MetricsSnapshot:
        async with self._lock:
            return Test1MetricsSnapshot(
                rejections_total=sum(self._rejections.values()),
                completions_total=self._completions,
                rejection_breakdown=dict(self._rejections),
            )

    async def reset(self) -> None:
        async with self._lock:
            self._rejections.clear()
            self._completions = 0


_test1_metrics = _Test1Metrics()


async def record_test1_rejection(reason: str) -> None:
    await _test1_metrics.record_rejection(reason)


async def record_test1_completion() -> None:
    await _test1_metrics.record_completion()


async def get_test1_metrics_snapshot() -> Test1MetricsSnapshot:
    return await _test1_metrics.snapshot()


async def reset_test1_metrics() -> None:
    await _test1_metrics.reset()


__all__ = [
    "Test1MetricsSnapshot",
    "get_test1_metrics_snapshot",
    "record_test1_completion",
    "record_test1_rejection",
    "reset_test1_metrics",
]
