from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError

from backend.apps.admin_ui.services.cities import (
    api_cities_payload,
    api_city_owners_payload,
    get_city_capacity,
)
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.recruiters import (
    RecruiterValidationError,
    api_get_recruiter,
    api_recruiters_payload,
    build_recruiter_payload,
    create_recruiter,
    update_recruiter,
)
from backend.apps.admin_ui.services.slots import api_slots_payload
from backend.apps.admin_ui.services.templates import api_templates_payload
from backend.apps.admin_ui.utils import parse_optional_int, status_filter
from backend.apps.admin_ui.timezones import DEFAULT_TZ
from backend.apps.admin_ui.services.candidates import api_candidate_detail_payload
from backend.apps.admin_ui.services.notifications import notification_feed
from backend.apps.admin_ui.services.chat import (
    get_chat_templates,
    list_chat_history,
    send_chat_message as service_send_chat_message,
    retry_chat_message,
)
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.security import require_csrf_token
from backend.core.settings import get_settings

router = APIRouter(prefix="/api", tags=["api"])


class RecruiterPayload(BaseModel):
    name: str = Field(..., min_length=1)
    tz: Optional[str] = Field(default=DEFAULT_TZ)
    telemost: Optional[str] = None
    tg_chat_id: Optional[int] = Field(default=None, ge=1)
    active: Optional[bool] = True
    city_ids: List[int] = Field(default_factory=list)

    def tz_value(self) -> str:
        value = (self.tz or DEFAULT_TZ).strip()
        return value or DEFAULT_TZ

    def chat_id_str(self) -> str:
        return str(self.tg_chat_id) if self.tg_chat_id is not None else ""

    def city_values(self) -> List[str]:
        return [str(cid) for cid in self.city_ids if cid is not None]


class ChatSendPayload(BaseModel):
    text: Optional[str] = Field(default=None, max_length=2000)
    template_key: Optional[str] = None
    client_request_id: Optional[str] = Field(default=None, max_length=64)


@router.get("/health")
async def api_health():
    counts = await dashboard_counts()
    return counts


@router.get("/recruiters")
async def api_recruiters():
    return JSONResponse(await api_recruiters_payload())


@router.post("/recruiters", status_code=status.HTTP_201_CREATED)
async def api_recruiters_create(
    payload: RecruiterPayload, csrf_ok: None = Depends(require_csrf_token)
):
    try:
        recruiter_data = build_recruiter_payload(
            name=payload.name,
            tz=payload.tz_value(),
            telemost=payload.telemost or "",
            tg_chat_id=payload.chat_id_str(),
            active=payload.active if payload.active is not None else True,
        )
    except RecruiterValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"field": exc.field, "message": str(exc)},
        ) from exc

    result = await create_recruiter(recruiter_data, cities=payload.city_values())
    if not result.get("ok"):
        error_payload = result.get("error", {}) or {}
        detail = {"message": error_payload.get("message", "Не удалось создать рекрутёра.")}
        field = error_payload.get("field")
        if field:
            detail["field"] = field
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    recruiter_id = int(result.get("recruiter_id"))
    resource = await api_get_recruiter(recruiter_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Рекрутёр создан, но данные недоступны."},
        )

    response = JSONResponse(resource, status_code=status.HTTP_201_CREATED)
    response.headers["Location"] = f"/api/recruiters/{recruiter_id}"
    return response


@router.put("/recruiters/{recruiter_id}")
async def api_recruiters_update(
    recruiter_id: int,
    payload: RecruiterPayload,
    csrf_ok: None = Depends(require_csrf_token),
):
    try:
        recruiter_data = build_recruiter_payload(
            name=payload.name,
            tz=payload.tz_value(),
            telemost=payload.telemost or "",
            tg_chat_id=payload.chat_id_str(),
            active=payload.active if payload.active is not None else True,
        )
    except RecruiterValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"field": exc.field, "message": str(exc)},
        ) from exc

    result = await update_recruiter(
        recruiter_id,
        recruiter_data,
        cities=payload.city_values(),
    )
    if not result.get("ok"):
        error_payload = result.get("error", {}) or {}
        if error_payload.get("type") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": error_payload.get("message", "Рекрутёр не найден.")},
            )
        detail = {"message": error_payload.get("message", "Не удалось обновить рекрутёра.")}
        field = error_payload.get("field")
        if field:
            detail["field"] = field
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    resource = await api_get_recruiter(recruiter_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Рекрутёр не найден."},
        )
    return JSONResponse(resource)


