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
    poll_cycle_duration_ms: float
    poll_cycle_processed_last: int
    poll_cycle_source_last: str
    poll_skipped_total: int
    poll_skipped_reasons: Dict[str, int]
    rate_limit_wait_total: int
    rate_limit_wait_seconds: float
    poll_backoff_total: int
    poll_backoff_reasons: Dict[str, int]
    poll_staleness_seconds: float


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
        self._poll_duration_ms: float = 0.0
        self._poll_processed_last: int = 0
        self._poll_source_last: str = "idle"
        self._poll_skipped_total: int = 0
        self._poll_skipped_reasons: Counter[str] = Counter()
        self._rate_limit_wait_total: int = 0
        self._rate_limit_wait_seconds: float = 0.0
        self._poll_backoff_total: int = 0
        self._poll_backoff_reasons: Counter[str] = Counter()
        self._poll_staleness_seconds: float = 0.0

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

    async def record_poll_cycle(
        self,
        duration_seconds: float,
        processed: int,
        source: str,
        skipped_total: int,
        seconds_since_poll: float,
    ) -> None:
        async with self._lock:
            self._poll_duration_ms = max(duration_seconds, 0.0) * 1000.0
            self._poll_processed_last = max(processed, 0)
            self._poll_source_last = source
            self._poll_skipped_total = max(skipped_total, 0)
            self._poll_staleness_seconds = max(seconds_since_poll, 0.0)

    async def record_poll_skipped(self, reason: str, skipped_total: int) -> None:
        async with self._lock:
            self._poll_skipped_total = max(skipped_total, 0)
            self._poll_skipped_reasons[reason] += 1

    async def record_rate_limit_wait(self, wait_seconds: float) -> None:
        async with self._lock:
            self._rate_limit_wait_total += 1
            self._rate_limit_wait_seconds += max(wait_seconds, 0.0)

    async def record_poll_backoff(self, reason: str, delay: float) -> None:
        async with self._lock:
            self._poll_backoff_total += 1
            self._poll_backoff_reasons[reason] += 1

    async def record_poll_staleness(self, seconds: float) -> None:
        async with self._lock:
            self._poll_staleness_seconds = max(seconds, 0.0)

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
                poll_cycle_duration_ms=self._poll_duration_ms,
                poll_cycle_processed_last=self._poll_processed_last,
                poll_cycle_source_last=self._poll_source_last,
                poll_skipped_total=self._poll_skipped_total,
                poll_skipped_reasons=dict(self._poll_skipped_reasons),
                rate_limit_wait_total=self._rate_limit_wait_total,
                rate_limit_wait_seconds=self._rate_limit_wait_seconds,
                poll_backoff_total=self._poll_backoff_total,
                poll_backoff_reasons=dict(self._poll_backoff_reasons),
                poll_staleness_seconds=self._poll_staleness_seconds,
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
            self._poll_duration_ms = 0.0
            self._poll_processed_last = 0
            self._poll_source_last = "idle"
            self._poll_skipped_total = 0
            self._poll_skipped_reasons.clear()
            self._rate_limit_wait_total = 0
            self._rate_limit_wait_seconds = 0.0
            self._poll_backoff_total = 0
            self._poll_backoff_reasons.clear()
            self._poll_staleness_seconds = 0.0


_notification_metrics = _NotificationMetrics()


@dataclass
class ReminderMetricsSnapshot:
    """Aggregated counters tracking reminder lifecycle."""

    scheduled_total: Dict[str, int]
    immediate_total: Dict[str, int]
    adjusted_total: Dict[str, int]
    executed_total: Dict[str, int]
    skipped_total: Dict[str, int]
    skipped_reasons: Dict[str, int]


