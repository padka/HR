"""DB degraded-mode middleware.

Centralized here so degraded policy stays near perf/cache/metrics tooling.

Behavior:
- When `app.state.db_available` is False, most endpoints short-circuit to `503`
  to avoid noisy 500s and long hangs under pool exhaustion.
- A small allowlist of paths is still processed (static/SPA + `/health`, `/metrics`,
  and selected hot read endpoints that can serve from cache).
"""

from __future__ import annotations

from typing import Any, Callable

from starlette.responses import HTMLResponse, JSONResponse

from backend.apps.admin_ui.perf.degraded.allowlist import ALLOW_PATHS, ALLOW_PREFIXES
from backend.apps.admin_ui.perf.metrics.context import mark_degraded


class DegradedDatabaseMiddleware:
    """Short-circuit requests when DB is unavailable to avoid noisy 500s."""

    _allow_prefixes = ALLOW_PREFIXES
    _allow_paths = ALLOW_PATHS

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        root_app = scope.get("app")
        state = getattr(root_app, "state", None)
        db_available = getattr(state, "db_available", True)
        path = str(scope.get("path") or "")
        if not db_available:
            mark_degraded("database_unavailable")
            if path in self._allow_paths or path.startswith(self._allow_prefixes):
                await self.app(scope, receive, send)
                return

            # Header lookup is cheap; avoid instantiating Request/Response just for Accept.
            accepts = ""
            for k, v in (scope.get("headers") or []):
                if k.lower() == b"accept":
                    accepts = v.decode("latin-1", "ignore").lower()
                    break

            payload = {"status": "degraded", "reason": "database_unavailable"}
            if "application/json" in accepts:
                await JSONResponse(payload, status_code=503)(scope, receive, send)
                return
            await HTMLResponse(
                "<h1>Service temporarily degraded</h1>"
                "<p>Database is unavailable. Please try again позже.</p>",
                status_code=503,
            )(scope, receive, send)
            return

        await self.app(scope, receive, send)


__all__ = ["DegradedDatabaseMiddleware"]