@router.get("/recruiters/{recruiter_id}")
async def api_recruiter_detail(recruiter_id: int):
    resource = await api_get_recruiter(recruiter_id)
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Рекрутёр не найден."},
        )
    return JSONResponse(resource)


@router.get("/cities")
async def api_cities():
    return JSONResponse(await api_cities_payload())


@router.get("/cities/{city_id}/capacity")
async def api_city_capacity(city_id: int):
    """Get slot capacity information for a specific city.

    Returns:
        JSON with has_available_slots, total_free_slots, and city info.
        Returns 404 if city is not found.
    """
    capacity = await get_city_capacity(city_id)
    if capacity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Город не найден"},
        )
    return JSONResponse(capacity)


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


@router.get("/candidates/{candidate_id}")
async def api_candidate_detail_view(candidate_id: int):
    payload = await api_candidate_detail_payload(candidate_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate_not_found")
    return JSONResponse(payload)


@router.get("/candidates/{candidate_id}/chat")
async def api_candidate_chat_messages(
    candidate_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    before: Optional[str] = Query(default=None),
):
    before_dt: Optional[datetime] = None
    if before:
        try:
            before_dt = datetime.fromisoformat(before)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Некорректный формат параметра before"},
            ) from exc
    payload = await list_chat_history(candidate_id, limit, before_dt)
    return JSONResponse(payload)


@router.post("/candidates/{candidate_id}/chat")
async def api_candidate_chat_send(
    candidate_id: int,
    payload: ChatSendPayload,
    bot_service: BotService = Depends(provide_bot_service),
    csrf_ok: None = Depends(require_csrf_token),
):
    text_value = (payload.text or "").strip()
    if payload.template_key:
        template = next(
            (tpl for tpl in get_chat_templates() if tpl["key"] == payload.template_key),
            None,
        )
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Неизвестный ключ шаблона"},
            )
        if not text_value:
            text_value = template["text"]
    if not text_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Сообщение не может быть пустым"},
        )
    settings = get_settings()
    author_label = settings.admin_username or "admin"
    result = await service_send_chat_message(
        candidate_id,
        text=text_value,
        client_request_id=payload.client_request_id,
        author_label=author_label,
        bot_service=bot_service,
    )
    return JSONResponse(result)


@router.post("/candidates/{candidate_id}/chat/{message_id}/retry")
async def api_candidate_chat_retry(
    candidate_id: int,
    message_id: int,
    bot_service: BotService = Depends(provide_bot_service),
    csrf_ok: None = Depends(require_csrf_token),
):
    result = await retry_chat_message(candidate_id, message_id, bot_service=bot_service)
    return JSONResponse(result)


@router.get("/template_keys")
async def api_template_keys():
    return JSONResponse(
        [
            "invite_interview",
            "confirm_interview",
            "after_approval",
            "intro_day_reminder",
            "confirm_2h",
            "followup_missed",
            "after_meeting",
            "slot_rejected",
        ]
    )


@router.get("/notifications/feed")
async def api_notifications_feed(
    request: Request,
    after_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    if not getattr(request.app.state, "db_available", True):
        return JSONResponse(
            {"items": [], "latest_id": after_id, "degraded": True}
        )
    try:
        items = await notification_feed(after_id, limit)
    except OperationalError:
        request.app.state.db_available = False
        return JSONResponse(
            {"items": [], "latest_id": after_id, "degraded": True}
        )
    latest_id = items[-1]["id"] if items else after_id
    return JSONResponse(
        {
            "items": items,
            "latest_id": latest_id,
        }
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
async def api_bot_integration_update(
    request: Request, csrf_ok: None = Depends(require_csrf_token)
):
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
