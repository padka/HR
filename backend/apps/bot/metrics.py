"""Simple in-memory metrics for bot flows."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Optional


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


@dataclass
class NotificationMetricsSnapshot:
    """Aggregated counters for notification delivery."""

    notifications_sent_total: Dict[str, int]
    notifications_failed_total: Dict[str, int]
    candidate_confirmed_notice_total: int
    send_retry_total: int
    circuit_open_total: int
    outbox_queue_depth: int
    template_fallback_total: Dict[str, int]


class _NotificationMetrics:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sent: Counter[str] = Counter()
        self._failed: Counter[str] = Counter()
        self._template_fallback: Counter[str] = Counter()
        self._candidate_confirmed_notice: int = 0
        self._send_retry_total: int = 0
        self._circuit_open_total: int = 0
        self._outbox_queue_depth: int = 0

    async def record_sent(self, notification_type: Optional[str]) -> None:
        async with self._lock:
            if notification_type:
                self._sent[notification_type] += 1
            else:
                self._sent["_unknown"] += 1

    async def record_failed(self, notification_type: Optional[str]) -> None:
        async with self._lock:
            if notification_type:
                self._failed[notification_type] += 1
            else:
                self._failed["_unknown"] += 1

    async def record_template_fallback(self, key: str) -> None:
        async with self._lock:
            self._template_fallback[key] += 1

    async def record_candidate_notice(self) -> None:
        async with self._lock:
            self._candidate_confirmed_notice += 1

    async def record_send_retry(self) -> None:
        async with self._lock:
            self._send_retry_total += 1

    async def record_circuit_open(self) -> None:
        async with self._lock:
            self._circuit_open_total += 1

    async def set_outbox_depth(self, depth: int) -> None:
        async with self._lock:
            self._outbox_queue_depth = max(0, depth)

    async def snapshot(self) -> NotificationMetricsSnapshot:
        async with self._lock:
            return NotificationMetricsSnapshot(
                notifications_sent_total=dict(self._sent),
                notifications_failed_total=dict(self._failed),
                candidate_confirmed_notice_total=self._candidate_confirmed_notice,
                send_retry_total=self._send_retry_total,
                circuit_open_total=self._circuit_open_total,
                outbox_queue_depth=self._outbox_queue_depth,
                template_fallback_total=dict(self._template_fallback),
            )

    async def reset(self) -> None:
        async with self._lock:
            self._sent.clear()
            self._failed.clear()
            self._template_fallback.clear()
            self._candidate_confirmed_notice = 0
            self._send_retry_total = 0
            self._circuit_open_total = 0
            self._outbox_queue_depth = 0


_notification_metrics = _NotificationMetrics()


async def record_test1_rejection(reason: str) -> None:
    await _test1_metrics.record_rejection(reason)


async def record_test1_completion() -> None:
    await _test1_metrics.record_completion()


async def get_test1_metrics_snapshot() -> Test1MetricsSnapshot:
    return await _test1_metrics.snapshot()


async def reset_test1_metrics() -> None:
    await _test1_metrics.reset()


async def record_notification_sent(notification_type: Optional[str] = None) -> None:
    await _notification_metrics.record_sent(notification_type)


async def record_notification_failed(notification_type: Optional[str] = None) -> None:
    await _notification_metrics.record_failed(notification_type)


async def record_template_fallback(key: str) -> None:
    await _notification_metrics.record_template_fallback(key)


async def record_candidate_confirmed_notice() -> None:
    await _notification_metrics.record_candidate_notice()


async def record_send_retry() -> None:
    await _notification_metrics.record_send_retry()


async def record_circuit_open() -> None:
    await _notification_metrics.record_circuit_open()


async def set_outbox_queue_depth(depth: int) -> None:
    await _notification_metrics.set_outbox_depth(depth)


async def get_notification_metrics_snapshot() -> NotificationMetricsSnapshot:
    return await _notification_metrics.snapshot()


async def reset_notification_metrics() -> None:
    await _notification_metrics.reset()


__all__ = [
    "Test1MetricsSnapshot",
    "get_test1_metrics_snapshot",
    "record_test1_completion",
    "record_test1_rejection",
    "reset_test1_metrics",
    "NotificationMetricsSnapshot",
    "record_notification_sent",
    "record_notification_failed",
    "record_candidate_confirmed_notice",
    "record_template_fallback",
    "record_send_retry",
    "record_circuit_open",
    "set_outbox_queue_depth",
    "get_notification_metrics_snapshot",
    "reset_notification_metrics",
]
