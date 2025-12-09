from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, File, Form, UploadFile, Query
from fastapi.responses import HTMLResponse, JSONResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.bot_service import (
    BOT_RUNTIME_AVAILABLE,
    IntegrationSwitch,
)
from backend.apps.admin_ui.services.cities import list_cities
from backend.apps.admin_ui.services.dashboard import (
    dashboard_counts,
    get_recent_candidates,
    get_waiting_candidates,
    get_upcoming_interviews,
    get_hiring_funnel_stats,
    get_recent_activities,
    get_ai_insights,
    get_quick_slots,
    smart_create_candidate,
    format_dashboard_candidate,
    SmartCreateError,
)
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.core.settings import get_settings

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    recruiter_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    counts = await dashboard_counts()
    recruiter_rows = await list_recruiters()
    recruiters = [row["rec"] for row in recruiter_rows]
    cities = await list_cities()

    # Get dashboard data
    recent_candidates = await get_recent_candidates(limit=5)
    # Берём больше слотов, чтобы все одобренные брони (в т.ч. свежие) попали в календарь.
    parsed_date_from = _parse_date(date_from)
    parsed_date_to = _parse_date(date_to)
    recruiter_id_int: int | None = None
    if recruiter_id:
        try:
            recruiter_id_int = int(recruiter_id)
        except ValueError:
            recruiter_id_int = None
    upcoming_interviews = await get_upcoming_interviews(
        limit=20,
        recruiter_id=recruiter_id_int,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
    )
    interview_events = [ev for ev in upcoming_interviews if (ev.get("event_kind") or "").lower() != "ознакомительный день"]
    intro_day_events = [ev for ev in upcoming_interviews if (ev.get("event_kind") or "").lower() == "ознакомительный день"]
    hiring_funnel = await get_hiring_funnel_stats()
    recent_activities = await get_recent_activities(limit=10)
    ai_insights = await get_ai_insights()
    quick_slots = await get_quick_slots()
    incoming_candidates_all = await get_waiting_candidates(limit=80)
    incoming_candidates_top = incoming_candidates_all[:12]
    incoming_candidates_rest = incoming_candidates_all[12:]
    incoming_candidates = incoming_candidates_top
    # Placeholder analytics until proper calculations are wired
    analytics = {
        "hire_time_median_days": None,
        "hire_conversion_pct": None,
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
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "counts": counts,
            "recruiters": recruiters,
            "cities": cities,
            "recent_candidates": recent_candidates,
            "incoming_candidates": incoming_candidates,
            "incoming_candidates_top": incoming_candidates_top,
            "incoming_candidates_rest": incoming_candidates_rest,
            "incoming_candidates_all": incoming_candidates_all,
            "upcoming_interviews": upcoming_interviews,
            "upcoming_interviews_main": interview_events,
            "upcoming_intro_days": intro_day_events,
            "hiring_funnel": hiring_funnel,
            "recent_activities": recent_activities,
            "ai_insights": ai_insights,
            "bot_status": bot_status,
            "quick_slots": quick_slots,
            "analytics": analytics,
            "upcoming_filter_recruiter": recruiter_id_int,
            "upcoming_filter_date_from": date_from or "",
            "upcoming_filter_date_to": date_to or "",
        },
    )


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return dt


@router.post("/smart-create")
async def smart_create_candidate_action(
    name: str = Form(...),
    position: str = Form(""),
    stage: str = Form("new"),
    slot_id: str = Form(""),
    resume: Optional[UploadFile] = File(None),
):
    slot_value: Optional[int] = None
    if slot_id:
        try:
            slot_value = int(slot_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Некорректный слот."},
            )

    resume_name = resume.filename if resume else None

    try:
        user, booked_slot_id = await smart_create_candidate(
            name=name,
            position=position or None,
            stage=stage,
            slot_id=slot_value,
            resume_filename=resume_name,
        )
    except SmartCreateError as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(exc)},
        )

    candidate_payload = format_dashboard_candidate(user)
    return JSONResponse(
        {
            "success": True,
            "candidate": candidate_payload,
            "booked_slot_id": booked_slot_id,
        }
    )
