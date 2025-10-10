<<<<<<< HEAD
import logging
=======
from __future__ import annotations
>>>>>>> b3672573975ada7003f245221393aee8f94a23f1

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.bot_service import (
    BOT_RUNTIME_AVAILABLE,
    IntegrationSwitch,
)
from backend.apps.admin_ui.services.dashboard import dashboard_counts

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
<<<<<<< HEAD
    weekly = _empty_weekly_kpis(settings.timezone)
    try:
        weekly = await get_weekly_kpis()
        weekly.pop("is_placeholder", None)
    except Exception:
        logger.exception("Failed to load weekly KPIs for admin dashboard.")
=======

>>>>>>> b3672573975ada7003f245221393aee8f94a23f1
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "counts": counts,
            "bot_status": bot_status,

        },
    )
