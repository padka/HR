from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.apps.admin_ui.config import safe_template_response
from backend.apps.admin_ui.services.bot_service import (
    BOT_RUNTIME_AVAILABLE,
    IntegrationSwitch,
)
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.dashboard_calendar import (
    dashboard_calendar_snapshot,
)
from backend.apps.admin_ui.services.kpis import get_weekly_kpis
from backend.core.settings import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _empty_weekly_kpis(timezone: str) -> dict[str, object]:
    placeholder_label = "Нет данных"
    return {
        "timezone": timezone,
        "current": {
            "week_start": None,
            "week_end": None,
            "label": placeholder_label,
            "metrics": [],
        },
        "previous": {
            "week_start": None,
            "week_end": None,
            "label": placeholder_label,
            "metrics": {},
            "computed_at": None,
        },
        "is_placeholder": True,
    }


def _empty_calendar(timezone: str) -> dict[str, object]:
    return {
        "ok": False,
        "selected_date": None,
        "selected_label": "нет данных",
        "selected_human": "",
        "timezone": timezone,
        "days": [],
        "events": [],
        "events_total": 0,
        "status_summary": {
            "CONFIRMED_BY_CANDIDATE": 0,
            "BOOKED": 0,
            "PENDING": 0,
            "CANCELED": 0,
        },
        "meta": "Нет назначенных интервью",
        "updated_label": "",
        "generated_at": None,
        "window_days": 0,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    counts = await dashboard_counts()
    switch: IntegrationSwitch | None = getattr(
        request.app.state, "bot_integration_switch", None
    )
    bot_service = getattr(request.app.state, "bot_service", None)
    settings = get_settings()
    runtime_enabled = (
        switch.is_enabled() if switch else settings.bot_integration_enabled
    )
    health = bot_service.health_status if bot_service else "missing"
    ready = bot_service.is_ready() if bot_service else False
    mode = (
        "real"
        if bot_service and bot_service.configured and BOT_RUNTIME_AVAILABLE
        else "null"
    )
    bot_status = {
        "config_enabled": settings.bot_integration_enabled,
        "runtime_enabled": runtime_enabled,
        "updated_at": switch.updated_at.isoformat() if switch else None,
        "health": health,
        "ready": ready,
        "mode": mode,
    }
    weekly = _empty_weekly_kpis(settings.timezone)
    calendar = _empty_calendar(settings.timezone)
    try:
        weekly = await get_weekly_kpis()
        weekly.pop("is_placeholder", None)
    except Exception:
        logger.exception("Failed to load weekly KPIs for admin dashboard.")
    try:
        calendar = await dashboard_calendar_snapshot(tz_name=settings.timezone)
    except Exception:
        logger.exception("Failed to load dashboard calendar snapshot.")
    return safe_template_response(
        "index.html",
        request,
        {
            "counts": counts,
            "bot_status": bot_status,
            "weekly_kpis": weekly,
            "calendar": calendar,
        },
        encode_json_keys=("weekly_kpis", "calendar"),
    )
