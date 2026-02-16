"""Prometheus metrics for admin_ui performance engineering.

Design goals:
- per-route visibility (route template when available)
- separate outcomes: success vs degraded vs error
- safe, low-cardinality labels (no user IDs / PII)
- minimal overhead on the request path

Note: quantiles (p50/p95/p99) are exposed as *approximate* rolling-window gauges
to make diagnostics trivial during local load testing. Histograms are also exported
for accurate Prometheus-side quantiles/recording rules.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable
from threading import Lock

from prometheus_client import REGISTRY, Counter, Gauge, Histogram
from prometheus_client.core import GaugeMetricFamily

from backend.apps.admin_ui.perf.metrics import context as perf_context

# ----------------------------
# HTTP metrics
# ----------------------------

HTTP_INFLIGHT = Gauge(
    "http_inflight_requests",
    "Number of in-flight HTTP requests (global).",
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests by route/method/status/outcome.",
    labelnames=("route", "method", "status", "outcome"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds by route/method/status/outcome.",
    labelnames=("route", "method", "status", "outcome"),
    # Bias buckets towards sub-second latencies, but keep tail visibility.
    buckets=(
        0.001,
        0.0025,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "HTTP errors by route/method/status/outcome (only outcome!=success).",
    labelnames=("route", "method", "status", "outcome"),
)

HTTP_SERVED_FROM_CACHE_TOTAL = Counter(
    "served_from_cache_total",
    "Responses served from cache by route and backend.",
    labelnames=("route", "backend"),
)

HTTP_SERVED_STALE_TOTAL = Counter(
    "served_stale_total",
    "Responses served stale (degraded mode) by route and backend.",
    labelnames=("route", "backend"),
)

HTTP_DB_QUERIES_PER_REQUEST = Histogram(
    "http_db_queries_per_request",
    "Number of DB queries executed during a single HTTP request (best-effort).",
    labelnames=("route", "outcome"),
    buckets=(0, 1, 2, 5, 10, 20, 50, 100, 200),
)

HTTP_DB_QUERY_TIME_SECONDS = Histogram(
    "http_db_query_time_seconds",
    "Total DB time spent during a single HTTP request in seconds (best-effort).",
    labelnames=("route", "outcome"),
    buckets=(
        0.0005,
        0.001,
        0.0025,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

# ----------------------------
# DB metrics
# ----------------------------

DB_QUERIES_TOTAL = Counter(
    "db_queries_total",
    "Total number of DB queries executed, labeled by route and operation.",
    labelnames=("route", "operation"),
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "DB query latency in seconds, labeled by route and operation.",
    labelnames=("route", "operation"),
    buckets=(
        0.0005,
        0.001,
        0.0025,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
    ),
)

DB_SLOW_QUERIES_TOTAL = Counter(
    "db_slow_queries_total",
    "Slow DB queries (above threshold), labeled by route and operation.",
    labelnames=("route", "operation"),
)

DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out",
    "SQLAlchemy pool checked-out connections (best-effort).",
)
DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "SQLAlchemy pool size (best-effort).",
)
DB_POOL_OVERFLOW = Gauge(
    "db_pool_overflow",
    "SQLAlchemy pool overflow (best-effort).",
)
DB_POOL_TIMEOUTS_TOTAL = Counter(
    "db_pool_timeouts_total",
    "Total pool timeout errors observed (best-effort).",
)
DB_TOO_MANY_CONNECTIONS_TOTAL = Counter(
    "db_too_many_connections_total",
    "Total asyncpg TooManyConnectionsError observed (best-effort).",
)

DB_POOL_ACQUIRE_SECONDS = Histogram(
    "db_pool_acquire_seconds",
    "Time spent acquiring a DB connection from the SQLAlchemy pool (best-effort), labeled by route.",
    labelnames=("route",),
    buckets=(
        0.0005,
        0.001,
        0.0025,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        30.0,
    ),
)
# Ensure the metric exists in `/metrics` even before the first observation.
DB_POOL_ACQUIRE_SECONDS.labels(route="unknown")

DB_ACTIVE_CONNECTIONS = Gauge(
    "db_active_connections",
    "Active DB connections (pg_stat_activity, best-effort; -1 when unknown).",
)


# ----------------------------
# Rolling quantiles collector
# ----------------------------

_LatencyKey = tuple[str, str, str, str]  # route, method, status, outcome


class _LatencyWindow:
    def __init__(self, *, max_samples: int = 1024) -> None:
        self._max_samples = max_samples
        self._lock = Lock()
        self._samples: dict[_LatencyKey, deque[float]] = {}

    def record(self, key: _LatencyKey, value: float) -> None:
        with self._lock:
            dq = self._samples.get(key)
            if dq is None:
                dq = deque(maxlen=self._max_samples)
                self._samples[key] = dq
            dq.append(value)

    def snapshot(self) -> dict[_LatencyKey, list[float]]:
        with self._lock:
            return {k: list(v) for k, v in self._samples.items()}


_LAT_WINDOW = _LatencyWindow(max_samples=2048)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values.sort()
    n = len(values)
    # Nearest-rank (1-indexed) quantile.
    rank = int(math.ceil(q * n))
    idx = max(0, min(n - 1, rank - 1))
    return float(values[idx])


class _LatencyQuantilesCollector:
    """Expose per-route rolling quantiles as gauges for easy diagnostics."""

    def collect(self) -> Iterable[GaugeMetricFamily]:
        snap = _LAT_WINDOW.snapshot()

        p50 = GaugeMetricFamily(
            "latency_p50_seconds",
            "Approx rolling-window p50 latency in seconds.",
            labels=("route", "method", "status", "outcome"),
        )
        p95 = GaugeMetricFamily(
            "latency_p95_seconds",
            "Approx rolling-window p95 latency in seconds.",
            labels=("route", "method", "status", "outcome"),
        )
        p99 = GaugeMetricFamily(
            "latency_p99_seconds",
            "Approx rolling-window p99 latency in seconds.",
            labels=("route", "method", "status", "outcome"),
        )

        for (route, method, status, outcome), vals in snap.items():
            if not vals:
                continue
            q50 = _quantile(vals, 0.50)
            q95 = _quantile(vals, 0.95)
            q99 = _quantile(vals, 0.99)
            if q50 is not None:
                p50.add_metric([route, method, status, outcome], q50)
            if q95 is not None:
                p95.add_metric([route, method, status, outcome], q95)
            if q99 is not None:
                p99.add_metric([route, method, status, outcome], q99)

        yield p50
        yield p95
        yield p99


_collector_registered = False


def ensure_registered() -> None:
    """Register custom collectors once per process."""

    global _collector_registered
    if _collector_registered:
        return
    REGISTRY.register(_LatencyQuantilesCollector())
    _collector_registered = True


def observe_http(
    *,
    route: str,
    method: str,
    status_code: int,
    outcome: str,
    duration_seconds: float,
) -> None:
    """Record a single HTTP request observation."""

    status = str(int(status_code))
    HTTP_REQUESTS_TOTAL.labels(route=route, method=method, status=status, outcome=outcome).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        route=route, method=method, status=status, outcome=outcome
    ).observe(duration_seconds)

    if outcome != "success":
        HTTP_ERRORS_TOTAL.labels(route=route, method=method, status=status, outcome=outcome).inc()

    ensure_registered()
    _LAT_WINDOW.record((route, method, status, outcome), duration_seconds)


def observe_cache(*, route: str, backend: str, freshness: str) -> None:
    """Record cache markers for the current request."""

    HTTP_SERVED_FROM_CACHE_TOTAL.labels(route=route, backend=backend).inc()
    if freshness == "stale":
        HTTP_SERVED_STALE_TOTAL.labels(route=route, backend=backend).inc()


def current_route_label() -> str:
    """Return best-known route label for the current request."""

    ctx = perf_context.get_context()
    if ctx is None:
        return "unknown"
    return ctx.route or "unknown"
