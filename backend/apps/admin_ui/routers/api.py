from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from backend.apps.admin_ui.services.cities import (
    api_cities_payload,
    api_city_owners_payload,
)
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.recruiters import api_recruiters_payload
from backend.apps.admin_ui.services.slots import api_slots_payload
from backend.apps.admin_ui.services.templates import api_templates_payload
from backend.apps.admin_ui.utils import parse_optional_int, status_filter
from backend.core.settings import get_settings

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def api_health():
    counts = await dashboard_counts()
    return counts


@router.get("/recruiters")
async def api_recruiters():
    return JSONResponse(await api_recruiters_payload())


@router.get("/cities")
async def api_cities():
    return JSONResponse(await api_cities_payload())


@router.get("/slots")
async def api_slots(
    recruiter_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    recruiter = parse_optional_int(recruiter_id)
    status_norm = status_filter(status)
    payload = await api_slots_payload(recruiter, status_norm, limit)
    return JSONResponse(payload)


@router.get("/templates")
async def api_templates(city_id: Optional[int] = None, key: Optional[str] = None):
    payload = await api_templates_payload(city_id, key)
    status_code = 200
    if isinstance(payload, dict) and payload.get("found") is False:
        status_code = 404
    return JSONResponse(payload, status_code=status_code)


@router.get("/template_keys")
async def api_template_keys():
    return JSONResponse(
        [
            "invite_interview",
            "confirm_interview",
            "after_approval",
            "intro_day_reminder",
            "confirm_2h",
            "reminder_1h",
            "followup_missed",
            "after_meeting",
            "slot_rejected",
        ]
    )


@router.get("/city_owners")
async def api_city_owners():
    payload = await api_city_owners_payload()
    status_code = 200 if payload.get("ok") else 400
    return JSONResponse(payload, status_code=status_code)


@router.get("/bot/integration")
async def api_bot_integration_status(request: Request):
    switch = getattr(request.app.state, "bot_integration_switch", None)
    bot_service = getattr(request.app.state, "bot_service", None)
    settings = get_settings()
    runtime_enabled = (
        switch.is_enabled() if switch else settings.bot_integration_enabled
    )
    payload = {
        "config_enabled": settings.bot_integration_enabled,
        "runtime_enabled": runtime_enabled,
        "updated_at": switch.updated_at.isoformat() if switch else None,
        "service_health": bot_service.health_status if bot_service else "missing",
        "service_ready": bot_service.is_ready() if bot_service else False,
    }
    return JSONResponse(payload)


@router.post("/bot/integration")
async def api_bot_integration_update(request: Request):
    switch = getattr(request.app.state, "bot_integration_switch", None)
    if switch is None:
        return JSONResponse(
            {"ok": False, "error": "switch_unavailable"}, status_code=503
        )

    enabled_value: Optional[bool] = None
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        data = await request.json()
        enabled_value = bool(data.get("enabled"))
    else:
        form = await request.form()
        if "enabled" in form:
            raw = str(form.get("enabled") or "").strip().lower()
            enabled_value = raw in {"1", "true", "yes", "on"}

    if enabled_value is None:
        return JSONResponse(
            {"ok": False, "error": "enabled_not_provided"}, status_code=400
        )

    switch.set(enabled_value)
    bot_service = getattr(request.app.state, "bot_service", None)
    payload = {
        "ok": True,
        "runtime_enabled": switch.is_enabled(),
        "updated_at": switch.updated_at.isoformat(),
        "service_health": bot_service.health_status if bot_service else "missing",
        "service_ready": bot_service.is_ready() if bot_service else False,
    }
    return JSONResponse(payload)
