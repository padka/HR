from datetime import datetime, timedelta, timezone
import random
from pathlib import Path
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
    get_bot_funnel_stats,
    get_funnel_step_candidates,
    get_recruiter_performance,
    get_recent_activities,
    get_ai_insights,
    get_quick_slots,
    smart_create_candidate,
    format_dashboard_candidate,
    SmartCreateError,
)
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.domain.candidates.status import CandidateStatus
from backend.core.settings import get_settings

router = APIRouter()


def _generate_fake_incoming(count: int) -> list[dict]:
    """Generate synthetic incoming candidates for demo/dev UI."""
    now = datetime.now(timezone.utc)
    cities = ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск", "Самара", "Удалённо"]
    rows: list[dict] = []
    for idx in range(1, count + 1):
        wait_hours = random.randint(1, 120)
        waiting_since = now - timedelta(hours=wait_hours)
        rows.append(
            {
                "id": -idx,
                "name": f"Тестовый кандидат {idx:03d}",
                "city": random.choice(cities),
                "status_display": "Ждет назначения слота",
                "status_color": "warning",
                "status_slug": CandidateStatus.WAITING_SLOT.value,
                "waiting_since": waiting_since,
                "waiting_hours": wait_hours,
                "availability_window": "Сегодня · 14:00–18:00",
                "availability_note": "Готов созвониться в ближайшие часы",
                "tz": "Europe/Moscow",
                "telegram_id": None,
                "telegram_user_id": None,
                "telegram_username": None,
                "schedule_url": "#",
                "profile_url": "#",
                "priority_score": random.randint(1, 99),
            }
        )
    return rows


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    recruiter_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    recruiter_id_int: int | None = None
    if not getattr(request.app.state, "db_available", True):
        counts = {"waiting_candidates_total": 0}
        recruiters = []
        cities = []
        recent_candidates = []
        upcoming_interviews = []
        interview_events = []
        intro_day_events = []
        hiring_funnel = {"summary": {}, "stages": []}
        recruiter_performance = []
        recent_activities = []
        ai_insights = {}
        quick_slots = []
        incoming_candidates_all = []
        incoming_candidates_top = []
        incoming_candidates_rest = []
        incoming_candidates = []
    else:
        counts = await dashboard_counts()
        recruiter_rows = await list_recruiters()
        recruiters = [row["rec"] for row in recruiter_rows]
        cities = await list_cities()

        # Get dashboard data
        recent_candidates = await get_recent_candidates(limit=5)
        # Берём больше слотов, чтобы все одобренные брони (в т.ч. свежие) попали в календарь.
        parsed_date_from = _parse_date(date_from)
        parsed_date_to = _parse_date(date_to, is_end=True)
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
        interview_events = [
            ev for ev in upcoming_interviews if (ev.get("event_kind") or "").lower() != "ознакомительный день"
        ]
        intro_day_events = [
            ev for ev in upcoming_interviews if (ev.get("event_kind") or "").lower() == "ознакомительный день"
        ]
        hiring_funnel = await get_hiring_funnel_stats()
        recruiter_performance = await get_recruiter_performance()
        recent_activities = await get_recent_activities(limit=10)
        ai_insights = await get_ai_insights()
        quick_slots = await get_quick_slots()
        incoming_candidates_all = await get_waiting_candidates(limit=120)
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
            "db_available": getattr(request.app.state, "db_available", True),
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
            "funnel_summary": hiring_funnel.get("summary", {}),
            "funnel_stages": hiring_funnel.get("stages", []),
            "recruiter_performance": recruiter_performance,
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


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_alias(
    request: Request,
    recruiter_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    return await index(
        request,
        recruiter_id=recruiter_id,
        date_from=date_from,
        date_to=date_to,
    )


def _parse_date(value: str | None, *, is_end: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        if "T" not in value:
            dt = datetime.fromisoformat(value)
            if is_end:
                dt = dt + timedelta(days=1) - timedelta(microseconds=1)
            return dt.replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/dashboard/funnel")
async def dashboard_funnel(
    request: Request,
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    city: str | None = Query(default=None),
    recruiter: int | None = Query(default=None),
    source: str | None = Query(default=None),
):
    if not getattr(request.app.state, "db_available", True):
        return JSONResponse(
            {
                "range": {"from": None, "to": None, "ttl_hours": None},
                "steps": [],
                "dropoffs": {},
                "series": {"labels": [], "entered": [], "test1_completed": []},
                "last_period_comparison": None,
                "degraded": True,
            }
        )
    payload = await get_bot_funnel_stats(
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to, is_end=True),
        city=city,
        recruiter_id=recruiter,
        source=source,
    )
    payload["degraded"] = False
    return JSONResponse(payload)


@router.get("/dashboard/funnel/step")
async def dashboard_funnel_step(
    request: Request,
    step: str = Query(...),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    city: str | None = Query(default=None),
    recruiter: int | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
):
    if not getattr(request.app.state, "db_available", True):
        return JSONResponse({"items": [], "degraded": True})
    items = await get_funnel_step_candidates(
        step_key=step,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to, is_end=True),
        city=city,
        recruiter_id=recruiter,
        source=source,
        limit=limit,
    )
    return JSONResponse({"items": items, "degraded": False})


_ALLOWED_RESUME_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}
_ALLOWED_RESUME_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAX_RESUME_BYTES = 5 * 1024 * 1024


async def _validate_resume_upload(resume: UploadFile) -> Optional[str]:
    """Basic validation for uploaded resumes to avoid dangerous payloads."""
    filename = resume.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_RESUME_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_RESUME_EXTENSIONS))
        return f"Недопустимый формат файла. Разрешены: {allowed}"

    content_type = (resume.content_type or "").lower()
    if content_type and content_type not in _ALLOWED_RESUME_MIME:
        return "Недопустимый тип файла. Загрузите PDF, PNG, JPG или DOCX."

    payload = await resume.read(_MAX_RESUME_BYTES + 1)
    if len(payload) > _MAX_RESUME_BYTES:
        return "Файл слишком большой. Максимальный размер — 5 МБ."
    try:
        resume.file.seek(0)
    except Exception:
        pass
    return None


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
    if resume:
        validation_error = await _validate_resume_upload(resume)
        if validation_error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": validation_error},
            )

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
