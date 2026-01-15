#!/usr/bin/env python
"""Generate synthetic notifications to measure enqueue/latency."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, List

from backend.apps.bot.broker import InMemoryNotificationBroker, NotificationBroker
from backend.apps.bot.services import NotificationService
from backend.core.settings import get_settings

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Redis = None  # type: ignore

METRIC_FIELDS = [
    "count",
    "target_count",
    "duration_sec",
    "duration_limit_sec",
    "avg_publish_sec",
    "max_publish_sec",
    "p95_publish_sec",
    "throughput_per_sec",
    "broker",
    "rate_limit",
    "batch_size",
    "poll_interval",
    "started_at",
    "finished_at",
]  # order matters for CSV dumps


def _build_broker(args, settings):
    if args.broker == "redis":
        if Redis is None:
            raise RuntimeError("redis-py is not installed")
        redis_url = args.redis_url or settings.redis_url
        if not redis_url:
            raise RuntimeError("Redis URL must be provided via --redis-url or REDIS_URL")
        client = Redis.from_url(redis_url)
        return NotificationBroker(client)
    return InMemoryNotificationBroker()


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * (percentile / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[int(rank)]
    low_value = sorted_values[low]
    high_value = sorted_values[high]
    return low_value + (high_value - low_value) * (rank - low)


def _write_json(path: Path, metrics: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def _write_csv(path: Path, metrics: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: metrics.get(field) for field in METRIC_FIELDS})


async def run_load(args):
    settings = get_settings()
    broker = _build_broker(args, settings)
    await broker.start()
    service = NotificationService(
        broker=broker,
        poll_interval=args.poll_interval,
        batch_size=args.batch_size,
        rate_limit_per_sec=args.rate_limit,
        max_attempts=settings.notification_max_attempts,
        retry_base_delay=settings.notification_retry_base_seconds,
        retry_max_delay=settings.notification_retry_max_seconds,
    )
    service.start(allow_poll_loop=True)

    latencies: List[float] = []
    count_target = max(0, args.count)
    duration_limit = max(0.0, args.duration)
    published = 0
    started_at = datetime.now(timezone.utc)
    start_perf = time.perf_counter()
    deadline = start_perf + duration_limit if duration_limit else None

    try:
        while True:
            if count_target and published >= count_target:
                break
            if deadline is not None and time.perf_counter() >= deadline:
                break
            payload = {
                "outbox_id": published + 1,
                "attempt": 0,
                "max_attempts": settings.notification_max_attempts,
            }
            enqueue_ts = time.perf_counter()
            await broker.publish(payload)
            latencies.append(time.perf_counter() - enqueue_ts)
            published += 1
    finally:
        elapsed = time.perf_counter() - start_perf
        finished_at = datetime.now(timezone.utc)
        avg_latency = mean(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0
        throughput = published / elapsed if elapsed else 0.0
        metrics = {
            "count": published,
            "target_count": count_target,
            "duration_sec": round(elapsed, 2),
            "duration_limit_sec": duration_limit,
            "avg_publish_sec": round(avg_latency, 6),
            "max_publish_sec": round(max_latency, 6),
            "p95_publish_sec": round(_percentile(latencies, 95.0), 6) if latencies else 0.0,
            "throughput_per_sec": round(throughput, 2),
            "broker": args.broker,
            "rate_limit": args.rate_limit,
            "batch_size": args.batch_size,
            "poll_interval": args.poll_interval,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }
        print(json.dumps(metrics, indent=2))
        if args.metrics_json:
            _write_json(Path(args.metrics_json), metrics)
        if args.metrics_csv:
            _write_csv(Path(args.metrics_csv), metrics)
        await service.shutdown()
        await broker.close()


def main():
    parser = argparse.ArgumentParser(description="Notification broker load tester")
    parser.add_argument("--count", type=int, default=100, help="Number of notifications to publish (0 to disable)")
    parser.add_argument("--duration", type=float, default=0.0, help="Duration in seconds (0 to disable)")
    parser.add_argument("--broker", choices=["memory", "redis"], default="memory")
    parser.add_argument("--redis-url", dest="redis_url", default="", help="Redis URL override")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--rate-limit", type=float, default=5.0)
    parser.add_argument("--metrics-json", dest="metrics_json", default="", help="Optional path to store JSON summary")
    parser.add_argument("--metrics-csv", dest="metrics_csv", default="", help="Optional path to append CSV summary")
    args = parser.parse_args()
    asyncio.run(run_load(args))


if __name__ == "__main__":
    main()
