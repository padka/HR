"""HTTP per-route metrics and cache/degraded markers.

Implemented as ASGI middleware (instead of BaseHTTPMiddleware) to:
- reduce overhead under load
- handle client disconnects during response streaming without noisy tracebacks
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from backend.apps.admin_ui.perf.metrics import context as perf_context
from backend.apps.admin_ui.perf.metrics import prometheus
from backend.core.settings import get_settings


def _route_label(scope: dict[str, Any]) -> str:
    """Return a low-cardinality route label (prefer route template)."""

    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    raw = scope.get("path") or ""
    return str(raw) if raw else "unknown"


def _sanitize_path(path: str) -> str:
    # Best-effort de-cardinalization before routing resolves templates.
    parts = []
    for part in (path or "").split("/"):
        if not part:
            continue
        if part.isdigit():
            parts.append("{id}")
            continue
        if len(part) == 36 and part.count("-") == 4:
            parts.append("{uuid}")
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def _diagnostic_headers_enabled() -> bool:
    settings = get_settings()
    if settings.environment == "production":
        return False
    return os.getenv("PERF_DIAGNOSTIC_HEADERS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _is_client_disconnect(exc: BaseException) -> bool:
    msg = str(exc)
    # uvloop: RuntimeError: unable to perform operation on <TCPTransport closed=True ...>
    return ("TCPTransport closed" in msg) or ("handler is closed" in msg)


class HTTPMetricsMiddleware:
    """Collect per-route latency/rps/error metrics with cache + degraded markers."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "GET")
        # Use raw path early, refine to route template after routing.
        initial_route = _sanitize_path(str(scope.get("path") or ""))
        token = perf_context.set_context(route=initial_route, method=method)

        diagnostic_headers = _diagnostic_headers_enabled()

        prometheus.HTTP_INFLIGHT.inc()
        start = time.perf_counter()
        status_code = 500
        client_disconnected = False

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code, client_disconnected
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)

                # Optional headers for non-prod diagnostics.
                if diagnostic_headers:
                    ctx = perf_context.get_context()
                    if ctx is not None:
                        cache_hits = [ev for ev in ctx.cache_events if ev.state == "hit"]
                        cache_misses = [ev for ev in ctx.cache_events if ev.state != "hit"]
                        stale_hit = any(ev.freshness == "stale" for ev in cache_hits)
                        x_cache = None
                        if stale_hit:
                            x_cache = "STALE"
                        elif cache_hits:
                            x_cache = "HIT"
                        elif cache_misses:
                            x_cache = "MISS"
                        if x_cache:
                            headers = list(message.get("headers") or [])
                            if not any(k.lower() == b"x-cache" for k, _ in headers):
                                headers.append((b"x-cache", x_cache.encode("ascii", "ignore")))
                                message["headers"] = headers

            try:
                await send(message)
            except (BrokenPipeError, ConnectionResetError):
                client_disconnected = True
                return
            except RuntimeError as exc:
                if _is_client_disconnect(exc):
                    client_disconnected = True
                    return
                raise

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = max(0.0, time.perf_counter() - start)
            prometheus.HTTP_INFLIGHT.dec()

            ctx = perf_context.get_context()
            final_route = _route_label(scope)
            if ctx is not None:
                ctx.route = final_route

            degraded = bool(ctx and ctx.degraded_reason)
            if degraded:
                outcome = "degraded"
            elif client_disconnected:
                # Not a server error; the client aborted mid-response.
                outcome = "error"
                status_code = 499
            elif status_code >= 500:
                outcome = "error"
            else:
                outcome = "success"

            prometheus.observe_http(
                route=final_route,
                method=method,
                status_code=status_code,
                outcome=outcome,
                duration_seconds=duration,
            )

            # Cache markers.
            cache_hits = []
            stale_hit = False
            if ctx is not None:
                for ev in ctx.cache_events:
                    if ev.state == "hit":
                        cache_hits.append(ev)
                        if ev.freshness == "stale":
                            stale_hit = True

            if cache_hits:
                # Only count one hit per backend per request.
                by_backend: dict[str, str] = {}
                for ev in cache_hits:
                    prev = by_backend.get(ev.backend)
                    if prev == "stale":
                        continue
                    by_backend[ev.backend] = ev.freshness
                for backend, freshness in by_backend.items():
                    prometheus.observe_cache(route=final_route, backend=backend, freshness=freshness)

            # Per-request DB diagnostics (best-effort).
            if ctx is not None:
                prometheus.HTTP_DB_QUERIES_PER_REQUEST.labels(
                    route=final_route,
                    outcome=outcome,
                ).observe(float(ctx.db_query_count))
                prometheus.HTTP_DB_QUERY_TIME_SECONDS.labels(
                    route=final_route,
                    outcome=outcome,
                ).observe(float(ctx.db_query_seconds))

            perf_context.reset_context(token)
