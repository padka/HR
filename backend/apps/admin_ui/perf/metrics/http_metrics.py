"""HTTP per-route metrics and cache/degraded markers."""

from __future__ import annotations

import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.apps.admin_ui.perf.metrics import context as perf_context
from backend.apps.admin_ui.perf.metrics import prometheus
from backend.core.settings import get_settings


def _route_label(request: Request) -> str:
    """Return a low-cardinality route label (prefer route template)."""

    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    # Fallback: raw path (may include IDs, but should be rare for API routes).
    return request.url.path


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


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    """Collect per-route latency/rps/error metrics with cache + degraded markers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use raw path early, refine to route template after routing.
        initial_route = _sanitize_path(request.url.path)
        token = perf_context.set_context(route=initial_route, method=request.method)
        prometheus.HTTP_INFLIGHT.inc()
        start = time.perf_counter()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = int(getattr(response, "status_code", 500))
            return response
        finally:
            duration = max(0.0, time.perf_counter() - start)
            prometheus.HTTP_INFLIGHT.dec()

            ctx = perf_context.get_context()
            # Refine route label if possible.
            final_route = _route_label(request)
            if ctx is not None:
                ctx.route = final_route

            degraded = bool(ctx and ctx.degraded_reason)
            if degraded:
                outcome = "degraded"
            elif status_code >= 500:
                outcome = "error"
            else:
                outcome = "success"

            prometheus.observe_http(
                route=final_route,
                method=request.method,
                status_code=status_code,
                outcome=outcome,
                duration_seconds=duration,
            )

            # Cache markers.
            cache_hits = []
            cache_misses = []
            stale_hit = False
            if ctx is not None:
                for ev in ctx.cache_events:
                    if ev.state == "hit":
                        cache_hits.append(ev)
                        if ev.freshness == "stale":
                            stale_hit = True
                    else:
                        cache_misses.append(ev)

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

            # Optional headers for non-prod diagnostics.
            if response is not None and _diagnostic_headers_enabled():
                x_cache = None
                if stale_hit:
                    x_cache = "STALE"
                elif cache_hits:
                    x_cache = "HIT"
                elif cache_misses:
                    x_cache = "MISS"
                if x_cache:
                    response.headers.setdefault("X-Cache", x_cache)

            perf_context.reset_context(token)
