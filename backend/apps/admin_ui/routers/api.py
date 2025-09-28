from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.apps.admin_ui.utils import parse_optional_int, status_filter
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.recruiters import api_recruiters_payload
from backend.apps.admin_ui.services.cities import (
    api_cities_payload,
    api_city_owners_payload,
)
from backend.apps.admin_ui.services.slots import api_slots_payload
from backend.apps.admin_ui.services.templates import api_templates_payload

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
