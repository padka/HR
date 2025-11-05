"""Performance monitoring and metrics collection.

This module provides:
- Request timing
- Query performance tracking
- Cache hit rate monitoring
- System resource metrics
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, DefaultDict

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    endpoint: str
    method: str
    start_time: datetime
    duration_ms: float
    status_code: int
    query_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass
class QueryMetrics:
    """Metrics for database queries."""

    operation: str
    duration_ms: float
    timestamp: datetime
    slow_query: bool = False


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total * 100

    @property
    def total_operations(self) -> int:
        """Total cache operations."""
        return self.hits + self.misses + self.sets + self.deletes


@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""

    requests: DefaultDict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    queries: list[QueryMetrics] = field(default_factory=list)
    cache: CacheMetrics = field(default_factory=CacheMetrics)
    slow_query_threshold_ms: float = 100.0
    slow_request_threshold_ms: float = 1000.0

    def record_request(self, endpoint: str, duration_ms: float) -> None:
        """Record request duration."""
        self.requests[endpoint].append(duration_ms)

    def record_query(self, operation: str, duration_ms: float) -> None:
        """Record query execution."""
        is_slow = duration_ms > self.slow_query_threshold_ms
        self.queries.append(
            QueryMetrics(
                operation=operation,
                duration_ms=duration_ms,
                timestamp=datetime.utcnow(),
                slow_query=is_slow,
            )
        )

        if is_slow:
            logger.warning(
                f"Slow query detected: {operation} took {duration_ms:.2f}ms "
                f"(threshold: {self.slow_query_threshold_ms}ms)"
            )

    def record_cache_hit(self) -> None:
        """Record cache hit."""
        self.cache.hits += 1

    def record_cache_miss(self) -> None:
        """Record cache miss."""
        self.cache.misses += 1

    def record_cache_set(self) -> None:
        """Record cache set operation."""
        self.cache.sets += 1

    def record_cache_delete(self) -> None:
        """Record cache delete operation."""
        self.cache.deletes += 1

    def record_cache_error(self) -> None:
        """Record cache error."""
        self.cache.errors += 1

    def get_endpoint_stats(self, endpoint: str) -> dict[str, Any]:
        """Get statistics for specific endpoint."""
        durations = self.requests.get(endpoint, [])

        if not durations:
            return {
                "endpoint": endpoint,
                "count": 0,
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }

        sorted_durations = sorted(durations)
        count = len(sorted_durations)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)

        return {
            "endpoint": endpoint,
            "count": count,
            "avg_ms": sum(durations) / count,
            "min_ms": min(durations),
            "max_ms": max(durations),
            "p95_ms": sorted_durations[p95_idx] if p95_idx < count else sorted_durations[-1],
            "p99_ms": sorted_durations[p99_idx] if p99_idx < count else sorted_durations[-1],
        }

    def get_all_endpoint_stats(self) -> list[dict[str, Any]]:
        """Get statistics for all endpoints."""
        return [self.get_endpoint_stats(endpoint) for endpoint in self.requests.keys()]

    def get_slow_queries(self) -> list[QueryMetrics]:
        """Get all slow queries."""
        return [q for q in self.queries if q.slow_query]

    def get_query_stats(self) -> dict[str, Any]:
        """Get aggregated query statistics."""
        if not self.queries:
            return {
                "total_queries": 0,
                "avg_duration_ms": 0.0,
                "slow_queries": 0,
                "slow_query_rate": 0.0,
            }

        durations = [q.duration_ms for q in self.queries]
        slow_count = len(self.get_slow_queries())

        return {
            "total_queries": len(self.queries),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "slow_queries": slow_count,
            "slow_query_rate": slow_count / len(self.queries) * 100,
        }

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "hits": self.cache.hits,
            "misses": self.cache.misses,
            "hit_rate": self.cache.hit_rate,
            "sets": self.cache.sets,
            "deletes": self.cache.deletes,
            "errors": self.cache.errors,
            "total_operations": self.cache.total_operations,
        }

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all metrics."""
        return {
            "endpoints": self.get_all_endpoint_stats(),
            "queries": self.get_query_stats(),
            "cache": self.get_cache_stats(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self.requests.clear()
        self.queries.clear()
        self.cache = CacheMetrics()

    def cleanup_old_data(self, max_age: timedelta = timedelta(hours=1)) -> None:
        """Remove metrics older than max_age."""
        cutoff = datetime.utcnow() - max_age

        # Clean up old queries
        self.queries = [q for q in self.queries if q.timestamp > cutoff]


# Global metrics instance
_metrics: PerformanceStats | None = None


def get_metrics() -> PerformanceStats:
    """Get global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = PerformanceStats()
    return _metrics


def reset_metrics() -> None:
    """Reset global metrics."""
    global _metrics
    _metrics = PerformanceStats()


class PerformanceTimer:
    """
    Context manager for timing operations.

    Usage:
        with PerformanceTimer("database_query") as timer:
            result = await execute_query()
        print(f"Query took {timer.elapsed_ms}ms")
    """

    def __init__(self, operation: str, record_to_metrics: bool = True):
        self.operation = operation
        self.record_to_metrics = record_to_metrics
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def __enter__(self) -> PerformanceTimer:
        """Start timer."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timer and record metrics."""
        self.end_time = time.time()

        if self.record_to_metrics:
            metrics = get_metrics()
            metrics.record_query(self.operation, self.elapsed_ms)

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.end_time == 0.0:
            # Still running
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000


def timed(operation: str | None = None) -> Callable:
    """
    Decorator to time function execution.

    Usage:
        @timed("get_users")
        async def get_users():
            ...
    """

    def decorator(func: Callable) -> Callable:
        op_name = operation or f"{func.__module__}.{func.__name__}"

        async def async_wrapper(*args, **kwargs):
            with PerformanceTimer(op_name):
                return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            with PerformanceTimer(op_name):
                return func(*args, **kwargs)

        # Check if function is async
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Logging helpers
def log_performance_summary() -> None:
    """Log performance summary."""
    metrics = get_metrics()
    summary = metrics.get_summary()

    logger.info("=== Performance Summary ===")
    logger.info(f"Cache hit rate: {summary['cache']['hit_rate']:.2f}%")
    logger.info(f"Total queries: {summary['queries']['total_queries']}")
    logger.info(f"Slow queries: {summary['queries']['slow_queries']}")

    if summary['endpoints']:
        logger.info("Top endpoints:")
        for ep_stats in sorted(
            summary['endpoints'], key=lambda x: x['avg_ms'], reverse=True
        )[:5]:
            logger.info(
                f"  {ep_stats['endpoint']}: "
                f"{ep_stats['count']} requests, "
                f"avg {ep_stats['avg_ms']:.2f}ms"
            )
