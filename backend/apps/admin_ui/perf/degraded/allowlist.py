"""Allowlist for endpoints that may proceed during DB degraded mode.

Rationale:
- keep UI usable by serving cached snapshots for hot read endpoints
- keep ops endpoints available (/health, /metrics)
"""

from __future__ import annotations

ALLOW_PREFIXES: tuple[str, ...] = (
    "/static",
    "/assets",
    "/app",
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)

ALLOW_PATHS: tuple[str, ...] = (
    "/",
    "/favicon.ico",
    "/.well-known/appspecific/com.chrome.devtools.json",
    # Read-only UX/Ops endpoints can serve cached snapshots even when DB is temporarily degraded.
    "/api/profile",
    "/api/dashboard/summary",
    "/api/dashboard/incoming",
    "/api/calendar/events",
    "/api/notifications/feed",
    "/api/notifications/logs",
    "/api/bot/reminders/jobs",
)

