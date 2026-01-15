from datetime import date as date_type, datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.apps.admin_ui.services.cities import (
    api_cities_payload,
    api_city_owners_payload,
)
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.dashboard_calendar import (
    dashboard_calendar_snapshot,
)
from backend.apps.admin_ui.services.candidates import (
    get_candidate_detail,
    update_candidate_status,
)
from backend.apps.admin_ui.services.chat import (
    list_chat_history,
    retry_chat_message,
    send_chat_message,
)
from backend.apps.admin_ui.services.slots import execute_bot_dispatch
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.recruiters import api_recruiters_payload
from backend.apps.admin_ui.services.slots.core import api_slots_payload
from backend.apps.admin_ui.services.templates import (
    api_templates_payload,
    list_known_template_keys,
)
from backend.apps.admin_ui.utils import parse_optional_int, status_filter
from backend.apps.admin_ui.security import require_csrf_token
from backend.core.settings import get_settings
from backend.core.sanitizers import sanitize_plain_text

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def api_health():
    counts = await dashboard_counts()
    return counts


@router.get("/dashboard/calendar")
async def api_dashboard_calendar(
    date: Optional[str] = Query(default=None),
    days: int = Query(default=14, ge=1, le=60),
):
    target_date: Optional[date_type] = None
    if date:
        try:
            target_date = date_type.fromisoformat(date)
        except ValueError:
            return JSONResponse(
                {"ok": False, "error": "invalid_date"}, status_code=400
            )
    snapshot = await dashboard_calendar_snapshot(target_date, days=days)
    return JSONResponse(snapshot)


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


@router.get("/kpis/current")
async def api_weekly_kpis(company_tz: Optional[str] = Query(default=None)):
    return JSONResponse(await get_weekly_kpis(company_tz))


@router.get("/kpis/history")
async def api_weekly_history(
    limit: int = Query(default=12, ge=1, le=104),
    offset: int = Query(default=0, ge=0),
):
    return JSONResponse(await list_weekly_history(limit=limit, offset=offset))


@router.get("/template_keys")
async def api_template_keys():
    return JSONResponse(list_known_template_keys())


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


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string into aware datetime if possible."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный параметр before"},
        )


@router.get("/candidates/{candidate_id}/chat")
async def api_chat_history(
    candidate_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    before: Optional[str] = Query(default=None),
) -> JSONResponse:
    before_dt = _parse_iso_datetime(before)
    payload = await list_chat_history(candidate_id, limit=limit, before=before_dt)
    return JSONResponse(payload)


@router.post("/candidates/{candidate_id}/chat")
async def api_chat_send(
    request: Request,
    candidate_id: int,
    bot_service: BotService = Depends(provide_bot_service),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Ожидался JSON"})

    raw_text = str(data.get("text") or "").strip()
    if not raw_text:
        raise HTTPException(
            status_code=400,
            detail={"message": "Текст сообщения обязателен"},
        )
    text = sanitize_plain_text(raw_text, max_length=2000)
    client_request_id = data.get("client_request_id") or None
    author_label = getattr(request.state, "admin_username", None) or "admin"

    result = await send_chat_message(
        candidate_id,
        text=text,
        client_request_id=client_request_id,
        author_label=author_label,
        bot_service=bot_service,
    )
    return JSONResponse(result)


@router.post("/candidates/{candidate_id}/chat/{message_id}/retry")
async def api_chat_retry(
    candidate_id: int,
    message_id: int,
    bot_service: BotService = Depends(provide_bot_service),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    result = await retry_chat_message(candidate_id, message_id, bot_service=bot_service)
    return JSONResponse(result)


@router.post("/candidates/{candidate_id}/actions/{action_key}")
async def api_candidate_action(
    request: Request,
    candidate_id: int,
    action_key: str,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail={"message": "Кандидат не найден"},
        )

    actions = detail.get("candidate_actions") or []
    action = next((item for item in actions if getattr(item, "key", None) == action_key), None)
    if not action:
        raise HTTPException(
            status_code=400,
            detail={"message": "Действие недоступно для текущего статуса"},
        )
    if (action.method or "GET").upper() != "POST":
        raise HTTPException(
            status_code=400,
            detail={"message": "Действие выполняется как переход по ссылке"},
        )

    if action.target_status:
        ok, message, stored_status, dispatch = await update_candidate_status(
            candidate_id, action.target_status, bot_service=bot_service
        )
        if dispatch is not None and ok:
            plan = getattr(dispatch, "plan", None)
            if plan is not None:
                background_tasks.add_task(
                    execute_bot_dispatch, plan, stored_status or "", bot_service
                )
        status_code = 200 if ok else 400
        return JSONResponse(
            {
                "ok": ok,
                "message": message or "",
                "status": stored_status or action.target_status,
            },
            status_code=status_code,
        )

    raise HTTPException(
        status_code=400,
        detail={"message": "Действие не поддерживается"},
    )
