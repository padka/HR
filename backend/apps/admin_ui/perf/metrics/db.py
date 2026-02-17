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
import logging
import os
import time

from sqlalchemy import event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.apps.admin_ui.perf.metrics import context as perf_context
from backend.apps.admin_ui.perf.metrics import prometheus
from backend.core.db import async_session
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

_installed = False


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


__all__ = ["install_sqlalchemy_metrics", "start_db_stats_task"]

