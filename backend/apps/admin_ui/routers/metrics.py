"""Prometheus metrics endpoint (non-breaking, gated by env)."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from backend.apps.admin_ui.perf.metrics import prometheus as prom_metrics
from backend.core.settings import get_settings

router = APIRouter(tags=["metrics"])


def _metrics_enabled() -> bool:
    settings = get_settings()
    raw = os.getenv("METRICS_ENABLED")
    if raw is None:
        # Enabled by default in non-production to support local perf work.
        return settings.environment != "production"
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    if not _metrics_enabled():
        raise HTTPException(status_code=404)
    prom_metrics.ensure_registered()
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)

