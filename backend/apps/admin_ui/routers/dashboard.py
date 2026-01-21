from __future__ import annotations

import logging
from datetime import date as date_type, datetime, time, timezone

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from backend.apps.admin_ui.config import safe_template_response
from backend.apps.admin_ui.services.bot_service import (
    BOT_RUNTIME_AVAILABLE,
    IntegrationSwitch,
)
from backend.apps.admin_ui.services.dashboard import (
    dashboard_counts,
    get_bot_funnel_stats,
    get_funnel_step_candidates,
    get_pipeline_snapshot,
)
from backend.apps.admin_ui.services.dashboard_calendar import (
    dashboard_calendar_snapshot,
)
from backend.apps.admin_ui.services.kpis import get_weekly_kpis
from backend.apps.admin_ui.utils import parse_optional_int
from backend.core.settings import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_date_param(value: str | None, *, end: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date_type.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный параметр даты"},
        ) from exc
    dt = datetime.combine(parsed, time.max if end else time.min)
    return dt.replace(tzinfo=timezone.utc)


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
    db_available = True
    try:
        counts = await dashboard_counts()
    except Exception:
        logger.exception("Failed to load dashboard counts.")
        db_available = False
        counts = {
            "cities": 0,
            "recruiters": 0,
            "pending": 0,
            "booked": 0,
            "confirmed": 0,
            "total_slots": 0,
            "waiting_candidates": 0,
            "all_slots_total": 0,
        }
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
            "db_available": db_available,
        },
        encode_json_keys=("weekly_kpis", "calendar"),
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_alias(request: Request):
    """Backward-compatible route used by rate limit checks."""
    return await index(request)


@router.get("/dashboard/funnel")
async def dashboard_funnel(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    city: str | None = Query(default=None),
    recruiter: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> JSONResponse:
    date_from = _parse_date_param(from_)
    date_to = _parse_date_param(to, end=True)
    recruiter_id = parse_optional_int(recruiter)
    try:
        payload = await get_bot_funnel_stats(
            date_from=date_from,
            date_to=date_to,
            city=city,
            recruiter_id=recruiter_id,
            source=source,
        )
        snapshot = await get_pipeline_snapshot(
            city=city,
            recruiter_id=recruiter_id,
            source=source,
        )
        payload["snapshot"] = snapshot
        return JSONResponse(payload)
    except Exception:
        logger.exception("Failed to load funnel stats.")
        return JSONResponse({"degraded": True, "error": "funnel_unavailable"})


@router.get("/dashboard/funnel/step")
async def dashboard_funnel_step(
    step: str = Query(...),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    city: str | None = Query(default=None),
    recruiter: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> JSONResponse:
    date_from = _parse_date_param(from_)
    date_to = _parse_date_param(to, end=True)
    recruiter_id = parse_optional_int(recruiter)
    try:
        items = await get_funnel_step_candidates(
            step_key=step,
            date_from=date_from,
            date_to=date_to,
            city=city,
            recruiter_id=recruiter_id,
            source=source,
        )
        return JSONResponse({"items": items})
    except Exception:
        logger.exception("Failed to load funnel step candidates.")
        return JSONResponse({"items": [], "degraded": True})
