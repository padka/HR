"""DB + pool instrumentation for performance diagnostics.

This module is the canonical home for SQLAlchemy/DB instrumentation. It is
designed for local perf work and is gated by `METRICS_ENABLED` (enabled by
default in non-production).

Design constraints:
- avoid high-cardinality labels
- attribute queries to the current HTTP route via perf context
- keep overhead manageable; production defaults keep metrics disabled
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from sqlalchemy import event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.apps.admin_ui.perf.metrics import context as perf_context
from backend.apps.admin_ui.perf.metrics import prometheus
from backend.core.db import async_session
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

_installed = False


def _truthy_env(name: str) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _sql_profile_enabled() -> bool:
    settings = get_settings()
    if settings.environment == "production":
        return False
    return _truthy_env("DB_PROFILE_ENABLED") or bool(os.getenv("DB_PROFILE_OUTPUT"))


def _sql_profile_sample_rate() -> float:
    raw = os.getenv("DB_PROFILE_SAMPLE_RATE", "0.05") or "0.05"
    try:
        return max(0.0, min(1.0, float(raw)))
    except Exception:
        return 0.05


def _sql_profile_max_keys() -> int:
    raw = os.getenv("DB_PROFILE_MAX_KEYS", "500") or "500"
    try:
        return max(50, int(raw))
    except Exception:
        return 500


_WS_RE = re.compile(r"\s+")
_STR_RE = re.compile(r"'(?:''|[^'])*'")
_NUM_RE = re.compile(r"\b\d+\b")


def _fingerprint_sql(statement: str) -> str:
    """Normalize SQL into a low-cardinality fingerprint for local profiling."""

    s = _WS_RE.sub(" ", (statement or "").strip())
    if not s:
        return "empty"
    s = _STR_RE.sub("?", s)
    s = _NUM_RE.sub("?", s)
    return s[:200]


@dataclass
class _SQLStat:
    count: int = 0
    total_seconds: float = 0.0
    max_seconds: float = 0.0
    example: str = ""
    last_route: str = ""


class SQLProfileCollector:
    """Best-effort in-process SQL profile collector (sampled, bounded)."""

    def __init__(self) -> None:
        self._enabled = _sql_profile_enabled()
        self._sample_rate = _sql_profile_sample_rate()
        self._max_keys = _sql_profile_max_keys()
        self._lock = Lock()
        self._stats: dict[str, _SQLStat] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._enabled and self._sample_rate > 0.0)

    def observe(self, *, statement: str, elapsed_seconds: float, route: str) -> None:
        """Record a query observation (sampled, bounded)."""

        if not self.enabled:
            return
        if self._sample_rate < 1.0 and random.random() > self._sample_rate:
            return
        fp = _fingerprint_sql(statement)
        with self._lock:
            stat = self._stats.get(fp)
            if stat is None:
                if len(self._stats) >= self._max_keys:
                    # Deterministic eviction: clear all (cheap, bounded).
                    self._stats.clear()
                stat = _SQLStat(example=fp, last_route=route)
                self._stats[fp] = stat
            stat.count += 1
            stat.total_seconds += float(elapsed_seconds)
            stat.max_seconds = max(stat.max_seconds, float(elapsed_seconds))
            stat.last_route = route

    def snapshot(self) -> dict[str, _SQLStat]:
        """Return a shallow copy snapshot."""

        with self._lock:
            return dict(self._stats)

    def dump_json(self, path: Path) -> None:
        """Write a JSON summary to disk (best-effort)."""

        snap = self.snapshot()
        items = [
            {
                "fingerprint": fp,
                "count": st.count,
                "total_ms": round(st.total_seconds * 1000.0, 3),
                "max_ms": round(st.max_seconds * 1000.0, 3),
                "last_route": st.last_route,
            }
            for fp, st in snap.items()
        ]
        top_by_total = sorted(items, key=lambda r: r["total_ms"], reverse=True)[:50]
        top_by_count = sorted(items, key=lambda r: r["count"], reverse=True)[:50]
        payload = {
            "sample_rate": self._sample_rate,
            "unique_fingerprints": len(items),
            "top_by_total_ms": top_by_total,
            "top_by_count": top_by_count,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


_SQL_PROFILE = SQLProfileCollector()


async def _sql_profile_flusher(output_path: Path, interval_seconds: float) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            _SQL_PROFILE.dump_json(output_path)
        except Exception:
            # Never fail the app for diagnostics.
            continue


def _metrics_enabled() -> bool:
    settings = get_settings()
    raw = os.getenv("METRICS_ENABLED")
    if raw is None:
        # Enabled by default in non-production to support local perf work.
        return settings.environment != "production"
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _operation(statement: str) -> str:
    head = (statement or "").lstrip().split(None, 1)
    if not head:
        return "unknown"
    op = head[0].lower()
    if op in {"select", "insert", "update", "delete"}:
        return op
    return "other"


def install_sqlalchemy_metrics(async_engine: AsyncEngine) -> None:
    """Install SQLAlchemy engine + pool instrumentation (idempotent).

    Notes:
    - Route attribution relies on perf_context (set by HTTP metrics middleware).
    - In tests, this remains safe; microcache is disabled and these metrics are inert unless scraped.
    """

    global _installed
    if _installed:
        return
    if not _metrics_enabled():
        return

    sync_engine: Engine = async_engine.sync_engine

    slow_threshold_s = float(os.getenv("DB_SLOW_QUERY_SECONDS", "0.2") or "0.2")

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-redef]
        context._perf_query_start = time.perf_counter()  # noqa: SLF001

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-redef]
        start = getattr(context, "_perf_query_start", None)
        if start is None:
            return
        elapsed = max(0.0, time.perf_counter() - float(start))
        ctx = perf_context.get_context()
        route = (ctx.route if ctx and ctx.route else "unknown")
        perf_context.add_db_query(duration_seconds=elapsed)
        op = _operation(statement or "")
        prometheus.DB_QUERIES_TOTAL.labels(route=route, operation=op).inc()
        prometheus.DB_QUERY_DURATION_SECONDS.labels(route=route, operation=op).observe(elapsed)
        if _SQL_PROFILE.enabled:
            _SQL_PROFILE.observe(statement=statement or "", elapsed_seconds=elapsed, route=route)
        if elapsed >= slow_threshold_s:
            prometheus.DB_SLOW_QUERIES_TOTAL.labels(route=route, operation=op).inc()
            # Avoid logging full statements by default; add a short fingerprint for diagnostics.
            stmt_short = " ".join((statement or "").split())[:200]
            logger.warning("Slow query (%.3fs) route=%s op=%s stmt=%s", elapsed, route, op, stmt_short)

    pool = sync_engine.pool

    def _safe_call(name: str) -> float:
        fn = getattr(pool, name, None)
        if fn is None:
            return 0.0
        try:
            return float(fn())
        except Exception:
            return 0.0

    prometheus.DB_POOL_CHECKED_OUT.set_function(lambda: _safe_call("checkedout"))
    prometheus.DB_POOL_SIZE.set_function(lambda: _safe_call("size"))
    prometheus.DB_POOL_OVERFLOW.set_function(lambda: _safe_call("overflow"))

    # Best-effort pool acquisition timing.
    #
    # We wrap the pool's internal `_do_get()` to measure *wait time* under
    # contention (plus any connection creation time when the pool grows).
    #
    # Notes:
    # - This is intended for non-prod perf work; metrics are off in production
    #   by default, and install_sqlalchemy_metrics() is idempotent.
    # - Route attribution relies on perf_context (set by HTTP middleware).
    if not getattr(pool, "_perf_do_get_wrapped", False) and hasattr(pool, "_do_get"):
        try:
            orig_do_get = pool._do_get  # type: ignore[attr-defined]

            def _wrapped_do_get():  # type: ignore[no-redef]
                start = time.perf_counter()
                try:
                    return orig_do_get()
                finally:
                    elapsed = max(0.0, time.perf_counter() - start)
                    ctx = perf_context.get_context()
                    route = (ctx.route if ctx and ctx.route else "unknown")
                    prometheus.DB_POOL_ACQUIRE_SECONDS.labels(route=route).observe(elapsed)

            pool._do_get = _wrapped_do_get  # type: ignore[attr-defined]
            setattr(pool, "_perf_do_get_wrapped", True)
        except Exception:
            logger.exception("Failed to install pool acquisition timing wrapper")

    _installed = True


async def _sample_active_connections_forever(interval_seconds: float = 15.0) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with async_session() as session:
                # Best-effort: pg_stat_activity is only available on PostgreSQL.
                count = await session.scalar(
                    text(
                        "SELECT COUNT(*) FROM pg_stat_activity "
                        "WHERE datname = current_database()"
                    )
                )
            prometheus.DB_ACTIVE_CONNECTIONS.set(float(count or 0))
        except Exception:
            # Unknown / unsupported - keep negative to make it explicit.
            prometheus.DB_ACTIVE_CONNECTIONS.set(-1.0)


def start_db_stats_task() -> asyncio.Task | None:
    """Start a best-effort PostgreSQL connection sampler task.

    Returns:
        asyncio.Task if started, otherwise None.
    """

    if not _metrics_enabled():
        return None

    settings = get_settings()
    try:
        url = make_url(settings.database_url_sync)
        backend = (url.get_backend_name() or "").lower()
    except Exception:
        backend = ""

    if not backend.startswith("postgresql"):
        # Not supported (e.g. sqlite dev db).
        prometheus.DB_ACTIVE_CONNECTIONS.set(-1.0)
        return None

    # Prime with unknown until first sample arrives.
    prometheus.DB_ACTIVE_CONNECTIONS.set(-1.0)
    return asyncio.create_task(
        _sample_active_connections_forever(),
        name="db_active_connections_sampler",
    )


def start_sql_profile_task() -> asyncio.Task | None:
    """Start a best-effort SQL profile flusher when enabled via env.

    Env:
        DB_PROFILE_ENABLED=1
        DB_PROFILE_OUTPUT=.local/perf/sql_profile.json
        DB_PROFILE_FLUSH_SECONDS=10
        DB_PROFILE_SAMPLE_RATE=0.05
    """

    if not _SQL_PROFILE.enabled:
        return None
    output = Path(os.getenv("DB_PROFILE_OUTPUT", ".local/perf/sql_profile.json"))
    interval = float(os.getenv("DB_PROFILE_FLUSH_SECONDS", "10") or "10")
    interval = max(1.0, interval)
    return asyncio.create_task(
        _sql_profile_flusher(output, interval_seconds=interval),
        name="sql_profile_flusher",
    )


__all__ = ["install_sqlalchemy_metrics", "start_db_stats_task", "start_sql_profile_task"]
