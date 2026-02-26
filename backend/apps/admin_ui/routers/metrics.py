"""Prometheus metrics endpoint (non-breaking, gated by env)."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from backend.apps.admin_ui.perf.metrics import prometheus as prom_metrics
from backend.apps.admin_ui.security import get_client_ip, try_get_current_principal
from backend.core.settings import get_settings

router = APIRouter(tags=["metrics"])
_DEFAULT_METRICS_IP_ALLOWLIST = {"127.0.0.1", "::1", "localhost", "testclient"}


def _metrics_enabled() -> bool:
    settings = get_settings()
    raw = os.getenv("METRICS_ENABLED")
    if raw is None:
        # Enabled by default in non-production to support local perf work.
        return settings.environment != "production"
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _metrics_allowlisted_ips() -> set[str]:
    raw = os.getenv("METRICS_IP_ALLOWLIST")
    if raw is None:
        return set(_DEFAULT_METRICS_IP_ALLOWLIST)
    parsed = {
        item.strip().lower()
        for item in raw.split(",")
        if item and item.strip()
    }
    return parsed or set(_DEFAULT_METRICS_IP_ALLOWLIST)


def _is_metrics_client_allowlisted(request: Request) -> bool:
    ip = get_client_ip(request).strip().lower()
    return ip in _metrics_allowlisted_ips()


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    if not _metrics_enabled():
        raise HTTPException(status_code=404)
    principal = await try_get_current_principal(request)
    if principal is None and not _is_metrics_client_allowlisted(request):
        raise HTTPException(status_code=403, detail="Metrics access forbidden")
    prom_metrics.ensure_registered()
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