class _ReminderMetrics:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._scheduled: Counter[str] = Counter()
        self._immediate: Counter[str] = Counter()
        self._adjusted: Counter[str] = Counter()
        self._executed: Counter[str] = Counter()
        self._skipped: Counter[str] = Counter()
        self._skipped_reasons: Counter[str] = Counter()

    @staticmethod
    def _kind_id(kind: object) -> str:
        value = getattr(kind, "value", None)
        if isinstance(value, str):
            return value
        if isinstance(kind, str):
            return kind
        return str(kind)

    async def record_scheduled(
        self,
        kind: object,
        *,
        immediate: bool,
        adjusted: bool,
    ) -> None:
        key = self._kind_id(kind)
        async with self._lock:
            self._scheduled[key] += 1
            if immediate:
                self._immediate[key] += 1
            if adjusted:
                self._adjusted[key] += 1

    async def record_executed(self, kind: object) -> None:
        key = self._kind_id(kind)
        async with self._lock:
            self._executed[key] += 1

    async def record_skipped(self, kind: object, reason: str) -> None:
        key = self._kind_id(kind)
        label = reason or "unspecified"
        async with self._lock:
            self._skipped[key] += 1
            self._skipped_reasons[f"{key}:{label}"] += 1

    async def snapshot(self) -> ReminderMetricsSnapshot:
        async with self._lock:
            return ReminderMetricsSnapshot(
                scheduled_total=dict(self._scheduled),
                immediate_total=dict(self._immediate),
                adjusted_total=dict(self._adjusted),
                executed_total=dict(self._executed),
                skipped_total=dict(self._skipped),
                skipped_reasons=dict(self._skipped_reasons),
            )

    async def reset(self) -> None:
        async with self._lock:
            self._scheduled.clear()
            self._immediate.clear()
            self._adjusted.clear()
            self._executed.clear()
            self._skipped.clear()
            self._skipped_reasons.clear()


_reminder_metrics = _ReminderMetrics()


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


async def record_notification_poll_cycle(
    *,
    duration: float,
    processed: int,
    source: str,
    skipped_total: int,
    seconds_since_poll: float,
) -> None:
    await _notification_metrics.record_poll_cycle(
        duration_seconds=duration,
        processed=processed,
        source=source,
        skipped_total=skipped_total,
        seconds_since_poll=seconds_since_poll,
    )


async def record_notification_poll_skipped(*, reason: str, skipped_total: int) -> None:
    await _notification_metrics.record_poll_skipped(reason, skipped_total)


async def record_rate_limit_wait(wait_seconds: float) -> None:
    await _notification_metrics.record_rate_limit_wait(wait_seconds)


async def record_notification_poll_backoff(reason: str, delay: float) -> None:
    await _notification_metrics.record_poll_backoff(reason, delay)


async def record_notification_poll_staleness(seconds: float) -> None:
    await _notification_metrics.record_poll_staleness(seconds)


async def get_notification_metrics_snapshot() -> NotificationMetricsSnapshot:
    return await _notification_metrics.snapshot()


async def reset_notification_metrics() -> None:
    await _notification_metrics.reset()


async def record_reminder_scheduled(
    kind: object,
    *,
    immediate: bool = False,
    adjusted: bool = False,
) -> None:
    await _reminder_metrics.record_scheduled(
        kind,
        immediate=immediate,
        adjusted=adjusted,
    )


async def record_reminder_executed(kind: object) -> None:
    await _reminder_metrics.record_executed(kind)


async def record_reminder_skipped(kind: object, reason: str) -> None:
    await _reminder_metrics.record_skipped(kind, reason)


async def get_reminder_metrics_snapshot() -> ReminderMetricsSnapshot:
    return await _reminder_metrics.snapshot()


async def reset_reminder_metrics() -> None:
    await _reminder_metrics.reset()


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
    "record_notification_poll_cycle",
    "record_notification_poll_skipped",
    "record_notification_poll_backoff",
    "record_notification_poll_staleness",
    "record_rate_limit_wait",
    "get_notification_metrics_snapshot",
    "reset_notification_metrics",
    "ReminderMetricsSnapshot",
    "record_reminder_scheduled",
    "record_reminder_executed",
    "record_reminder_skipped",
    "get_reminder_metrics_snapshot",
    "reset_reminder_metrics",
]
