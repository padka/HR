import logging
import secrets
from datetime import date as date_type, datetime, time, timezone, timedelta
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.responses import FileResponse

from backend.apps.admin_ui.perf.cache import keys as cache_keys
from backend.apps.admin_ui.perf.cache.readthrough import get_cached, get_or_compute
from backend.apps.admin_ui.perf.metrics import prometheus as perf_prometheus
from backend.apps.admin_ui.routers import content_api
from backend.apps.admin_ui.routers.directory import router as directory_router
from backend.apps.admin_ui.routers.profile_api import router as profile_api_router
from backend.apps.admin_ui.security import (
    Principal,
    get_principal_identifier,
    limiter,
    require_admin,
    require_csrf_token,
    require_principal,
)
from backend.apps.admin_ui.services.cities import api_city_owners_payload, invalidate_city_caches
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.calendar_events import (
    get_calendar_events,
)
from backend.apps.admin_ui.services.calendar_tasks import (
    create_calendar_task,
    delete_calendar_task,
    update_calendar_task,
)
from backend.apps.admin_ui.services.candidates import (
    api_candidate_detail_payload,
    assign_candidate_recruiter,
    delete_candidate,
    get_candidate_cohort_comparison,
    get_candidate_detail,
    list_candidates,
    upsert_candidate,
    update_candidate_status,
)
from backend.apps.admin_ui.services.chat import (
    get_chat_templates,
    list_chat_history,
    retry_chat_message,
    send_chat_message,
    wait_for_chat_history_updates,
)
from backend.apps.admin_ui.services.candidate_chat_threads import (
    get_workspace as get_candidate_chat_workspace,
    list_threads as list_candidate_chat_threads,
    mark_read as mark_candidate_chat_read,
    set_archived as set_candidate_chat_archived,
    update_workspace as update_candidate_chat_workspace,
    wait_for_thread_updates as wait_candidate_chat_updates,
)
from backend.apps.admin_ui.services.dashboard import (
    DASHBOARD_COUNTS_CACHE_STALE_SECONDS,
    DASHBOARD_COUNTS_CACHE_TTL_SECONDS,
    DASHBOARD_INCOMING_CACHE_STALE_SECONDS,
    DASHBOARD_INCOMING_CACHE_TTL_SECONDS,
    WAITING_CANDIDATES_DEFAULT_LIMIT,
    dashboard_counts,
    get_bot_funnel_stats,
    get_recruiter_leaderboard,
    get_waiting_candidates,
    normalize_waiting_candidates_limit,
)
from backend.apps.admin_ui.services.dashboard_calendar import (
    dashboard_calendar_snapshot,
)
from backend.apps.admin_ui.services.kpis import (
    get_weekly_kpis,
    list_weekly_history,
)
from backend.apps.admin_ui.services.messenger_health import (
    get_candidate_channel_health,
    get_messenger_health_snapshot,
)
from backend.apps.admin_ui.services.recruiter_plan import (
    add_recruiter_plan_entry,
    delete_recruiter_plan_entry,
    get_recruiter_plan,
)
from backend.apps.admin_ui.services.slots import (
    assign_existing_candidate_slot_silent,
    approve_slot_booking,
    delete_slot,
    execute_bot_dispatch,
    reject_slot_booking,
    schedule_manual_candidate_slot_silent,
    set_slot_outcome,
)
from backend.apps.admin_ui.services.slots.core import (
    api_slots_payload,
    bulk_create_slots,
    bulk_delete_slots,
    bulk_schedule_reminders,
)
from backend.apps.admin_ui.services.staff_chat import (
    add_thread_members as staff_add_thread_members,
    create_group_thread,
    create_or_get_direct_thread,
    decide_candidate_task as staff_decide_candidate_task,
    get_attachment as staff_get_attachment,
    list_messages as staff_list_messages,
    list_thread_members as staff_list_thread_members,
    list_threads as staff_list_threads,
    mark_read as staff_mark_read,
    remove_thread_member as staff_remove_thread_member,
    send_candidate_task as staff_send_candidate_task,
    send_message as staff_send_message,
    wait_for_message_updates as staff_wait_message_updates,
    wait_for_thread_updates as staff_wait_thread_updates,
)
from backend.apps.admin_ui.timezones import timezone_options
from backend.apps.admin_ui.utils import norm_status, parse_optional_int, recruiter_time_to_utc, status_filter
from backend.core.audit import log_audit_action
from backend.core.content_updates import KIND_REMINDERS_CHANGED, publish_content_update
from backend.core.db import async_session
from backend.core.guards import ensure_slot_scope
from backend.core.messenger.channel_state import mark_messenger_channel_healthy
from backend.core.messenger.protocol import InlineButton, MessengerPlatform
from backend.core.messenger.registry import get_registry
from backend.core.sanitizers import sanitize_plain_text
from backend.core.settings import get_settings
from backend.domain.candidates.models import (
    CandidateInviteToken,
    CandidateJourneySession,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    User,
)
from backend.domain.candidates.services import issue_candidate_invite_token
from backend.domain.candidates.portal_service import (
    CandidatePortalError,
    build_candidate_portal_journey,
    build_candidate_public_max_mini_app_url_async,
    build_candidate_public_portal_url,
    bump_candidate_portal_session_version,
    ensure_candidate_portal_session,
    get_candidate_portal_max_entry_status_async,
    get_candidate_portal_public_status,
    restart_candidate_portal_journey,
)
from backend.domain.hh_integration.summary import build_candidate_hh_summary
from backend.domain.models import ActionToken, City, Recruiter, Slot, SlotAssignment, SlotStatus, recruiter_city_association
from backend.domain.slot_service import (
    approve_slot as approve_domain_slot,
    reserve_slot as reserve_domain_slot,
)
from backend.apps.bot.runtime_config import (
    get_reminder_policy_config,
    save_reminder_policy_config,
)
from backend.core.messenger.bootstrap import bootstrap_messenger_adapters
from starlette_wtf import csrf_token

router = APIRouter(prefix="/api", tags=["api"])
router.include_router(directory_router)
router.include_router(profile_api_router)
router.include_router(content_api.router)
logger = logging.getLogger(__name__)
CANDIDATE_CREATE_LIMIT = "30/minute"

# Backward-compatible re-exports for tests that import handlers directly.
list_known_template_keys = content_api.list_known_template_keys
known_template_presets = content_api.known_template_presets


async def api_template_keys():
    return JSONResponse(list_known_template_keys())


async def api_template_presets():
    presets_list = known_template_presets()

    def _sanitize(value: str) -> str:
        return value.encode("utf-8", "ignore").decode("utf-8") if value else value

    result = {}
    for item in presets_list:
        result[item["key"]] = _sanitize(item["text"])
    return JSONResponse(result)


def _empty_weekly_kpis(timezone_label: Optional[str]) -> dict[str, object]:
    placeholder_label = "Нет данных"
    tz = timezone_label or "Europe/Moscow"
    return {
        "timezone": tz,
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

class CandidateKanbanMovePayload(BaseModel):
    target_status: str


class CandidateChatQuickActionPayload(BaseModel):
    status: str
    send_message: bool = False
    template_key: Optional[str] = None
    message_text: Optional[str] = None


class CandidateChatWorkspacePayload(BaseModel):
    shared_note: str = ""
    agreements: list[str] = []
    follow_up_due_at: Optional[datetime] = None


class ManualSlotBookingPayload(BaseModel):
    candidate_id: Optional[int] = None
    slot_id: Optional[int] = None
    fio: Optional[str] = None
    phone: Optional[str] = None
    city_id: int
    recruiter_id: int
    date: str
    time: str
    comment: Optional[str] = None


@router.get("/csrf")
async def api_csrf(request: Request):
    """Return CSRF token for SPA clients."""
    state = getattr(request, "state", None)
    if state is not None and not getattr(state, "csrf_config", None):
        settings = get_settings()
        request.scope.setdefault("session", {})
        state.csrf_config = {
            "csrf_secret": settings.session_secret,
            "csrf_field_name": "csrf_token",
        }
    return JSONResponse({"token": csrf_token(request)})


def _parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or value == "":
        return None
    value = value.lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_date_param(value: Optional[str], *, end: bool = False) -> Optional[datetime]:
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


def _parse_datetime_param(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": "Некорректный параметр даты"}) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_candidate_chat_folder(value: Optional[str]) -> str:
    normalized = str(value or "inbox").strip().lower()
    if normalized not in {"inbox", "archive", "all"}:
        raise HTTPException(status_code=400, detail={"message": "Некорректная папка чатов"})
    return normalized


def _chat_template_text(template_key: Optional[str]) -> Optional[str]:
    key = str(template_key or "").strip().lower()
    if not key:
        return None
    for item in get_chat_templates():
        if str(item.get("key") or "").strip().lower() == key:
            return str(item.get("text") or "").strip() or None
    raise HTTPException(status_code=404, detail={"message": "Шаблон сообщения не найден"})


@router.get("/health")
async def api_health():
    counts = await dashboard_counts()
    return counts


@router.get("/dashboard/summary")
async def api_dashboard_summary(
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    if not getattr(request.app.state, "db_available", True):
        cache_key = cache_keys.dashboard_counts(principal=principal).value
        cached_payload = await get_cached(
            cache_key,
            expected_type=dict,
            ttl_seconds=DASHBOARD_COUNTS_CACHE_TTL_SECONDS,
            stale_seconds=DASHBOARD_COUNTS_CACHE_STALE_SECONDS,
        )
        if cached_payload is not None and isinstance(cached_payload[0], dict):
            return JSONResponse(cached_payload[0])
        return JSONResponse({"status": "degraded", "reason": "database_unavailable"}, status_code=503)

    return JSONResponse(await dashboard_counts(principal=principal))


@router.get("/dashboard/incoming")
async def api_dashboard_incoming(
    request: Request,
    limit: int = Query(default=WAITING_CANDIDATES_DEFAULT_LIMIT, ge=1, le=2000),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    """Candidates who passed test1 and are waiting for a free interview slot."""
    normalized_limit = normalize_waiting_candidates_limit(limit)
    if not getattr(request.app.state, "db_available", True):
        cache_key = cache_keys.dashboard_incoming(principal=principal, limit=normalized_limit).value
        cached_payload = await get_cached(
            cache_key,
            expected_type=list,
            ttl_seconds=DASHBOARD_INCOMING_CACHE_TTL_SECONDS,
            stale_seconds=DASHBOARD_INCOMING_CACHE_STALE_SECONDS,
        )
        if cached_payload is not None and isinstance(cached_payload[0], list):
            return JSONResponse({"items": cached_payload[0]})
        return JSONResponse({"status": "degraded", "reason": "database_unavailable"}, status_code=503)

    payload = await get_waiting_candidates(limit=normalized_limit, principal=principal)
    return JSONResponse({"items": payload})


@router.get("/dashboard/recruiter-performance")
async def api_dashboard_recruiter_performance(
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_admin),
) -> JSONResponse:
    date_from = _parse_date_param(from_)
    date_to = _parse_date_param(to, end=True)
    payload = await get_recruiter_leaderboard(
        date_from=date_from,
        date_to=date_to,
        city=city,
    )
    return JSONResponse(payload)


class StaffMemberPayload(BaseModel):
    type: str
    id: int


class StaffThreadCreatePayload(BaseModel):
    type: str
    title: Optional[str] = None
    members: Optional[list[StaffMemberPayload]] = None


class StaffThreadMembersPayload(BaseModel):
    members: list[StaffMemberPayload]


class StaffCandidateTaskPayload(BaseModel):
    candidate_id: int
    note: Optional[str] = None


class StaffCandidateDecisionPayload(BaseModel):
    comment: Optional[str] = None


class CalendarTaskCreatePayload(BaseModel):
    title: str
    start: datetime
    end: datetime
    description: Optional[str] = None
    recruiter_id: Optional[int] = None
    is_done: bool = False


class CalendarTaskUpdatePayload(BaseModel):
    title: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    description: Optional[str] = None
    recruiter_id: Optional[int] = None
    is_done: Optional[bool] = None


@router.get("/staff/threads")
async def api_staff_threads(principal: Principal = Depends(require_principal)) -> JSONResponse:
    return JSONResponse(await staff_list_threads(principal))


@router.get("/candidate-chat/threads")
async def api_candidate_chat_threads(
    search: Optional[str] = Query(default=None),
    unread_only: bool = Query(default=False),
    folder: str = Query(default="inbox"),
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    payload = await list_candidate_chat_threads(
        principal,
        search=search,
        unread_only=unread_only,
        folder=_normalize_candidate_chat_folder(folder),  # type: ignore[arg-type]
        limit=limit,
    )
    return JSONResponse(jsonable_encoder(payload))


@router.get("/candidate-chat/threads/updates")
async def api_candidate_chat_threads_updates(
    since: Optional[str] = Query(default=None),
    timeout: int = Query(default=25, ge=5, le=60),
    search: Optional[str] = Query(default=None),
    unread_only: bool = Query(default=False),
    folder: str = Query(default="inbox"),
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    since_dt = _parse_datetime_param(since)
    payload = await wait_candidate_chat_updates(
        principal,
        since=since_dt,
        timeout=timeout,
        search=search,
        unread_only=unread_only,
        folder=_normalize_candidate_chat_folder(folder),  # type: ignore[arg-type]
        limit=limit,
    )
    return JSONResponse(jsonable_encoder(payload))


@router.get("/candidate-chat/templates")
async def api_candidate_chat_templates(
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    del principal
    return JSONResponse({"items": get_chat_templates()})


@router.post("/candidate-chat/threads/{candidate_id}/read")
async def api_candidate_chat_mark_read(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    await mark_candidate_chat_read(candidate_id, principal)
    return JSONResponse({"ok": True})


@router.post("/candidate-chat/threads/{candidate_id}/archive")
async def api_candidate_chat_archive(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    await set_candidate_chat_archived(candidate_id, principal, archived=True)
    return JSONResponse({"ok": True, "archived": True})


@router.post("/candidate-chat/threads/{candidate_id}/unarchive")
async def api_candidate_chat_unarchive(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    await set_candidate_chat_archived(candidate_id, principal, archived=False)
    return JSONResponse({"ok": True, "archived": False})


@router.get("/candidate-chat/threads/{candidate_id}/workspace")
async def api_candidate_chat_workspace(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    payload = await get_candidate_chat_workspace(candidate_id, principal)
    return JSONResponse(jsonable_encoder(payload))


@router.put("/candidate-chat/threads/{candidate_id}/workspace")
async def api_candidate_chat_workspace_update(
    candidate_id: int,
    payload: CandidateChatWorkspacePayload,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    shared_note = sanitize_plain_text(payload.shared_note or "", max_length=4000)
    agreements = [
        sanitize_plain_text(item or "", max_length=240)
        for item in list(payload.agreements or [])
        if sanitize_plain_text(item or "", max_length=240).strip()
    ]
    updated_by = getattr(request.state, "admin_username", None)
    if not updated_by:
        updated_by = "Администратор" if principal.type == "admin" else "Рекрутер"
    workspace = await update_candidate_chat_workspace(
        candidate_id,
        principal,
        shared_note=shared_note,
        agreements=agreements,
        follow_up_due_at=payload.follow_up_due_at,
        updated_by=updated_by,
    )
    return JSONResponse(jsonable_encoder(workspace))


@router.post("/staff/threads")
async def api_staff_threads_create(
    payload: StaffThreadCreatePayload,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    thread_type = (payload.type or "").strip().lower()
    members = payload.members or []
    if thread_type not in {"direct", "group"}:
        raise HTTPException(status_code=400, detail={"message": "Некорректный тип чата"})

    if thread_type == "direct":
        if len(members) != 1:
            raise HTTPException(status_code=400, detail={"message": "Для личного чата нужен один участник"})
        other = members[0]
        thread = await create_or_get_direct_thread(principal, other.type, other.id)
        return JSONResponse(thread)

    if not payload.title:
        raise HTTPException(status_code=400, detail={"message": "Укажите название группового чата"})
    if len(members) < 1:
        raise HTTPException(status_code=400, detail={"message": "Добавьте участников"})
    thread = await create_group_thread(principal, payload.title, [m.model_dump() for m in members])
    return JSONResponse(thread)


@router.get("/staff/threads/updates")
async def api_staff_threads_updates(
    since: Optional[str] = Query(default=None),
    timeout: int = Query(default=25, ge=5, le=60),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    since_dt = _parse_datetime_param(since)
    payload = await staff_wait_thread_updates(principal, since=since_dt, timeout=timeout)
    return JSONResponse(jsonable_encoder(payload))


@router.get("/staff/threads/{thread_id}/messages")
async def api_staff_messages(
    thread_id: int,
    limit: int = Query(default=50, ge=10, le=200),
    before: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    before_dt = _parse_datetime_param(before)
    return JSONResponse(await staff_list_messages(thread_id, principal, limit=limit, before=before_dt))


@router.post("/staff/threads/{thread_id}/messages")
async def api_staff_send_message(
    thread_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    text: Optional[str] = None
    files: Optional[List[UploadFile]] = None

    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception:
            data = {}
        if isinstance(data, dict):
            raw_text = data.get("text")
            if raw_text is not None:
                text = str(raw_text)
    else:
        form = await request.form()
        raw_text = form.get("text")
        if raw_text is not None:
            text = str(raw_text)
        uploads = form.getlist("files")
        if uploads:
            # Starlette returns starlette.datastructures.UploadFile; FastAPI's UploadFile
            # is a subclass, so we should accept the Starlette base type here.
            files = [item for item in uploads if isinstance(item, StarletteUploadFile)]

    payload = await staff_send_message(thread_id, principal, text=text, files=files)
    return JSONResponse(payload)


@router.get("/staff/threads/{thread_id}/updates")
async def api_staff_messages_updates(
    thread_id: int,
    since: Optional[str] = Query(default=None),
    timeout: int = Query(default=25, ge=5, le=60),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    since_dt = _parse_datetime_param(since)
    payload = await staff_wait_message_updates(thread_id, principal, since=since_dt, timeout=timeout)
    return JSONResponse(payload)


@router.post("/staff/threads/{thread_id}/read")
async def api_staff_mark_read(
    thread_id: int,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    await staff_mark_read(thread_id, principal)
    return JSONResponse({"ok": True})


@router.get("/staff/attachments/{attachment_id}")
async def api_staff_attachment(
    attachment_id: int,
    principal: Principal = Depends(require_principal),
) -> FileResponse:
    attachment = await staff_get_attachment(attachment_id, principal)
    settings = get_settings()
    base_dir = Path(settings.data_dir).resolve()
    file_path = (base_dir / attachment.storage_path).resolve()
    if not str(file_path).startswith(str(base_dir)):
        raise HTTPException(status_code=403, detail={"message": "Нет доступа"})
    if not file_path.exists():
        raise HTTPException(status_code=404, detail={"message": "Файл не найден"})
    return FileResponse(file_path, filename=attachment.filename, media_type=attachment.mime_type or "application/octet-stream")


@router.get("/staff/threads/{thread_id}/members")
async def api_staff_thread_members(
    thread_id: int,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    members = await staff_list_thread_members(thread_id, principal)
    return JSONResponse({"members": members})


@router.post("/staff/threads/{thread_id}/members")
async def api_staff_thread_members_add(
    thread_id: int,
    payload: StaffThreadMembersPayload,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    members = await staff_add_thread_members(
        thread_id,
        principal,
        [m.model_dump() for m in payload.members],
    )
    return JSONResponse({"members": members})


@router.delete("/staff/threads/{thread_id}/members/{member_type}/{member_id}")
async def api_staff_thread_member_remove(
    thread_id: int,
    member_type: str,
    member_id: int,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    members = await staff_remove_thread_member(thread_id, principal, member_type, member_id)
    return JSONResponse({"members": members})


@router.post("/staff/threads/{thread_id}/candidate")
async def api_staff_candidate_task(
    thread_id: int,
    payload: StaffCandidateTaskPayload,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    message = await staff_send_candidate_task(thread_id, principal, payload.candidate_id, payload.note)
    return JSONResponse(message)


@router.post("/staff/messages/{message_id}/candidate/accept")
async def api_staff_candidate_task_accept(
    message_id: int,
    payload: StaffCandidateDecisionPayload,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    message = await staff_decide_candidate_task(message_id, principal, "accepted", payload.comment)
    return JSONResponse(message)


@router.post("/staff/messages/{message_id}/candidate/decline")
async def api_staff_candidate_task_decline(
    message_id: int,
    payload: StaffCandidateDecisionPayload,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    message = await staff_decide_candidate_task(message_id, principal, "declined", payload.comment)
    return JSONResponse(message)


@router.get("/dashboard/calendar")
async def api_dashboard_calendar(
    date: Optional[str] = Query(default=None),
    days: int = Query(default=14, ge=1, le=60),
    recruiter: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_principal),
):
    target_date: Optional[date_type] = None
    if date:
        try:
            target_date = date_type.fromisoformat(date)
        except ValueError:
            return JSONResponse(
                {"ok": False, "error": "invalid_date"}, status_code=400
            )
    recruiter_id = principal.id if principal.type == "recruiter" else parse_optional_int(recruiter)
    snapshot = await dashboard_calendar_snapshot(target_date, days=days, recruiter_id=recruiter_id)
    return JSONResponse(snapshot)


@router.get("/calendar/events")
async def api_calendar_events(
    request: Request,
    start: str = Query(..., description="Start date ISO format (YYYY-MM-DD)"),
    end: str = Query(..., description="End date ISO format (YYYY-MM-DD)"),
    recruiter_id: Optional[int] = Query(default=None),
    city_id: Optional[int] = Query(default=None),
    status: Optional[List[str]] = Query(default=None),
    include_tasks: bool = Query(default=False),
    principal: Principal = Depends(require_principal),
):
    """
    Get calendar events in FullCalendar-compatible format.

    Returns all slot statuses (FREE, PENDING, BOOKED, CONFIRMED) with colors.
    """
    try:
        start_date = date_type.fromisoformat(start)
    except ValueError:
        return JSONResponse({"ok": False, "error": "invalid_start_date"}, status_code=400)

    try:
        end_date = date_type.fromisoformat(end)
    except ValueError:
        return JSONResponse({"ok": False, "error": "invalid_end_date"}, status_code=400)

    # Validate date range (max 60 days)
    if (end_date - start_date).days > 60:
        return JSONResponse({"ok": False, "error": "date_range_too_large"}, status_code=400)

    # For recruiters, filter to their own slots only
    effective_recruiter_id = recruiter_id
    if principal.type == "recruiter":
        effective_recruiter_id = principal.id

    if not getattr(request.app.state, "db_available", True):
        from backend.apps.admin_ui.utils import DEFAULT_TZ as _DEFAULT_TZ
        cache_key = cache_keys.calendar_events(
            start_date=start_date,
            end_date=end_date,
            recruiter_id=effective_recruiter_id,
            city_id=city_id,
            statuses=status,
            tz_name=_DEFAULT_TZ,
            include_canceled=False,
            include_tasks=include_tasks,
        ).value
        cached_payload = await get_cached(
            cache_key,
            expected_type=dict,
            ttl_seconds=2.0,
            stale_seconds=10.0,
        )
        if cached_payload is not None and isinstance(cached_payload[0], dict) and "events" in cached_payload[0]:
            return JSONResponse({"ok": True, **cached_payload[0]})
        return JSONResponse({"ok": False, "error": "database_unavailable"}, status_code=503)

    result = await get_calendar_events(
        start_date=start_date,
        end_date=end_date,
        recruiter_id=effective_recruiter_id,
        city_id=city_id,
        statuses=status,
        include_tasks=include_tasks,
    )
    return JSONResponse({"ok": True, **result})


@router.post("/calendar/tasks")
async def api_calendar_task_create(
    payload: CalendarTaskCreatePayload,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    try:
        task = await create_calendar_task(
            principal=principal,
            title=payload.title,
            start_utc=payload.start,
            end_utc=payload.end,
            description=payload.description,
            recruiter_id=payload.recruiter_id,
            is_done=payload.is_done,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail={"message": "Недостаточно прав"})
    except LookupError:
        raise HTTPException(status_code=404, detail={"message": "Рекрутер не найден"})
    except ValueError as exc:
        message = str(exc)
        if message == "title_required":
            message = "Укажите название задачи"
        elif message == "invalid_time_range":
            message = "Время окончания должно быть позже времени начала"
        elif message == "recruiter_required":
            message = "Нужно выбрать рекрутера"
        raise HTTPException(status_code=400, detail={"message": message})
    return JSONResponse({"ok": True, "task": task}, status_code=201)


@router.patch("/calendar/tasks/{task_id}")
async def api_calendar_task_update(
    task_id: int,
    payload: CalendarTaskUpdatePayload,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    try:
        task = await update_calendar_task(
            task_id,
            principal=principal,
            title=payload.title,
            start_utc=payload.start,
            end_utc=payload.end,
            description=payload.description,
            recruiter_id=payload.recruiter_id,
            is_done=payload.is_done,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail={"message": "Недостаточно прав"})
    except LookupError as exc:
        message = str(exc)
        if message == "task_not_found":
            raise HTTPException(status_code=404, detail={"message": "Задача не найдена"})
        raise HTTPException(status_code=404, detail={"message": "Рекрутер не найден"})
    except ValueError as exc:
        message = str(exc)
        if message == "title_required":
            message = "Укажите название задачи"
        elif message == "invalid_time_range":
            message = "Время окончания должно быть позже времени начала"
        raise HTTPException(status_code=400, detail={"message": message})
    return JSONResponse({"ok": True, "task": task})


@router.delete("/calendar/tasks/{task_id}")
async def api_calendar_task_delete(
    task_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    try:
        deleted = await delete_calendar_task(task_id, principal=principal)
    except PermissionError:
        raise HTTPException(status_code=403, detail={"message": "Недостаточно прав"})
    if not deleted:
        raise HTTPException(status_code=404, detail={"message": "Задача не найдена"})
    return JSONResponse({"ok": True})


@router.get("/dashboard/funnel")
async def api_dashboard_funnel(
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    recruiter: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_principal),
):
    date_from = _parse_date_param(from_)
    date_to = _parse_date_param(to, end=True)
    recruiter_id = parse_optional_int(recruiter)
    if principal.type == "recruiter":
        recruiter_id = principal.id
    payload = await get_bot_funnel_stats(
        date_from=date_from,
        date_to=date_to,
        city=city,
        recruiter_id=recruiter_id,
        source=source,
    )
    return JSONResponse(payload)




@router.get("/slots")
async def api_slots(
    recruiter_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    sort_dir: str = Query(default="desc"),
    principal: Principal = Depends(require_principal),
):
    recruiter = parse_optional_int(recruiter_id)
    if principal.type == "recruiter":
        recruiter = principal.id
    status_norm = status_filter(status)
    payload = await api_slots_payload(
        recruiter,
        status_norm,
        limit,
    )
    return JSONResponse(payload)


class SlotsBulkCreatePayload(BaseModel):
    recruiter_id: int
    city_id: int
    start_date: str
    end_date: str
    start_time: str
    end_time: str
    break_start: str
    break_end: str
    step_min: int
    include_weekends: bool = False
    use_break: bool = True


@router.post("/slots/bulk_create")
async def api_slots_bulk_create(
    payload: SlotsBulkCreatePayload,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    recruiter_id = int(payload.recruiter_id)
    if principal.type == "recruiter":
        recruiter_id = int(principal.id)

    created, error = await bulk_create_slots(
        recruiter_id=recruiter_id,
        city_id=int(payload.city_id),
        start_date=str(payload.start_date),
        end_date=str(payload.end_date),
        start_time=str(payload.start_time),
        end_time=str(payload.end_time),
        break_start=str(payload.break_start),
        break_end=str(payload.break_end),
        step_min=int(payload.step_min),
        include_weekends=bool(payload.include_weekends),
        use_break=bool(payload.use_break),
    )
    if error:
        return JSONResponse({"ok": False, "error": error, "created": 0}, status_code=400)
    return JSONResponse({"ok": True, "created": int(created)})


class SlotOutcomePayload(BaseModel):
    outcome: str


class SlotBookPayload(BaseModel):
    candidate_tg_id: int
    candidate_fio: Optional[str] = None


class SlotProposePayload(BaseModel):
    candidate_id: str


class SlotReschedulePayload(BaseModel):
    date: str
    time: str
    reason: Optional[str] = None


class SlotsBulkPayload(BaseModel):
    action: str
    slot_ids: list[int]
    force: Optional[bool] = None


class PlanEntryPayload(BaseModel):
    last_name: str


def _format_time_for_message(dt: datetime, tz_label: str) -> str:
    try:
        zone = ZoneInfo(tz_label)
    except Exception:
        zone = ZoneInfo("Europe/Moscow")
    return dt.astimezone(zone).strftime("%d.%m %H:%M")


async def _assign_existing_slot_for_candidate(
    *,
    slot_id: int,
    candidate: User,
    principal: Principal,
    route_label: str,
    created_by: str,
) -> JSONResponse:
    from backend.domain.candidates.status_service import set_status_slot_pending
    from backend.domain.slot_assignment_service import create_slot_assignment

    async with async_session() as session:
        selected_slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )
        if selected_slot is None:
            perf_prometheus.slot_propose_404(reason="slot_not_found")
            logger.warning(
                "slot_assignment_route.failed",
                extra={
                    "route": route_label,
                    "slot_id": slot_id,
                    "candidate_id": candidate.id,
                    "error_code": "slot_not_found",
                    "status_code": 404,
                },
            )
            return JSONResponse({"ok": False, "error": "slot_not_found"}, status_code=404)
        ensure_slot_scope(selected_slot, principal)
        if (getattr(selected_slot, "purpose", None) or "interview") != "interview":
            return JSONResponse({"ok": False, "error": "slot_not_interview"}, status_code=409)
        if norm_status(selected_slot.status) != "FREE":
            return JSONResponse({"ok": False, "error": "slot_not_free"}, status_code=409)
        slot_tz = (
            getattr(selected_slot, "tz_name", None)
            or (getattr(selected_slot.city, "tz", None) if selected_slot.city else None)
            or (getattr(selected_slot.recruiter, "tz", None) if selected_slot.recruiter else None)
            or "Europe/Moscow"
        )

    candidate_tg_id = candidate.telegram_user_id or candidate.telegram_id
    if candidate_tg_id is None:
        return JSONResponse(
            {
                "ok": False,
                "error": "candidate_telegram_missing",
                "message": "У кандидата не привязан Telegram.",
            },
            status_code=400,
        )
    if not candidate.candidate_id:
        return JSONResponse({"ok": False, "error": "missing_candidate_id"}, status_code=409)

    assignment_result = await create_slot_assignment(
        slot_id=slot_id,
        candidate_id=candidate.candidate_id,
        candidate_tg_id=candidate_tg_id,
        candidate_tz=slot_tz,
        created_by=created_by,
        allow_replace_active_assignment=True,
    )
    if not assignment_result.ok:
        status_code = assignment_result.status_code or 409
        logger.warning(
            "slot_assignment_route.failed",
            extra={
                "route": route_label,
                "slot_id": slot_id,
                "candidate_id": candidate.id,
                "error_code": assignment_result.status,
                "status_code": status_code,
            },
        )
        return JSONResponse(
            {
                "ok": False,
                "error": assignment_result.status,
                "message": assignment_result.message or "Не удалось назначить слот.",
            },
            status_code=status_code,
        )

    try:
        await set_status_slot_pending(candidate_tg_id)
    except Exception:
        logger.exception(
            "Failed to set SLOT_PENDING after assigning existing slot",
            extra={"candidate_id": candidate.id, "slot_id": slot_id},
        )

    try:
        async with async_session() as session:
            db_user = await session.get(User, candidate.id)
            if db_user and db_user.responsible_recruiter_id != selected_slot.recruiter_id:
                db_user.responsible_recruiter_id = selected_slot.recruiter_id
                await session.commit()
    except Exception:
        logger.exception(
            "Failed to assign responsible recruiter after existing slot assignment",
            extra={"candidate_id": candidate.id},
        )

    logger.info(
        "slot_assignment_route.succeeded",
        extra={
            "route": route_label,
            "slot_id": slot_id,
            "candidate_id": candidate.id,
            "error_code": None,
            "status_code": 201,
        },
    )
    return JSONResponse(
        {
            "ok": True,
            "status": "pending_offer",
            "message": "Предложение отправлено кандидату",
            "slot_id": slot_id,
            "slot_assignment_id": int(assignment_result.payload.get("slot_assignment_id") or 0),
        },
        status_code=201,
    )


@router.post("/slots/{slot_id}/approve_booking")
async def api_slot_approve(
    slot_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    ok, message, notified = await approve_slot_booking(slot_id, principal=principal)
    status_code = 200 if ok else (404 if message and "не найден" in message.lower() else 400)
    return JSONResponse({"ok": ok, "message": message, "bot_notified": notified}, status_code=status_code)


@router.post("/slots/{slot_id}/reject_booking")
async def api_slot_reject(
    slot_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    ok, message, notified = await reject_slot_booking(slot_id, principal=principal)
    status_code = 200 if ok else (404 if message and "не найден" in message.lower() else 400)
    return JSONResponse({"ok": ok, "message": message, "bot_notified": notified}, status_code=status_code)


@router.post("/slots/{slot_id}/reschedule")
async def api_slot_reschedule(
    slot_id: int,
    payload: SlotReschedulePayload,
    request: Request,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter))
            .where(Slot.id == slot_id)
        )
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
        ensure_slot_scope(slot, principal)
        if not getattr(slot, "candidate_tg_id", None) and not getattr(slot, "candidate_id", None):
            return JSONResponse({"ok": False, "error": "no_candidate", "message": "Слот не привязан к кандидату"}, status_code=400)

        slot_tz = getattr(slot.recruiter, "tz", None) if slot.recruiter else None
        slot_tz = slot_tz or getattr(slot, "tz_name", None) or "Europe/Moscow"
        dt_utc = recruiter_time_to_utc(payload.date, payload.time, slot_tz)
        if not dt_utc:
            return JSONResponse({"ok": False, "error": "invalid_datetime", "message": "Некорректная дата/время"}, status_code=400)

        candidate = None
        if getattr(slot, "candidate_id", None):
            candidate = await session.scalar(select(User).where(User.candidate_id == slot.candidate_id))
        if candidate is None and getattr(slot, "candidate_tg_id", None):
            candidate = await session.scalar(select(User).where(User.telegram_id == slot.candidate_tg_id))
        if candidate is None:
            await session.commit()
            return JSONResponse({"ok": False, "error": "candidate_not_found", "message": "Кандидат не найден"}, status_code=404)

        candidate_tg_id = candidate.telegram_user_id or candidate.telegram_id
        if candidate_tg_id is None:
            await session.commit()
            return JSONResponse({"ok": False, "error": "no_candidate_tg", "message": "У кандидата нет Telegram ID"}, status_code=400)

        candidate_id = candidate.candidate_id
        if not candidate_id:
            await session.commit()
            return JSONResponse({"ok": False, "error": "no_candidate_id", "message": "У кандидата нет candidate_id"}, status_code=400)

        now = datetime.now(timezone.utc)
        active_statuses = ("offered", "confirmed", "reschedule_requested", "reschedule_confirmed")
        target_slot = slot
        purpose_key = (getattr(slot, "purpose", None) or "interview").strip().lower()
        existing_target_slot = await session.scalar(
            select(Slot)
            .where(
                Slot.recruiter_id == slot.recruiter_id,
                Slot.id != slot.id,
                Slot.start_utc == dt_utc,
                func.lower(func.coalesce(Slot.purpose, "interview")) == purpose_key,
                Slot.status != SlotStatus.CANCELED,
            )
        )
        if existing_target_slot is not None:
            existing_target_assignment = await session.scalar(
                select(SlotAssignment)
                .where(
                    SlotAssignment.slot_id == existing_target_slot.id,
                    SlotAssignment.status.in_(active_statuses),
                )
            )
            candidate_conflict = (
                existing_target_slot.candidate_id not in (None, candidate_id)
                or existing_target_slot.candidate_tg_id not in (None, candidate_tg_id)
            )
            assignment_conflict = existing_target_assignment is not None and (
                existing_target_assignment.candidate_id not in (None, candidate_id)
                or existing_target_assignment.candidate_tg_id not in (None, candidate_tg_id)
            )
            if candidate_conflict or assignment_conflict:
                return JSONResponse(
                    {
                        "ok": False,
                        "error": "target_slot_conflict",
                        "message": "На выбранное время уже есть другой слот рекрутёра.",
                    },
                    status_code=409,
                )
            target_slot = existing_target_slot
            target_slot.status = SlotStatus.PENDING
            target_slot.candidate_id = candidate_id
            target_slot.candidate_tg_id = candidate_tg_id
            target_slot.candidate_fio = candidate.fio
            target_slot.candidate_tz = getattr(slot, "candidate_tz", None) or slot_tz
            target_slot.candidate_city_id = getattr(slot, "candidate_city_id", None)

            slot.status = SlotStatus.FREE
            slot.candidate_id = None
            slot.candidate_tg_id = None
            slot.candidate_fio = None
            slot.candidate_tz = None
            slot.candidate_city_id = None
        else:
            slot.start_utc = dt_utc
            slot.status = SlotStatus.PENDING

        assignment = await session.scalar(
            select(SlotAssignment)
            .where(SlotAssignment.candidate_id == candidate_id)
            .where(SlotAssignment.status.in_(active_statuses))
        )
        if assignment is None:
            assignment = SlotAssignment(
                slot_id=target_slot.id,
                recruiter_id=target_slot.recruiter_id,
                candidate_id=candidate_id,
                candidate_tg_id=candidate_tg_id,
                candidate_tz=getattr(target_slot, "candidate_tz", None) or slot_tz,
                status="offered",
                offered_at=now,
            )
            session.add(assignment)
            await session.flush()
        else:
            assignment.slot_id = target_slot.id
            assignment.recruiter_id = target_slot.recruiter_id
            assignment.status = "offered"
            assignment.offered_at = now
            assignment.confirmed_at = None
            assignment.reschedule_requested_at = None
            assignment.status_before_reschedule = None

        expires_at = now + timedelta(days=2)
        confirm_token = ActionToken(
            token=secrets.token_urlsafe(16),
            action="confirm_assignment",
            entity_id=str(assignment.id),
            expires_at=expires_at,
        )
        reschedule_token = ActionToken(
            token=secrets.token_urlsafe(16),
            action="reschedule_assignment",
            entity_id=str(assignment.id),
            expires_at=expires_at,
        )
        decline_token = ActionToken(
            token=secrets.token_urlsafe(16),
            action="decline_assignment",
            entity_id=str(assignment.id),
            expires_at=expires_at,
        )
        session.add_all([confirm_token, reschedule_token, decline_token])
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return JSONResponse(
                {
                    "ok": False,
                    "error": "slot_overlap",
                    "message": "На выбранное время уже есть пересекающийся слот рекрутёра.",
                },
                status_code=409,
            )
        assignment_id = assignment.id
        confirm_token_value = confirm_token.token
        reschedule_token_value = reschedule_token.token
        decline_token_value = decline_token.token

    reason = sanitize_plain_text(payload.reason or "", max_length=400)
    candidate_tz = getattr(target_slot, "candidate_tz", None) or slot_tz
    recruiter_time = _format_time_for_message(dt_utc, slot_tz)
    candidate_time = _format_time_for_message(dt_utc, candidate_tz)
    lines = [
        "Перенос встречи.",
        f"Новое время: {candidate_time} ({candidate_tz})",
        "Подтвердите участие, выберите другое время или откажитесь через кнопки ниже.",
    ]
    if candidate_tz != slot_tz:
        lines.append(f"Время рекрутёра: {recruiter_time} ({slot_tz})")
    if reason:
        lines.append(f"Причина: {reason}")
    message_text = "\n".join(lines)

    notified = False
    if candidate is not None:
        reply_markup = None
        try:
            from backend.apps.bot.keyboards import kb_slot_assignment_offer

            reply_markup = kb_slot_assignment_offer(
                assignment_id,
                confirm_token=confirm_token_value,
                reschedule_token=reschedule_token_value,
                decline_token=decline_token_value,
            )
        except Exception:
            reply_markup = None
        try:
            await send_chat_message(
                candidate.id,
                text=message_text,
                client_request_id=f"slot_reschedule_{slot_id}_{dt_utc.isoformat()}",
                author_label=getattr(request.state, "admin_username", None) or principal.type,
                bot_service=bot_service,
                reply_markup=reply_markup,
            )
            notified = True
        except Exception:
            notified = False

    return JSONResponse({"ok": True, "message": "Слот перенесён", "bot_notified": notified})


@router.post("/slots/{slot_id}/propose")
async def api_slot_propose(
    slot_id: int,
    payload: SlotProposePayload,
    request: Request,
    _: None = Depends(require_csrf_token),
    principal: Principal = Depends(require_principal),
):
    async with async_session() as session:
        candidate = await session.scalar(
            select(User).where(User.candidate_id == payload.candidate_id)
        )
        if candidate is None:
            perf_prometheus.slot_propose_404(reason="candidate_not_found")
            logger.warning(
                "slot_assignment_route.failed",
                extra={
                    "route": "/api/slots/{slot_id}/propose",
                    "slot_id": slot_id,
                    "candidate_id": payload.candidate_id,
                    "error_code": "candidate_not_found",
                    "status_code": 404,
                },
            )
            return JSONResponse(
                {
                    "ok": False,
                    "error": "candidate_not_found",
                    "message": "Кандидат не найден",
                },
                status_code=404,
            )

    created_by = (
        request.session.get("username")
        if getattr(request, "session", None) is not None
        else None
    ) or f"{principal.type}:{principal.id}"
    return await _assign_existing_slot_for_candidate(
        slot_id=slot_id,
        candidate=candidate,
        principal=principal,
        route_label="/api/slots/{slot_id}/propose",
        created_by=created_by,
    )


@router.post("/slots/{slot_id}/outcome")
async def api_slot_outcome(
    slot_id: int,
    payload: SlotOutcomePayload,
    request: Request,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    ok, message, stored, dispatch = await set_slot_outcome(
        slot_id,
        payload.outcome,
        bot_service=bot_service,
        principal=principal,
    )
    status_code = 200
    bot_status = dispatch.status if dispatch is not None else "skipped:not_applicable"
    if ok and dispatch and dispatch.plan is not None:
        background_tasks.add_task(execute_bot_dispatch, dispatch.plan, stored or "", bot_service)
    if not ok:
        status_code = 404 if message and "не найден" in message.lower() else 400
    response = JSONResponse({"ok": ok, "message": message, "outcome": stored}, status_code=status_code)
    response.headers["X-Bot"] = bot_status
    return response


@router.post("/slots/{slot_id}/book")
async def api_slot_book(
    slot_id: int,
    payload: SlotBookPayload,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    slot_recruiter_id: int | None = None
    slot_city_id: int | None = None
    slot_tz_name = "Europe/Moscow"
    candidate: User | None = None

    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Slot not found")
        ensure_slot_scope(slot, principal)
        if norm_status(slot.status) != "FREE":
            return JSONResponse({"ok": False, "error": "slot_not_free", "message": "Слот уже занят"}, status_code=400)
        slot_recruiter_id = int(slot.recruiter_id) if slot.recruiter_id is not None else None
        slot_city_id = int(slot.city_id) if slot.city_id is not None else None
        slot_tz_name = slot.tz_name or slot_tz_name
        candidate = await session.scalar(select(User).where(User.telegram_id == payload.candidate_tg_id))
        if candidate is None:
            return JSONResponse({"ok": False, "error": "candidate_not_found", "message": "Кандидат не найден"}, status_code=404)

    try:
        reservation = await reserve_domain_slot(
            slot_id,
            candidate_tg_id=payload.candidate_tg_id,
            candidate_fio=(payload.candidate_fio or candidate.fio or "").strip(),
            candidate_tz=slot_tz_name,
            candidate_id=candidate.candidate_id,
            candidate_city_id=slot_city_id,
            candidate_username=candidate.username,
            expected_recruiter_id=slot_recruiter_id,
            expected_city_id=slot_city_id,
        )
    except IntegrityError:
        existing_slot_id: int | None = None
        if payload.candidate_tg_id is not None:
            try:
                async with async_session() as session:
                    existing_slot_id = await session.scalar(
                        select(Slot.id)
                        .where(
                            Slot.candidate_tg_id == payload.candidate_tg_id,
                            func.lower(Slot.status).in_(
                                [
                                    SlotStatus.PENDING,
                                    SlotStatus.BOOKED,
                                    SlotStatus.CONFIRMED,
                                    SlotStatus.CONFIRMED_BY_CANDIDATE,
                                ]
                            ),
                        )
                        .order_by(Slot.start_utc.asc())
                    )
            except Exception:
                logger.exception(
                    "slot_book.conflict_lookup_failed",
                    extra={
                        "slot_id": slot_id,
                        "candidate_tg_id": payload.candidate_tg_id,
                        "recruiter_id": slot_recruiter_id,
                    },
                )
        logger.warning(
            "slot_book.conflict_integrity",
            extra={
                "slot_id": slot_id,
                "candidate_tg_id": payload.candidate_tg_id,
                "recruiter_id": slot_recruiter_id,
            },
        )
        return JSONResponse(
            {
                "ok": False,
                "error": "candidate_already_booked",
                "message": "У кандидата уже есть активная встреча",
                "existing_slot_id": existing_slot_id,
            },
            status_code=409,
        )
    except Exception:
        logger.exception(
            "slot_book.unexpected_reservation_error",
            extra={"slot_id": slot_id, "candidate_tg_id": payload.candidate_tg_id},
        )
        return JSONResponse(
            {"ok": False, "error": "slot_booking_failed", "message": "Не удалось забронировать слот"},
            status_code=400,
        )

    if reservation.status in {"duplicate_candidate", "already_reserved"}:
        existing_slot_id = reservation.slot.id if reservation.slot is not None else None
        return JSONResponse(
            {
                "ok": False,
                "error": "candidate_already_booked",
                "message": "У кандидата уже есть активная встреча",
                "existing_slot_id": existing_slot_id,
            },
            status_code=409,
        )

    if reservation.status != "reserved":
        return JSONResponse({"ok": False, "error": "slot_not_free", "message": "Слот уже занят"}, status_code=400)

    approved_slot = await approve_domain_slot(slot_id)
    if approved_slot is None:
        return JSONResponse({"ok": False, "error": "slot_not_free", "message": "Слот уже занят"}, status_code=400)

    return JSONResponse({
        "ok": True,
        "message": "Слот согласован с кандидатом",
        "slot_id": slot_id,
        "candidate_tg_id": payload.candidate_tg_id,
    })


@router.post("/slots/manual-bookings")
async def api_slots_manual_booking(
    payload: ManualSlotBookingPayload,
    request: Request,
    principal: Principal = Depends(require_principal),
    _: None = Depends(require_csrf_token),
):
    if principal.type == "recruiter" and payload.recruiter_id != principal.id:
        return JSONResponse(
            {"ok": False, "error": "permission_denied", "message": "Недостаточно прав для записи к другому рекрутёру."},
            status_code=403,
        )

    async with async_session() as session:
        recruiter = await session.get(Recruiter, int(payload.recruiter_id))
        city = await session.get(City, int(payload.city_id))
        if recruiter is None:
            return JSONResponse({"ok": False, "error": "recruiter_not_found"}, status_code=404)
        if city is None:
            return JSONResponse({"ok": False, "error": "city_not_found"}, status_code=404)
        if principal.type == "recruiter":
            allowed_city_ids = {
                int(row[0])
                for row in (
                    await session.execute(
                        select(recruiter_city_association.c.city_id).where(
                            recruiter_city_association.c.recruiter_id == principal.id
                        )
                    )
                ).all()
                if row[0] is not None
            }
            if int(city.id) not in allowed_city_ids:
                return JSONResponse(
                    {"ok": False, "error": "permission_denied", "message": "Город недоступен для этого рекрутёра."},
                    status_code=403,
                )

        candidate: Optional[User] = None
        if payload.candidate_id is not None:
            candidate = await session.get(User, int(payload.candidate_id))
            if candidate is None:
                return JSONResponse({"ok": False, "error": "candidate_not_found"}, status_code=404)

    recruiter_tz = getattr(recruiter, "tz", None) or "Europe/Moscow"
    dt_utc = recruiter_time_to_utc(payload.date, payload.time, recruiter_tz)
    if dt_utc is None:
        return JSONResponse(
            {"ok": False, "error": "invalid_datetime", "message": "Некорректная дата или время."},
            status_code=400,
        )

    if candidate is None:
        fio = sanitize_plain_text(str(payload.fio or "")).strip()
        phone = sanitize_plain_text(str(payload.phone or "")).strip() or None
        if not fio:
            return JSONResponse(
                {"ok": False, "error": "fio_required", "message": "Укажите ФИО кандидата."},
                status_code=400,
            )
        candidate = await upsert_candidate(
            telegram_id=None,
            fio=fio,
            city=getattr(city, "name_plain", None) or city.name,
            phone=phone,
            responsible_recruiter_id=recruiter.id,
            is_active=True,
            source="manual_silent",
            initial_status=None,
        )

    if payload.comment:
        async with async_session() as session:
            db_candidate = await session.get(User, int(candidate.id))
            if db_candidate is not None:
                db_candidate.manual_slot_comment = sanitize_plain_text(str(payload.comment or "")).strip() or None
                db_candidate.manual_slot_timezone = getattr(city, "tz", None) or recruiter_tz
                db_candidate.responsible_recruiter_id = recruiter.id
                if str(getattr(db_candidate, "source", "") or "").strip().lower() in {"", "manual_call"}:
                    db_candidate.source = "manual_silent"
                await session.commit()

    try:
        if payload.slot_id is not None:
            result = await assign_existing_candidate_slot_silent(
                slot_id=int(payload.slot_id),
                candidate=candidate,
                recruiter=recruiter,
                city=city,
                slot_tz=getattr(city, "tz", None) or recruiter_tz,
                admin_username=request.session.get("username", "admin"),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                principal=principal,
            )
        else:
            result = await schedule_manual_candidate_slot_silent(
                candidate=candidate,
                recruiter=recruiter,
                city=city,
                dt_utc=dt_utc,
                slot_tz=getattr(city, "tz", None) or recruiter_tz,
                admin_username=request.session.get("username", "admin"),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                principal=principal,
            )
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": "manual_booking_failed", "message": str(exc)},
            status_code=409,
        )

    return JSONResponse(
        {
            "ok": True,
            "candidate_id": int(candidate.id),
            "slot_id": getattr(getattr(result, "slot", None), "id", None),
            "status": result.status,
            "message": result.message,
            "manual_mode": True,
        },
        status_code=201,
    )


@router.delete("/slots/{slot_id}")
async def api_slot_delete(
    slot_id: int,
    request: Request,
    force: bool = Query(default=False),
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    if principal.type == "recruiter":
        async with async_session() as session:
            slot = await session.get(Slot, slot_id)
            if not slot:
                return JSONResponse({"ok": False, "message": "Слот не найден"}, status_code=404)
            ensure_slot_scope(slot, principal)
            if norm_status(slot.status) != "FREE":
                return JSONResponse({"ok": False, "message": "Удалять можно только свободные слоты"}, status_code=400)
        force = False
    ok, message = await delete_slot(slot_id, force=force, principal=principal)
    if not ok:
        status_code = 404 if message and "не найден" in message.lower() else 400
        return JSONResponse({"ok": False, "message": message}, status_code=status_code)
    return JSONResponse({"ok": True})


@router.post("/slots/bulk")
async def api_slots_bulk(
    payload: SlotsBulkPayload,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    action = (payload.action or "").lower()
    slot_ids = payload.slot_ids or []
    if not slot_ids:
        return JSONResponse({"ok": False, "error": "no_slots"}, status_code=400)
    if action == "delete":
        deleted, failed = await bulk_delete_slots(slot_ids, force=bool(payload.force), principal=principal)
        return JSONResponse({"ok": True, "deleted": deleted, "failed": failed})
    if action == "remind":
        scheduled, missing = await bulk_schedule_reminders(slot_ids, principal=principal)
        return JSONResponse({"ok": True, "scheduled": scheduled, "missing": missing})
    return JSONResponse({"ok": False, "error": "unsupported_action"}, status_code=400)


@router.get("/recruiter-plan")
async def api_recruiter_plan(principal: Principal = Depends(require_principal)):
    if principal.type != "recruiter":
        raise HTTPException(status_code=403, detail="Forbidden")
    payload = await get_recruiter_plan(principal.id)
    return JSONResponse(payload)


@router.post("/recruiter-plan/{city_id}/entries")
async def api_recruiter_plan_add(
    city_id: int,
    payload: PlanEntryPayload,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    if principal.type != "recruiter":
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        entry = await add_recruiter_plan_entry(principal.id, city_id, payload.last_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="last_name is required")
    except LookupError:
        raise HTTPException(status_code=404, detail="City not found")
    return JSONResponse(entry, status_code=201)


@router.delete("/recruiter-plan/entries/{entry_id}")
async def api_recruiter_plan_delete(
    entry_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    if principal.type != "recruiter":
        raise HTTPException(status_code=403, detail="Forbidden")
    ok = await delete_recruiter_plan_entry(principal.id, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return JSONResponse({"ok": True})


@router.get("/kpis/current")
async def api_weekly_kpis(
    company_tz: Optional[str] = Query(default=None),
    recruiter: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_principal),
):
    recruiter_id = parse_optional_int(recruiter) if principal.type == "admin" else None
    try:
        payload = await get_weekly_kpis(company_tz, principal=principal, recruiter_id=recruiter_id)
    except Exception:
        logger.exception(
            "kpis.current.failed",
            extra={"principal": getattr(principal, "type", None), "recruiter_id": recruiter_id},
        )
        payload = _empty_weekly_kpis(company_tz)
        payload["error"] = "kpis_unavailable"
    return JSONResponse(payload)


@router.get("/kpis/history")
async def api_weekly_history(
    limit: int = Query(default=12, ge=1, le=104),
    offset: int = Query(default=0, ge=0),
):
    return JSONResponse(await list_weekly_history(limit=limit, offset=offset))


@router.get("/timezones")
async def api_timezones():
    return JSONResponse(timezone_options())


@router.get("/city_owners")
async def api_city_owners():
    payload = await api_city_owners_payload()
    status_code = 200 if payload.get("ok") else 400
    return JSONResponse(payload, status_code=status_code)


@router.get("/notifications/feed")
async def api_notifications_feed(
    request: Request,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    _: Principal = Depends(require_admin),
):
    if getattr(request.app.state, "db_available", True) is False:
        return JSONResponse({"items": [], "latest_id": after_id, "degraded": True})
    from backend.apps.admin_ui.services.notifications_ops import list_outbox_notifications

    payload = await list_outbox_notifications(
        after_id=after_id,
        limit=limit,
        status=status,
        type=type,
    )
    return JSONResponse({**payload, "degraded": False})


@router.get("/notifications/logs")
async def api_notifications_logs(
    request: Request,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    candidate_tg_id: Optional[int] = Query(default=None, ge=1),
    booking_id: Optional[int] = Query(default=None, ge=1),
    _: Principal = Depends(require_admin),
):
    if getattr(request.app.state, "db_available", True) is False:
        return JSONResponse({"items": [], "latest_id": after_id, "degraded": True})
    from backend.apps.admin_ui.services.notifications_ops import list_notification_logs

    payload = await list_notification_logs(
        after_id=after_id,
        limit=limit,
        status=status,
        type=type,
        candidate_tg_id=candidate_tg_id,
        booking_id=booking_id,
    )
    return JSONResponse({**payload, "degraded": False})


@router.get("/system/messenger-health")
async def api_system_messenger_health(
    _: Principal = Depends(require_admin),
):
    return JSONResponse(await get_messenger_health_snapshot())


@router.post("/system/messenger-health/{channel}/recover")
async def api_recover_messenger_channel(
    channel: str,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    normalized_channel = str(channel or "").strip().lower()
    if normalized_channel not in {"telegram", "max"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Неизвестный канал"},
        )
    await mark_messenger_channel_healthy(normalized_channel)
    await log_audit_action(
        "messenger_channel_recovered",
        "messenger_channel",
        normalized_channel,
        changes={"channel": normalized_channel, "action": "recover"},
    )
    return JSONResponse({"ok": True, "channel": normalized_channel})


@router.post("/notifications/{notification_id}/retry")
async def api_notifications_retry(
    notification_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    from backend.apps.admin_ui.services.notifications_ops import retry_outbox_notification

    ok, error = await retry_outbox_notification(notification_id)
    if not ok:
        status_code = 404 if error == "not_found" else 409
        return JSONResponse({"ok": False, "error": error}, status_code=status_code)
    await log_audit_action(
        "outbox_retry",
        "outbox_notification",
        notification_id,
        changes={"action": "retry"},
    )
    return JSONResponse({"ok": True})


@router.post("/notifications/{notification_id}/cancel")
async def api_notifications_cancel(
    notification_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    from backend.apps.admin_ui.services.notifications_ops import cancel_outbox_notification

    ok, error = await cancel_outbox_notification(notification_id)
    if not ok:
        status_code = 404 if error == "not_found" else 409
        return JSONResponse({"ok": False, "error": error}, status_code=status_code)
    await log_audit_action(
        "outbox_cancel",
        "outbox_notification",
        notification_id,
        changes={"action": "cancel"},
    )
    return JSONResponse({"ok": True})


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
        "switch_source": switch.source if switch else "operator",
        "switch_reason": switch.reason if switch else None,
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

    switch.set(enabled_value, source="operator", reason=None)
    bot_service = getattr(request.app.state, "bot_service", None)
    payload = {
        "ok": True,
        "runtime_enabled": switch.is_enabled(),
        "switch_source": switch.source,
        "switch_reason": switch.reason,
        "updated_at": switch.updated_at.isoformat(),
        "service_health": bot_service.health_status if bot_service else "missing",
        "service_ready": bot_service.is_ready() if bot_service else False,
    }
    return JSONResponse(payload)


@router.post("/bot/cities/refresh")
async def api_bot_cities_refresh(
    _: Principal = Depends(require_admin),
    __: None = Depends(require_csrf_token),
) -> JSONResponse:
    try:
        await invalidate_city_caches()
    except Exception as exc:  # pragma: no cover - defensive
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    return JSONResponse({"ok": True})


@router.get("/bot/reminder-policy")
async def api_bot_reminder_policy(
    _: Principal = Depends(require_admin),
):
    policy, updated_at = await get_reminder_policy_config()
    return JSONResponse(
        {
            "policy": policy,
            "updated_at": updated_at.isoformat() if updated_at else None,
            "links": {
                "questions": "/app/questions",
                "message_templates": "/app/message-templates",
                "templates": "/app/templates",
            },
        }
    )


@router.put("/bot/reminder-policy")
async def api_bot_reminder_policy_update(
    request: Request,
    _: Principal = Depends(require_admin),
):
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    raw_policy = data.get("policy", data)
    policy, updated_at = await save_reminder_policy_config(raw_policy)

    rescheduled = {"scheduled": 0, "failed": 0}
    reminder_service = getattr(request.app.state, "reminder_service", None)
    if reminder_service is not None and hasattr(reminder_service, "reschedule_active_slots"):
        try:
            value = await reminder_service.reschedule_active_slots()
            if isinstance(value, dict):
                rescheduled["scheduled"] = int(value.get("scheduled", 0))
                rescheduled["failed"] = int(value.get("failed", 0))
        except Exception:
            logger.exception("Failed to reschedule reminders after policy update")

    # Best-effort: notify the standalone bot process to reload reminder policy and reschedule jobs.
    await publish_content_update(KIND_REMINDERS_CHANGED, {"key": "reminder_policy"})

    return JSONResponse(
        {
            "ok": True,
            "policy": policy,
            "updated_at": updated_at.isoformat(),
            "rescheduled_slots": rescheduled["scheduled"],
            "reschedule_failed": rescheduled["failed"],
        }
    )


@router.get("/bot/reminders/jobs")
async def api_bot_reminder_jobs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    kind: Optional[str] = Query(default=None),
    slot_id: Optional[int] = Query(default=None, ge=1),
    candidate_tg_id: Optional[int] = Query(default=None, ge=1),
    _: Principal = Depends(require_admin),
):
    """List upcoming reminder jobs persisted in the database."""
    if getattr(request.app.state, "db_available", True) is False:
        return JSONResponse({"items": [], "now_utc": datetime.now(timezone.utc).isoformat(), "degraded": True})

    from backend.apps.admin_ui.services.reminders_ops import list_reminder_jobs

    payload = await list_reminder_jobs(
        limit=limit,
        kind=kind,
        slot_id=slot_id,
        candidate_tg_id=candidate_tg_id,
    )
    return JSONResponse({**payload, "degraded": False})


@router.post("/bot/reminders/resync")
async def api_bot_reminder_resync(
    request: Request,
    _: Principal = Depends(require_admin),
):
    """Rebuild reminder jobs for active slots (best effort)."""
    _ = await require_csrf_token(request)

    reminder_service = getattr(request.app.state, "reminder_service", None)
    if reminder_service is None or not hasattr(reminder_service, "reschedule_active_slots"):
        return JSONResponse({"ok": False, "error": "reminder_service_unavailable"}, status_code=503)

    try:
        value = await reminder_service.reschedule_active_slots()
    except Exception:
        logger.exception("Failed to resync reminder jobs")
        return JSONResponse({"ok": False, "error": "resync_failed"}, status_code=500)

    scheduled = 0
    failed = 0
    if isinstance(value, dict):
        scheduled = int(value.get("scheduled", 0) or 0)
        failed = int(value.get("failed", 0) or 0)

    await log_audit_action(
        "reminder_resync",
        "system",
        0,
        changes={"scheduled": scheduled, "failed": failed},
    )

    return JSONResponse({"ok": True, "scheduled": scheduled, "failed": failed})


@router.delete("/bot/reminder-jobs/{job_id:path}")
async def api_cancel_reminder_job(
    request: Request, job_id: str
) -> JSONResponse:
    _ = await require_csrf_token(request)
    reminder_service = getattr(request.app.state, "reminder_service", None)
    if reminder_service is None:
        return JSONResponse({"ok": False, "error": "reminder_service_unavailable"}, status_code=503)

    cancelled = await reminder_service.cancel_job(job_id)
    if not cancelled:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return JSONResponse({"ok": True})


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


async def _get_accessible_candidate(candidate_id: int, principal: Principal) -> User:
    from backend.domain.repositories import find_city_by_plain_name

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail={"message": "Кандидат не найден"},
            )
        if principal.type == "recruiter" and user.responsible_recruiter_id != principal.id:
            if not user.city:
                raise HTTPException(
                    status_code=404,
                    detail={"message": "Кандидат не найден"},
                )
            city_record = await find_city_by_plain_name(user.city)
            if city_record is None:
                raise HTTPException(
                    status_code=404,
                    detail={"message": "Кандидат не найден"},
                )
            rows = await session.execute(
                select(recruiter_city_association.c.city_id)
                .where(recruiter_city_association.c.recruiter_id == principal.id)
            )
            allowed_city_ids = {int(row[0]) for row in rows if row[0] is not None}
            if int(city_record.id) not in allowed_city_ids:
                raise HTTPException(
                    status_code=404,
                    detail={"message": "Кандидат не найден"},
                )
        session.expunge(user)
        return user


@router.get("/candidates/{candidate_id}/chat")
async def api_chat_history(
    candidate_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    before: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    await _get_accessible_candidate(candidate_id, principal)
    before_dt = _parse_iso_datetime(before)
    payload = await list_chat_history(candidate_id, limit=limit, before=before_dt)
    return JSONResponse(payload)


@router.get("/candidates/{candidate_id}/chat/updates")
async def api_chat_history_updates(
    candidate_id: int,
    since: Optional[str] = Query(default=None),
    timeout: int = Query(default=25, ge=5, le=60),
    limit: int = Query(default=80, ge=1, le=200),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    await _get_accessible_candidate(candidate_id, principal)
    since_dt = _parse_datetime_param(since)
    payload = await wait_for_chat_history_updates(
        candidate_id,
        since=since_dt,
        timeout=timeout,
        limit=limit,
    )
    return JSONResponse(jsonable_encoder(payload))


@router.post("/candidates/{candidate_id}/chat")
async def api_chat_send(
    request: Request,
    candidate_id: int,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    await _get_accessible_candidate(candidate_id, principal)
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
    author_label = getattr(request.state, "admin_username", None)
    if not author_label:
        author_label = "Администратор" if principal.type == "admin" else "Рекрутер"

    result = await send_chat_message(
        candidate_id,
        text=text,
        client_request_id=client_request_id,
        author_label=author_label,
        bot_service=bot_service,
    )
    return JSONResponse(result)


@router.post("/candidates/{candidate_id}/chat/quick-action")
async def api_chat_quick_action(
    request: Request,
    candidate_id: int,
    payload: CandidateChatQuickActionPayload,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    await _get_accessible_candidate(candidate_id, principal)

    target_status = str(payload.status or "").strip().lower()
    if not target_status:
        raise HTTPException(status_code=400, detail={"message": "Статус обязателен"})

    prepared_message = ""
    if payload.send_message:
        prepared_message = str(payload.message_text or "").strip() or _chat_template_text(payload.template_key) or ""
        if not prepared_message:
            raise HTTPException(status_code=400, detail={"message": "Выберите или заполните сообщение"})

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id,
        target_status,
        bot_service=bot_service,
        principal=principal,
    )
    if not ok:
        return JSONResponse({"ok": False, "message": message}, status_code=400)

    if dispatch and dispatch.plan:
        background_tasks.add_task(
            execute_bot_dispatch,
            dispatch.plan,
            stored_status or "",
            bot_service,
        )

    response: dict[str, object] = {
        "ok": True,
        "message": message,
        "status": stored_status,
    }
    if not payload.send_message:
        return JSONResponse(response)

    author_label = getattr(request.state, "admin_username", None)
    if not author_label:
        author_label = "Администратор" if principal.type == "admin" else "Рекрутер"

    try:
        send_result = await send_chat_message(
            candidate_id,
            text=sanitize_plain_text(prepared_message, max_length=2000),
            client_request_id=f"quick-action:{candidate_id}:{datetime.now(timezone.utc).timestamp()}",
            author_label=author_label,
            bot_service=bot_service,
        )
        response["chat_message"] = send_result.get("message")
        response["chat_delivery_status"] = send_result.get("status")
    except HTTPException as exc:
        response["chat_delivery_status"] = "failed"
        response["chat_delivery_error"] = (
            exc.detail.get("message")
            if isinstance(exc.detail, dict)
            else str(exc.detail)
        )

    return JSONResponse(response)


@router.post("/candidates/{candidate_id}/chat/{message_id}/retry")
async def api_chat_retry(
    candidate_id: int,
    message_id: int,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    await _get_accessible_candidate(candidate_id, principal)
    result = await retry_chat_message(candidate_id, message_id, bot_service=bot_service)
    return JSONResponse(result)


async def _candidate_portal_link_errors_async() -> list[str]:
    portal_status = get_candidate_portal_public_status()
    max_status = await get_candidate_portal_max_entry_status_async()
    errors = []
    if portal_status.get("message"):
        errors.append(str(portal_status["message"]))
    if max_status.get("message") and str(max_status["message"]) not in errors:
        errors.append(str(max_status["message"]))
    return errors


async def _ensure_max_access_adapter():
    adapter = get_registry().get(MessengerPlatform.MAX)
    if adapter is not None:
        return adapter

    settings = get_settings()
    if not settings.max_bot_enabled or not settings.max_bot_token:
        return None

    try:
        await bootstrap_messenger_adapters(
            bot=None,
            max_bot_enabled=settings.max_bot_enabled,
            max_bot_token=settings.max_bot_token,
        )
    except Exception:
        logger.exception("candidate_portal.max_adapter_bootstrap_failed")
        return None
    return get_registry().get(MessengerPlatform.MAX)


def _candidate_portal_entry_buttons(*, browser_link: str | None, mini_app_link: str | None) -> list[list[InlineButton]] | None:
    buttons: list[list[InlineButton]] = []
    if mini_app_link:
        buttons.append([InlineButton(text="Открыть кабинет", url=mini_app_link, kind="web_app")])
    if browser_link:
        buttons.append([InlineButton(text="Открыть в браузере", url=browser_link, kind="link")])
    return buttons or None


def _candidate_portal_access_message(
    *,
    candidate_name: str,
    status_label: str,
    next_action: str,
    restarted: bool,
    browser_link: str | None,
    mini_app_link: str | None,
) -> str:
    lines = [
        "Личный кабинет кандидата обновлён." if not restarted else "Кабинет сброшен и готов к повторному прохождению.",
        f"Кандидат: <b>{candidate_name}</b>",
        f"Статус: <b>{status_label}</b>",
        next_action,
    ]
    if mini_app_link:
        lines.append("Откройте кабинет в MAX.")
    elif browser_link:
        lines.append("Откройте кабинет в браузере по новой ссылке.")
    return "\n".join(lines)


async def _record_candidate_portal_access_message(
    *,
    candidate_id: int,
    channel: str,
    text: str,
    success: bool,
    error: str | None = None,
) -> None:
    async with async_session() as session:
        async with session.begin():
            session.add(
                ChatMessage(
                    candidate_id=int(candidate_id),
                    direction=ChatMessageDirection.OUTBOUND.value,
                    channel=channel,
                    text=text,
                    status=ChatMessageStatus.SENT.value if success else ChatMessageStatus.FAILED.value,
                    error=error,
                    author_label="System",
                    payload_json={"kind": "portal_access_package"},
                    created_at=datetime.now(timezone.utc),
                )
            )


async def _deliver_candidate_portal_access_package(
    *,
    candidate: User,
    text: str,
    browser_link: str | None,
    mini_app_link: str | None,
    delivery_allowed: bool,
    skip_reason: str | None = None,
) -> dict[str, Any]:
    if not delivery_allowed:
        return {
            "status": "skipped_by_preflight",
            "sent": False,
            "attempted": False,
            "error": None,
            "skipped_reason": skip_reason,
        }
    if not browser_link and not mini_app_link:
        return {
            "status": "skipped_no_entry",
            "sent": False,
            "attempted": False,
            "error": "Нет публичной ссылки кабинета",
            "skipped_reason": skip_reason or "candidate_portal_entry_missing",
        }
    if not str(candidate.max_user_id or "").strip():
        return {
            "status": "not_linked",
            "sent": False,
            "attempted": False,
            "error": "MAX ID не привязан",
            "skipped_reason": skip_reason or "max_not_linked",
        }

    adapter = await _ensure_max_access_adapter()
    if adapter is None:
        return {
            "status": "adapter_unavailable",
            "sent": False,
            "attempted": False,
            "error": "MAX bot не готов",
            "skipped_reason": skip_reason or "max_adapter_unavailable",
        }

    try:
        result = await adapter.send_message(
            str(candidate.max_user_id),
            text,
            buttons=_candidate_portal_entry_buttons(browser_link=browser_link, mini_app_link=mini_app_link),
            parse_mode="HTML",
            correlation_id=f"candidate-portal-access:{candidate.id}:{int(datetime.now(timezone.utc).timestamp())}",
        )
    except Exception as exc:
        logger.exception("candidate_portal.max_delivery_failed", extra={"candidate_id": candidate.id})
        await _record_candidate_portal_access_message(
            candidate_id=int(candidate.id),
            channel="max",
            text=text,
            success=False,
            error=str(exc),
        )
        return {
            "status": "failed",
            "sent": False,
            "attempted": True,
            "error": str(exc),
            "skipped_reason": None,
        }

    success = bool(getattr(result, "success", False) or getattr(result, "ok", False))
    error = None if success else str(getattr(result, "error", None) or "delivery_failed")
    await _record_candidate_portal_access_message(
        candidate_id=int(candidate.id),
        channel="max",
        text=text,
        success=success,
        error=error,
    )
    return {
        "status": "sent" if success else "failed",
        "sent": success,
        "attempted": True,
        "error": error,
        "skipped_reason": None,
    }


async def _build_candidate_portal_access_delivery_text(
    *,
    candidate_id: int,
    journey_id: int,
    restarted: bool,
    browser_link: str | None,
    mini_app_link: str | None,
) -> str:
    async with async_session() as session:
        candidate = await session.get(User, int(candidate_id))
        journey = await session.get(CandidateJourneySession, int(journey_id))
        if candidate is None or journey is None:
            return "Личный кабинет кандидата обновлён. Откройте его по новой ссылке."
        journey_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel="max",
            journey=journey,
        )
    return _candidate_portal_access_message(
        candidate_name=str(candidate.fio or f"#{candidate.id}"),
        status_label=str(journey_payload["candidate"].get("status_label") or "В обработке"),
        next_action=str(journey_payload["journey"].get("next_action") or "Откройте кабинет, чтобы продолжить."),
        restarted=restarted,
        browser_link=browser_link,
        mini_app_link=mini_app_link,
    )


async def _candidate_portal_access_payload(
    *,
    session,
    candidate: User,
    journey: CandidateJourneySession,
    invite: CandidateInviteToken,
    rotated: bool,
    restarted: bool = False,
) -> dict[str, Any]:
    portal_status = get_candidate_portal_public_status()
    max_status = await get_candidate_portal_max_entry_status_async()
    browser_link = build_candidate_public_portal_url(
        candidate_uuid=str(candidate.candidate_id) if candidate.candidate_id else None,
        telegram_id=int(candidate.telegram_id) if candidate.telegram_id is not None and not candidate.candidate_id else None,
        entry_channel="max",
        source_channel="max_browser" if not restarted else "max_browser_restart",
        journey_session_id=int(journey.id),
        session_version=int(journey.session_version or 1),
    )
    mini_app_link = await build_candidate_public_max_mini_app_url_async(
        candidate_uuid=str(candidate.candidate_id),
        journey_session_id=int(journey.id),
        session_version=int(journey.session_version or 1),
        source_channel="max_app_restart" if restarted else "max_app",
    )

    public_link = str(max_status.get("url") or "").strip().rstrip("/")
    deep_link = ""
    if public_link and invite.token:
        separator = "&" if "?" in public_link else "?"
        deep_link = f"{public_link}{separator}start={quote(str(invite.token), safe='')}"
    delivery_block_reason = None
    if not portal_status.get("ready"):
        delivery_block_reason = str(portal_status.get("error") or "candidate_portal_public_url_invalid")
    elif not max_status.get("ready"):
        delivery_block_reason = str(max_status.get("error") or "max_entry_blocked")
    elif not str(candidate.max_user_id or "").strip():
        delivery_block_reason = "max_not_linked"
    delivery_ready = delivery_block_reason is None

    return {
        "public_link": public_link,
        "portal_public_url": portal_status.get("url"),
        "portal_entry_ready": bool(portal_status.get("ready")),
        "max_entry_ready": bool(max_status.get("ready")),
        "token_valid": max_status.get("token_valid"),
        "bot_profile_resolved": bool(max_status.get("bot_profile_resolved")),
        "bot_profile_name": max_status.get("bot_profile_name"),
        "max_link_base_resolved": bool(max_status.get("max_link_base_resolved")),
        "max_link_base_source": max_status.get("max_link_base_source"),
        "browser_link": browser_link or None,
        "invite_token": str(invite.token or ""),
        "deep_link": deep_link or None,
        "mini_app_link": mini_app_link or None,
        "invite": {
            "channel": "max",
            "status": "active",
            "rotated": bool(rotated),
        },
        "issued_at": invite.created_at.isoformat() if invite.created_at else None,
        "journey": {
            "id": int(journey.id),
            "session_version": int(journey.session_version or 1),
            "restarted": bool(restarted),
        },
        "config_errors": await _candidate_portal_link_errors_async(),
        "delivery_ready": delivery_ready,
        "delivery_block_reason": delivery_block_reason,
        "readiness_reason": delivery_block_reason or None,
    }


@router.post("/candidates/{candidate_id}/channels/max-link")
async def api_candidate_max_link(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    candidate = await _get_accessible_candidate(candidate_id, principal)
    portal_status = get_candidate_portal_public_status()
    if not portal_status["ready"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": portal_status["message"]},
        )

    async with async_session() as session:
        async with session.begin():
            stored_candidate = await session.get(User, candidate.id)
            if stored_candidate is None or not stored_candidate.candidate_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"message": "Не удалось выпустить MAX-ссылку"},
                )
            previous_invite = await session.scalar(
                select(CandidateInviteToken)
                .where(
                    CandidateInviteToken.candidate_id == stored_candidate.candidate_id,
                    CandidateInviteToken.channel == "max",
                    CandidateInviteToken.status == "active",
                )
                .order_by(CandidateInviteToken.created_at.desc(), CandidateInviteToken.id.desc())
                .limit(1)
            )
            invite, superseded_ids = await issue_candidate_invite_token(
                stored_candidate.candidate_id,
                channel="max",
                rotate_active=True,
                session=session,
            )
            invite_id = int(invite.id)
            journey = await ensure_candidate_portal_session(
                session,
                stored_candidate,
                entry_channel="max",
            )
            await bump_candidate_portal_session_version(session, candidate_id=int(stored_candidate.id))
            await session.refresh(journey)
            previous_invite_id = int(previous_invite.id) if previous_invite is not None else None
            payload = await _candidate_portal_access_payload(
                session=session,
                candidate=stored_candidate,
                journey=journey,
                invite=invite,
                rotated=bool(previous_invite is not None or superseded_ids),
            )
            delivery_candidate = stored_candidate

    delivery_text = await _build_candidate_portal_access_delivery_text(
        candidate_id=int(delivery_candidate.id),
        journey_id=int(payload["journey"]["id"]),
        restarted=False,
        browser_link=payload.get("browser_link"),
        mini_app_link=payload.get("mini_app_link"),
    )
    payload["delivery"] = await _deliver_candidate_portal_access_package(
        candidate=delivery_candidate,
        text=delivery_text,
        browser_link=payload.get("browser_link"),
        mini_app_link=payload.get("mini_app_link"),
        delivery_allowed=bool(payload.get("delivery_ready")),
        skip_reason=str(payload.get("delivery_block_reason") or "") or None,
    )

    await log_audit_action(
        "invite_issued",
        "candidate",
        candidate_id,
        changes={"channel": "max", "invite_id": invite_id},
    )
    if previous_invite is not None or superseded_ids:
        await log_audit_action(
            "invite_superseded",
            "candidate",
            candidate_id,
            changes={
                "channel": "max",
                "previous_invite_id": previous_invite_id,
                "superseded_ids": superseded_ids,
            },
        )
    await log_audit_action(
        "candidate_portal_reissued",
        "candidate",
        candidate_id,
        changes={
            "channel": "max",
            "journey_id": payload["journey"]["id"],
            "session_version": payload["journey"]["session_version"],
            "delivered": bool((payload.get("delivery") or {}).get("sent")),
        },
    )
    return JSONResponse(payload)


@router.post("/candidates/{candidate_id}/portal/restart")
async def api_candidate_portal_restart(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    candidate = await _get_accessible_candidate(candidate_id, principal)
    portal_status = get_candidate_portal_public_status()
    if not portal_status["ready"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": portal_status["message"]},
        )

    async with async_session() as session:
        async with session.begin():
            stored_candidate = await session.get(User, candidate.id)
            if stored_candidate is None or not stored_candidate.candidate_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"message": "Не удалось перезапустить кабинет кандидата"},
                )
            previous_invite = await session.scalar(
                select(CandidateInviteToken)
                .where(
                    CandidateInviteToken.candidate_id == stored_candidate.candidate_id,
                    CandidateInviteToken.channel == "max",
                    CandidateInviteToken.status == "active",
                )
                .order_by(CandidateInviteToken.created_at.desc(), CandidateInviteToken.id.desc())
                .limit(1)
            )
            try:
                journey, released_slot_id = await restart_candidate_portal_journey(
                    session,
                    stored_candidate,
                    entry_channel="max",
                )
            except CandidatePortalError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"message": str(exc)},
                ) from exc
            invite, superseded_ids = await issue_candidate_invite_token(
                stored_candidate.candidate_id,
                channel="max",
                rotate_active=True,
                session=session,
            )
            previous_invite_id = int(previous_invite.id) if previous_invite is not None else None
            payload = await _candidate_portal_access_payload(
                session=session,
                candidate=stored_candidate,
                journey=journey,
                invite=invite,
                rotated=bool(previous_invite is not None or superseded_ids),
                restarted=True,
            )
            delivery_candidate = stored_candidate

    delivery_text = await _build_candidate_portal_access_delivery_text(
        candidate_id=int(delivery_candidate.id),
        journey_id=int(payload["journey"]["id"]),
        restarted=True,
        browser_link=payload.get("browser_link"),
        mini_app_link=payload.get("mini_app_link"),
    )
    payload["delivery"] = await _deliver_candidate_portal_access_package(
        candidate=delivery_candidate,
        text=delivery_text,
        browser_link=payload.get("browser_link"),
        mini_app_link=payload.get("mini_app_link"),
        delivery_allowed=bool(payload.get("delivery_ready")),
        skip_reason=str(payload.get("delivery_block_reason") or "") or None,
    )

    await log_audit_action(
        "candidate_portal_restarted",
        "candidate",
        candidate_id,
        changes={
            "journey_id": payload["journey"]["id"],
            "session_version": payload["journey"]["session_version"],
            "released_slot_id": released_slot_id,
            "delivered": bool((payload.get("delivery") or {}).get("sent")),
        },
    )
    await log_audit_action(
        "invite_issued",
        "candidate",
        candidate_id,
        changes={"channel": "max", "invite_id": int(invite.id)},
    )
    if previous_invite is not None or superseded_ids:
        await log_audit_action(
            "invite_superseded",
            "candidate",
            candidate_id,
            changes={
                "channel": "max",
                "previous_invite_id": previous_invite_id,
                "superseded_ids": superseded_ids,
            },
        )
    return JSONResponse(payload)


@router.get("/candidates/{candidate_id}/channel-health")
async def api_candidate_channel_health(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
):
    await _get_accessible_candidate(candidate_id, principal)
    payload = await get_candidate_channel_health(candidate_id)
    if payload is None:
        raise HTTPException(status_code=404, detail={"message": "Кандидат не найден"})
    return JSONResponse(jsonable_encoder(payload))


@router.get("/candidates/{candidate_id}")
async def api_candidate(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
):
    await _get_accessible_candidate(candidate_id, principal)
    detail = await api_candidate_detail_payload(candidate_id)
    if detail is None:
        raise HTTPException(status_code=404, detail={"message": "Кандидат не найден"})
    return JSONResponse(jsonable_encoder(detail))


@router.get("/candidates/{candidate_id}/hh")
async def api_candidate_hh_summary(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
):
    await _get_accessible_candidate(candidate_id, principal)
    async with async_session() as session:
        summary = await build_candidate_hh_summary(session, candidate_id=candidate_id)
    return JSONResponse(jsonable_encoder(summary))


@router.get("/candidates/{candidate_id}/cohort-comparison")
async def api_candidate_cohort_comparison(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
):
    await _get_accessible_candidate(candidate_id, principal)
    payload = await get_candidate_cohort_comparison(candidate_id, principal=principal)
    return JSONResponse(jsonable_encoder(payload or {"available": False}))


@router.delete("/candidates/{candidate_id}")
async def api_candidate_delete(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    ok = await delete_candidate(candidate_id, principal=principal)
    if not ok:
        raise HTTPException(status_code=404, detail={"message": "Кандидат не найден"})
    return JSONResponse({"ok": True, "id": candidate_id})


@router.get("/candidates")
async def api_candidates_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=5, le=100),
    search: Optional[str] = Query(None),
    status: Optional[list[str]] = Query(None),
    recruiter_id: Optional[str] = Query(None),
    active: Optional[str] = Query(None),
    pipeline: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    calendar_mode: Optional[str] = Query(None),
    principal: Principal = Depends(require_principal),
):
    status_values = tuple(sorted({str(item).strip().lower() for item in (status or []) if str(item).strip()}))
    range_start = _parse_date_param(date_from)
    range_end = _parse_date_param(date_to, end=True)
    parsed_recruiter_id = parse_optional_int(recruiter_id)
    parsed_active = _parse_bool(active)
    pipeline_slug = pipeline or "interview"

    async def _compute_payload() -> dict[str, object]:
        data = await list_candidates(
            page=page,
            per_page=per_page,
            search=search,
            city=None,
            is_active=parsed_active,
            rating=None,
            has_tests=None,
            has_messages=None,
            stage=None,
            statuses=list(status_values) if status_values else None,
            recruiter_id=parsed_recruiter_id,
            city_ids=None,
            date_from=range_start,
            date_to=range_end,
            test1_status=None,
            test2_status=None,
            sort=None,
            sort_dir=None,
            calendar_mode=calendar_mode,
            pipeline=pipeline_slug,
            principal=principal,
        )
        return {
            "items": data.get("views", {}).get("candidates", []),
            "total": data.get("total", 0),
            "page": data.get("page", page),
            "pages_total": data.get("pages_total", 1),
            "filters": data.get("filters", {}),
            "pipeline": data.get("pipeline", pipeline_slug),
            "pipeline_options": data.get("pipeline_options", []),
            "views": data.get("views", {}),
        }

    # Cache only non-search first-page list to avoid caching PII from free-text queries.
    can_cache = (
        page == 1
        and (search is None or not str(search).strip())
        and (calendar_mode is None or not str(calendar_mode).strip())
    )
    if can_cache:
        key = (
            "candidates:list:v1:"
            f"{principal.type}:{principal.id}:pp{per_page}:"
            f"pipe:{pipeline_slug}:status:{','.join(status_values) or 'all'}:"
            f"rid:{parsed_recruiter_id or 'all'}:active:{parsed_active if parsed_active is not None else 'all'}:"
            f"from:{range_start.isoformat() if range_start else 'none'}:"
            f"to:{range_end.isoformat() if range_end else 'none'}"
        )
        payload = await get_or_compute(
            key,
            expected_type=dict,
            ttl_seconds=8.0,
            stale_seconds=12.0,
            compute=_compute_payload,
        )
        return JSONResponse(jsonable_encoder(payload))

    payload = await _compute_payload()
    return JSONResponse(jsonable_encoder(payload))


@router.post("/candidates/{candidate_id}/actions/{action_key}")
async def api_candidate_action(
    candidate_id: int,
    action_key: str,
    request: Request,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    payload = {}
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            payload = dict(await request.form())
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    reason = payload.get("reason") or payload.get("reject_reason")
    comment = payload.get("comment") or payload.get("reject_comment")
    
    # 1. Get candidate and allowed actions
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # 2. Find matching action definition
    # detail["candidate_actions"] is a list of CandidateAction objects
    actions = detail.get("candidate_actions", [])
    action_def = next((a for a in actions if a.key == action_key), None)
    
    if not action_def:
        logger.warning(f"Action {action_key} not allowed for candidate {candidate_id}")
        return JSONResponse(
            {"ok": False, "message": "Действие недоступно в текущем статусе"}, 
            status_code=400
        )

    # Special handling for approve_upcoming_slot
    if action_key == "approve_upcoming_slot":
        user = detail["user"]
        from sqlalchemy import select as sql_select
        async with async_session() as session:
            pending_slot = await session.scalar(
                sql_select(Slot)
                .where(
                    Slot.candidate_tg_id == user.telegram_id,
                    func.lower(Slot.status) == SlotStatus.PENDING,
                    Slot.start_utc >= datetime.now(timezone.utc),
                )
                .order_by(Slot.start_utc.asc())
                .limit(1)
            )
        if not pending_slot:
            return JSONResponse({"ok": False, "message": "Нет слотов, ожидающих подтверждения"}, status_code=400)
        ok, message, notified = await approve_slot_booking(pending_slot.id, principal=principal)
        if not ok:
            return JSONResponse({"ok": False, "message": message}, status_code=400)
        return JSONResponse({"ok": True, "message": "Собеседование подтверждено", "action": action_key})

    target_status = action_def.target_status

    if not target_status:
        # Action without status change
        return JSONResponse({"ok": True, "message": "Action executed"})

    # 3. Execute status change
    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id,
        target_status,
        bot_service=bot_service,
        principal=principal,
        reason=reason,
        comment=comment,
    )
    
    if not ok:
        return JSONResponse({"ok": False, "message": message}, status_code=400)
        
    # 4. Handle side effects (Bot)
    if dispatch and dispatch.plan:
        background_tasks.add_task(execute_bot_dispatch, dispatch.plan, stored_status or "", bot_service)
        
    return JSONResponse({
        "ok": True, 
        "message": message, 
        "status": stored_status,
        "action": action_key
    })


KANBAN_ALLOWED_TARGET_STATUSES = {
    "waiting_slot",
    "slot_pending",
    "interview_scheduled",
    "interview_confirmed",
    "test2_sent",
    "test2_completed",
    "intro_day_scheduled",
    "intro_day_confirmed_preliminary",
    "intro_day_confirmed_day_of",
}


@router.post("/candidates/{candidate_id}/kanban-status")
async def api_candidate_kanban_status(
    candidate_id: int,
    payload: CandidateKanbanMovePayload,
    request: Request,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)

    target_status = (payload.target_status or "").strip().lower()
    if target_status == "incoming":
        target_status = "waiting_slot"
    if target_status not in KANBAN_ALLOWED_TARGET_STATUSES:
        return JSONResponse(
            {"ok": False, "message": "Недопустимый статус для канбана"},
            status_code=400,
        )

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id,
        target_status,
        bot_service=bot_service,
        principal=principal,
    )
    if not ok:
        status_code = 404 if message == "Кандидат не найден" else 400
        return JSONResponse({"ok": False, "message": message}, status_code=status_code)

    if dispatch and dispatch.plan:
        background_tasks.add_task(
            execute_bot_dispatch,
            dispatch.plan,
            stored_status or "",
            bot_service,
        )

    return JSONResponse(
        {
            "ok": True,
            "message": message,
            "status": stored_status,
            "candidate_id": candidate_id,
        }
    )


@router.post("/candidates/{candidate_id}/assign-recruiter")
async def api_assign_candidate_recruiter(
    candidate_id: int,
    request: Request,
    principal: Principal = Depends(require_admin),
    _: None = Depends(require_csrf_token),
) -> JSONResponse:
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    recruiter_id = data.get("recruiter_id")
    if recruiter_id is None:
        raise HTTPException(status_code=400, detail={"message": "recruiter_id required"})
    try:
        recruiter_id_value = int(recruiter_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"message": "invalid recruiter_id"})
    try:
        ok = await assign_candidate_recruiter(candidate_id, recruiter_id_value, principal=principal)
    except ValueError:
        raise HTTPException(status_code=404, detail={"message": "Recruiter not found"})
    if not ok:
        raise HTTPException(status_code=404, detail={"message": "Кандидат не найден"})
    return JSONResponse({"ok": True, "recruiter_id": recruiter_id_value})


@router.post("/candidates", status_code=201)
@limiter.limit(CANDIDATE_CREATE_LIMIT, key_func=get_principal_identifier)
async def api_create_candidate(
    request: Request,
    _: None = Depends(require_csrf_token),
    principal: Principal = Depends(require_principal),
):
    """Create a new candidate (JSON API). Slot scheduling is a separate action."""
    from backend.apps.admin_ui.services.candidates import upsert_candidate

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    fio = sanitize_plain_text(str(data.get("fio") or "")).strip()
    phone = sanitize_plain_text(str(data.get("phone") or "")).strip() or None
    city_id = data.get("city_id")
    recruiter_id = data.get("recruiter_id")
    telegram_id_raw = data.get("telegram_id")

    if not fio:
        return JSONResponse({"ok": False, "error": "fio_required"}, status_code=400)

    # Validate city
    city_value = None
    interview_city = None
    if city_id:
        try:
            city_value = int(city_id)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "invalid_city_id"}, status_code=400)
        async with async_session() as session:
            interview_city = await session.get(City, city_value)
        if interview_city is None:
            return JSONResponse({"ok": False, "error": "city_not_found"}, status_code=404)

    # Validate recruiter
    recruiter_id_value = None
    interview_recruiter = None
    if recruiter_id:
        try:
            recruiter_id_value = int(recruiter_id)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "invalid_recruiter_id"}, status_code=400)
        # Recruiters can only create candidates for themselves
        if principal.type == "recruiter" and recruiter_id_value != principal.id:
            return JSONResponse({"ok": False, "error": "permission_denied"}, status_code=403)
        async with async_session() as session:
            interview_recruiter = await session.get(Recruiter, recruiter_id_value)
        if interview_recruiter is None:
            return JSONResponse({"ok": False, "error": "recruiter_not_found"}, status_code=404)

    if not city_value or not recruiter_id_value:
        return JSONResponse({"ok": False, "error": "city_and_recruiter_required"}, status_code=400)

    telegram_id_value: Optional[int] = None
    if telegram_id_raw not in (None, "", "null"):
        try:
            telegram_id_value = int(telegram_id_raw)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "invalid_telegram_id"}, status_code=400)
        async with async_session() as session:
            existing = await session.scalar(select(User).where(User.telegram_id == telegram_id_value))
            if existing is not None:
                return JSONResponse({"ok": False, "error": "duplicate_candidate"}, status_code=409)

    # Get city name for candidate
    candidate_city = None
    if interview_city:
        candidate_city = getattr(interview_city, "name_plain", None) or interview_city.name

    # Create candidate
    try:
        user = await upsert_candidate(
            telegram_id=telegram_id_value,
            fio=fio,
            city=candidate_city,
            phone=phone,
            is_active=True,
            responsible_recruiter_id=recruiter_id_value,
            manual_slot_from=None,
            manual_slot_to=None,
            manual_slot_timezone=None,
        )
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": "validation_error", "message": str(exc)}, status_code=400)
    except IntegrityError:
        return JSONResponse({"ok": False, "error": "duplicate_candidate"}, status_code=409)

    return JSONResponse(
        {
            "ok": True,
            "id": user.id,
            "fio": user.fio,
            "city": user.city,
            "slot_scheduled": False,
        },
        status_code=201,
    )


@router.get("/candidates/{candidate_id}/available-slots")
async def api_candidate_available_slots(
    candidate_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_principal),
):
    """Return nearest FREE interview slots that can be proposed to a candidate."""
    from backend.apps.admin_ui.timezones import DEFAULT_TZ
    from backend.domain.repositories import find_city_by_plain_name

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(status_code=404, detail={"message": "Кандидат не найден"})

        candidate_city_id: Optional[int] = None
        if user.city:
            city_record = await find_city_by_plain_name(user.city)
            candidate_city_id = getattr(city_record, "id", None)

        if principal.type == "recruiter" and user.responsible_recruiter_id != principal.id:
            rows = await session.execute(
                select(recruiter_city_association.c.city_id)
                .where(recruiter_city_association.c.recruiter_id == principal.id)
            )
            allowed_city_ids = {row[0] for row in rows}
            if candidate_city_id is None:
                raise HTTPException(
                    status_code=409,
                    detail={"message": "У кандидата не указан город — назначение недоступно."},
                )
            if candidate_city_id not in allowed_city_ids:
                raise HTTPException(
                    status_code=403,
                    detail={"message": "Кандидат из другого города — назначение недоступно."},
                )

        slots_stmt = (
            select(Slot, Recruiter, City)
            .join(Recruiter, Slot.recruiter_id == Recruiter.id)
            .outerjoin(City, Slot.city_id == City.id)
            .where(
                func.lower(Slot.status) == SlotStatus.FREE,
                func.coalesce(Slot.purpose, "interview") == "interview",
                Slot.start_utc >= now,
            )
            .order_by(Slot.start_utc.asc(), Slot.id.asc())
            .limit(limit)
        )
        if principal.type == "recruiter":
            slots_stmt = slots_stmt.where(Slot.recruiter_id == principal.id)
        if candidate_city_id is not None:
            slots_stmt = slots_stmt.where(Slot.city_id == candidate_city_id)

        rows = (await session.execute(slots_stmt)).all()

    items: list[dict[str, object]] = []
    for slot, recruiter, city in rows:
        slot_tz = getattr(slot, "tz_name", None) or getattr(city, "tz", None) or getattr(recruiter, "tz", None) or DEFAULT_TZ
        recruiter_tz = getattr(recruiter, "tz", None) or slot_tz
        items.append(
            {
                "slot_id": int(slot.id),
                "start_utc": slot.start_utc.isoformat() if slot.start_utc else None,
                "city_id": slot.city_id,
                "city_name": city.name if city else None,
                "recruiter_id": recruiter.id if recruiter else None,
                "recruiter_name": recruiter.name if recruiter else None,
                "slot_tz": slot_tz,
                "recruiter_tz": recruiter_tz,
            }
        )

    return JSONResponse(
        {
            "ok": True,
            "items": items,
            "candidate_city_id": candidate_city_id,
        }
    )


@router.post("/candidates/{candidate_id}/schedule-slot")
async def api_schedule_slot(
    request: Request,
    candidate_id: int,
    _: None = Depends(require_csrf_token),
    principal: Principal = Depends(require_principal),
):
    """Schedule a slot for an existing candidate (JSON API)."""
    from backend.apps.admin_ui.services.slots import (
        assign_existing_candidate_slot_silent,
        schedule_manual_candidate_slot,
        schedule_manual_candidate_slot_silent,
        ManualSlotError,
    )
    from backend.apps.admin_ui.timezones import DEFAULT_TZ
    from backend.core.time_utils import ensure_aware_utc, parse_form_datetime
    from backend.domain.candidates.status_service import set_status_slot_pending
    from backend.domain.repositories import find_city_by_plain_name
    from backend.domain.slot_assignment_service import propose_alternative

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    slot_id: Optional[int] = None
    mode = str(data.get("mode") or "bot").strip().lower() or "bot"
    if mode not in {"bot", "manual_silent"}:
        return JSONResponse({"ok": False, "error": "invalid_mode"}, status_code=400)
    slot_raw = data.get("slot_id")
    if slot_raw not in (None, "", "null"):
        try:
            slot_id = int(slot_raw)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "invalid_slot_id"}, status_code=400)

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(status_code=404, detail={"message": "Кандидат не найден"})

        if principal.type == "recruiter" and user.responsible_recruiter_id != principal.id:
            rows = await session.execute(
                select(recruiter_city_association.c.city_id)
                .where(recruiter_city_association.c.recruiter_id == principal.id)
            )
            allowed_city_ids = {row[0] for row in rows}

            candidate_city_id = None
            if slot_id is not None:
                slot_city = await session.scalar(select(Slot.city_id).where(Slot.id == slot_id))
                candidate_city_id = int(slot_city) if slot_city is not None else None
            if candidate_city_id is None:
                candidate_city_raw = data.get("city_id")
                if candidate_city_raw is not None:
                    try:
                        candidate_city_id = int(candidate_city_raw)
                    except (TypeError, ValueError):
                        candidate_city_id = None
            if candidate_city_id is None and user.city:
                city_record = await find_city_by_plain_name(user.city)
                candidate_city_id = getattr(city_record, "id", None)
            if candidate_city_id is None:
                raise HTTPException(
                    status_code=409,
                    detail={"message": "У кандидата не указан город — назначение недоступно."},
                )
            if candidate_city_id not in allowed_city_ids:
                raise HTTPException(
                    status_code=403,
                    detail={"message": "Кандидат из другого города — назначение недоступно."},
                )

    candidate_tg_id = user.telegram_user_id or user.telegram_id
    if mode != "manual_silent" and not candidate_tg_id:
        return JSONResponse(
            {
                "ok": False,
                "error": "candidate_telegram_missing",
                "message": "У кандидата не привязан Telegram.",
            },
            status_code=400,
        )
    if not user.candidate_id:
        return JSONResponse({"ok": False, "error": "missing_candidate_id"}, status_code=409)

    selected_slot: Optional[Slot] = None
    recruiter = None
    city = None
    slot_tz = DEFAULT_TZ
    dt_utc: Optional[datetime] = None

    recruiter_id = data.get("recruiter_id")
    city_id = data.get("city_id")
    date_str = data.get("date")
    time_str = data.get("time")
    custom_message = data.get("custom_message")
    custom_message_text = custom_message.strip() if isinstance(custom_message, str) and custom_message.strip() else None

    if slot_id is not None:
        async with async_session() as session:
            selected_slot = await session.scalar(
                select(Slot)
                .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                .where(Slot.id == slot_id)
            )
            if selected_slot is None:
                return JSONResponse({"ok": False, "error": "slot_not_found"}, status_code=404)
            ensure_slot_scope(selected_slot, principal)
            if (getattr(selected_slot, "purpose", None) or "interview") != "interview":
                return JSONResponse({"ok": False, "error": "slot_not_interview"}, status_code=409)
            if norm_status(selected_slot.status) != "FREE":
                return JSONResponse({"ok": False, "error": "slot_not_free"}, status_code=409)

            recruiter = selected_slot.recruiter or await session.get(Recruiter, selected_slot.recruiter_id)
            city = selected_slot.city or (await session.get(City, selected_slot.city_id) if selected_slot.city_id else None)
            if recruiter is None:
                return JSONResponse({"ok": False, "error": "recruiter_not_found"}, status_code=404)
            if city is None:
                return JSONResponse({"ok": False, "error": "city_not_found"}, status_code=404)
            slot_tz = (
                getattr(selected_slot, "candidate_tz", None)
                or getattr(selected_slot, "tz_name", None)
                or getattr(city, "tz", None)
                or getattr(recruiter, "tz", None)
                or DEFAULT_TZ
            )
            dt_utc = ensure_aware_utc(selected_slot.start_utc)
    else:
        if not recruiter_id and principal.type == "recruiter":
            recruiter_id = principal.id
        if not recruiter_id or not city_id or not date_str or not time_str:
            return JSONResponse({"ok": False, "error": "missing_fields"}, status_code=400)

        async with async_session() as session:
            recruiter = await session.get(Recruiter, int(recruiter_id))
            city = await session.get(City, int(city_id))
        if recruiter is None:
            return JSONResponse({"ok": False, "error": "recruiter_not_found"}, status_code=404)
        if city is None:
            return JSONResponse({"ok": False, "error": "city_not_found"}, status_code=404)

        if principal.type == "recruiter" and recruiter.id != principal.id:
            return JSONResponse({"ok": False, "error": "permission_denied"}, status_code=403)

        settings = get_settings()
        recruiter_tz = getattr(recruiter, "tz", None) or settings.timezone or DEFAULT_TZ
        slot_tz = getattr(city, "tz", None) or recruiter_tz
        try:
            # Manual input is interpreted in recruiter local timezone.
            # Candidate timezone is stored separately on the slot/assignment.
            dt_utc = parse_form_datetime(f"{date_str}T{time_str}", recruiter_tz)
        except ValueError:
            return JSONResponse({"ok": False, "error": "invalid_datetime"}, status_code=400)

    if dt_utc is None:
        return JSONResponse({"ok": False, "error": "invalid_datetime"}, status_code=400)

    admin_username = request.session.get("username", "admin")
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    custom_message_sent = bool(custom_message_text)

    # If the candidate has an active reschedule request, reuse the existing slot assignment
    # instead of creating a new one (otherwise we block on "candidate_has_active_assignment").
    try:
        candidate_key = user.candidate_id
        assignment = None
        source_slot = None
        if mode != "manual_silent" and candidate_key:
            from backend.domain.models import (
                RescheduleRequest,
                RescheduleRequestStatus,
                SlotAssignmentStatus,
            )

            async with async_session() as session:
                assignment = await session.scalar(
                    select(SlotAssignment)
                    .join(
                        RescheduleRequest,
                        RescheduleRequest.slot_assignment_id == SlotAssignment.id,
                    )
                    .where(
                        SlotAssignment.candidate_id == candidate_key,
                        SlotAssignment.status == SlotAssignmentStatus.RESCHEDULE_REQUESTED,
                        RescheduleRequest.status == RescheduleRequestStatus.PENDING,
                    )
                    .order_by(SlotAssignment.updated_at.desc(), SlotAssignment.id.desc())
                )
                if assignment is not None:
                    source_slot = await session.get(Slot, assignment.slot_id)
                    if source_slot is None:
                        assignment = None

            if assignment is not None and source_slot is not None:
                if int(recruiter.id) != int(assignment.recruiter_id):
                    return JSONResponse(
                        {
                            "ok": False,
                            "error": "assignment_recruiter_mismatch",
                            "message": "Запрос переноса привязан к другому рекрутёру.",
                        },
                        status_code=409,
                    )
                if getattr(source_slot, "city_id", None) is not None and int(city.id) != int(source_slot.city_id):
                    return JSONResponse(
                        {
                            "ok": False,
                            "error": "assignment_city_mismatch",
                            "message": "Запрос переноса привязан к другому городу.",
                        },
                        status_code=409,
                    )

                result = await propose_alternative(
                    assignment_id=int(assignment.id),
                    decided_by_id=int(principal.id),
                    decided_by_type=str(principal.type),
                    new_start_utc=ensure_aware_utc(dt_utc),
                    comment=custom_message_text,
                )
                if not result.ok:
                    logger.warning(
                        "slot_assignment_route.failed",
                        extra={
                            "route": "/api/candidates/{candidate_id}/schedule-slot",
                            "slot_id": int(result.payload.get("slot_id") or 0)
                            if isinstance(result.payload, dict)
                            else None,
                            "candidate_id": candidate_id,
                            "error_code": result.status,
                            "status_code": result.status_code or 409,
                        },
                    )
                    return JSONResponse(
                        {
                            "ok": False,
                            "error": result.status,
                            "message": result.message or "Не удалось перенести слот.",
                        },
                        status_code=result.status_code or 409,
                    )
                try:
                    await set_status_slot_pending(candidate_tg_id)
                except Exception:
                    logger.exception(
                        "Failed to set SLOT_PENDING after reschedule propose",
                        extra={"candidate_id": candidate_id},
                    )
                return JSONResponse(
                    {
                        "ok": True,
                        "status": "pending_offer",
                        "message": "Предложение отправлено кандидату",
                        "slot_id": result.payload.get("slot_id") if isinstance(result.payload, dict) else None,
                        "slot_assignment_id": int(assignment.id),
                    },
                    status_code=201,
                )
    except Exception:
        logger.exception("schedule-slot: reschedule probe failed", extra={"candidate_id": candidate_id})
        return JSONResponse({"ok": False, "error": "reschedule_probe_failed"}, status_code=500)

    if selected_slot is not None and mode == "manual_silent":
        try:
            result = await assign_existing_candidate_slot_silent(
                slot_id=selected_slot.id,
                candidate=user,
                recruiter=recruiter,
                city=city,
                slot_tz=slot_tz,
                admin_username=admin_username,
                ip_address=ip_address,
                user_agent=user_agent,
                principal=principal,
            )
        except ManualSlotError as exc:
            return JSONResponse(
                {"ok": False, "error": "slot_conflict", "message": str(exc)},
                status_code=409,
            )
        return JSONResponse(
            {
                "ok": True,
                "status": result.status,
                "message": result.message,
                "slot_id": getattr(getattr(result, "slot", None), "id", None),
                "manual_mode": True,
            },
            status_code=201,
        )

    if selected_slot is not None:
        return await _assign_existing_slot_for_candidate(
            slot_id=selected_slot.id,
            candidate=user,
            principal=principal,
            route_label="/api/candidates/{candidate_id}/schedule-slot",
            created_by=admin_username,
        )

    try:
        if mode == "manual_silent":
            result = await schedule_manual_candidate_slot_silent(
                candidate=user,
                recruiter=recruiter,
                city=city,
                dt_utc=dt_utc,
                slot_tz=slot_tz,
                admin_username=admin_username,
                ip_address=ip_address,
                user_agent=user_agent,
                principal=principal,
            )
        else:
            result = await schedule_manual_candidate_slot(
                candidate=user,
                recruiter=recruiter,
                city=city,
                dt_utc=dt_utc,
                slot_tz=slot_tz,
                admin_username=admin_username,
                ip_address=ip_address,
                user_agent=user_agent,
                custom_message_sent=custom_message_sent,
                custom_message_text=custom_message_text,
                principal=principal,
            )
    except ManualSlotError as exc:
        logger.warning(
            "slot_assignment_route.failed",
            extra={
                "route": "/api/candidates/{candidate_id}/schedule-slot",
                "slot_id": None,
                "candidate_id": candidate_id,
                "error_code": "slot_conflict",
                "status_code": 409,
            },
        )
        return JSONResponse({"ok": False, "error": "slot_conflict", "message": str(exc)}, status_code=409)
    except Exception:
        logger.exception("schedule-slot: unexpected error", extra={"candidate_id": candidate_id})
        return JSONResponse({"ok": False, "error": "internal_error"}, status_code=500)

    # Ensure recruiter is linked to candidate after successful scheduling
    try:
        async with async_session() as session:
            db_user = await session.get(User, candidate_id)
            if db_user and db_user.responsible_recruiter_id != recruiter.id:
                db_user.responsible_recruiter_id = recruiter.id
                await session.commit()
    except Exception:
        logger.exception("Failed to assign responsible recruiter after scheduling slot", extra={"candidate_id": candidate_id})

    logger.info(
        "slot_assignment_route.succeeded",
        extra={
            "route": "/api/candidates/{candidate_id}/schedule-slot",
            "slot_id": None,
            "candidate_id": candidate_id,
            "error_code": None,
            "status_code": 201,
        },
    )
    return JSONResponse(
        {
            "ok": True,
            "status": result.status,
            "message": result.message or "Slot scheduled",
            "manual_mode": mode == "manual_silent",
        },
        status_code=201,
    )


@router.post("/candidates/{candidate_id}/schedule-intro-day")
async def api_schedule_intro_day(
    request: Request,
    candidate_id: int,
    _: None = Depends(require_csrf_token),
    principal: Principal = Depends(require_principal),
):
    """Schedule intro day for a candidate (JSON API)."""
    from backend.apps.admin_ui.services.candidates import (
        build_intro_day_template_context,
        get_candidate_detail,
        render_intro_day_invitation,
        resolve_intro_day_template_source,
    )
    from backend.apps.admin_ui.services.max_sales_handoff import (
        IntroDayHandoffContext,
        dispatch_intro_day_handoff_to_max,
    )
    from backend.apps.admin_ui.services.slots import recruiter_time_to_utc
    from backend.apps.admin_ui.timezones import DEFAULT_TZ
    from backend.domain.repositories import find_city_by_plain_name, add_outbox_notification
    from backend.domain.models import Slot, SlotStatus, DEFAULT_INTRO_DAY_DURATION_MIN
    from sqlalchemy.orm import selectinload

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        raise HTTPException(status_code=404, detail={"message": "Candidate not found"})

    user = detail["user"]
    candidate_tg_id = user.telegram_user_id or user.telegram_id
    if not candidate_tg_id:
        return JSONResponse(
            {
                "ok": False,
                "error": "missing_telegram",
                "message": "У кандидата нет Telegram ID",
            },
            status_code=400,
        )

    date_str = data.get("date")
    time_str = data.get("time")
    recruiter = None
    requested_recruiter_id: Optional[int] = None
    recruiter_raw = data.get("recruiter_id")
    if recruiter_raw not in (None, "", "null"):
        try:
            requested_recruiter_id = int(recruiter_raw)
        except (TypeError, ValueError):
            return JSONResponse(
                {
                    "ok": False,
                    "error": "invalid_recruiter",
                    "message": "Некорректный рекрутёр.",
                },
                status_code=400,
            )

    if not date_str or not time_str:
        return JSONResponse(
            {
                "ok": False,
                "error": "missing_datetime",
                "message": "Укажите дату и время ознакомительного дня",
            },
            status_code=400,
        )

    # Find city and recruiter
    city_record = None
    latest_slot = None
    if user.city:
        city_record = await find_city_by_plain_name(user.city)
        if city_record:
            async with async_session() as session:
                city_record = await session.get(
                    City,
                    city_record.id,
                    options=(selectinload(City.recruiters),),
                )

    if city_record is None:
        async with async_session() as session:
            latest_slot = await session.scalar(
                select(Slot)
                .where(
                    or_(
                        Slot.candidate_id == user.candidate_id,
                        Slot.candidate_tg_id == candidate_tg_id,
                    )
                )
                .order_by(Slot.start_utc.desc(), Slot.id.desc())
            )
            if latest_slot:
                fallback_city_id = latest_slot.candidate_city_id or latest_slot.city_id
                if fallback_city_id:
                    city_record = await session.get(
                        City,
                        fallback_city_id,
                        options=(selectinload(City.recruiters),),
                    )

    if not city_record:
        return JSONResponse(
            {
                "ok": False,
                "error": "city_not_found",
                "message": "Не удалось определить город кандидата. Укажите город в карточке кандидата.",
            },
            status_code=400,
        )

    if principal.type == "recruiter":
        # Recruiter can schedule intro day only for themselves.
        if requested_recruiter_id is not None and requested_recruiter_id != principal.id:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "permission_denied",
                    "message": "Недостаточно прав для назначения ознакомительного дня другому рекрутёру.",
                },
                status_code=403,
            )
        requested_recruiter_id = principal.id

    # Resolve recruiter: explicit payload/self → city FK → city M2M → user fallback
    if requested_recruiter_id is not None:
        async with async_session() as session:
            candidate_recruiter = await session.get(Recruiter, requested_recruiter_id)
            if candidate_recruiter is not None and getattr(candidate_recruiter, "active", True):
                recruiter = candidate_recruiter

    if getattr(city_record, "responsible_recruiter_id", None):
        if recruiter is None:
            async with async_session() as session:
                recruiter = await session.get(Recruiter, city_record.responsible_recruiter_id)

    if not recruiter and getattr(city_record, "recruiters", None):
        for rec in city_record.recruiters:
            if rec is not None and getattr(rec, "active", True):
                recruiter = rec
                break

    if not recruiter:
        async with async_session() as session:
            if user.responsible_recruiter_id:
                recruiter = await session.get(Recruiter, user.responsible_recruiter_id)
            if recruiter is None:
                if latest_slot is None:
                    latest_slot = await session.scalar(
                        select(Slot)
                        .where(
                            or_(
                                Slot.candidate_id == user.candidate_id,
                                Slot.candidate_tg_id == candidate_tg_id,
                            )
                        )
                        .order_by(Slot.start_utc.desc(), Slot.id.desc())
                    )
                if latest_slot and latest_slot.recruiter_id:
                    recruiter = await session.get(Recruiter, latest_slot.recruiter_id)

    if not recruiter:
        return JSONResponse(
            {
                "ok": False,
                "error": "no_recruiter_for_city",
                "message": "К городу не привязан ни один активный рекрутёр. Добавьте рекрутёра на странице города.",
            },
            status_code=400,
        )

    # Recruiter scoping
    if principal.type == "recruiter" and recruiter.id != principal.id:
        return JSONResponse(
            {
                "ok": False,
                "error": "permission_denied",
                "message": "Недостаточно прав для назначения ознакомительного дня другому рекрутёру.",
            },
            status_code=403,
        )

    slot_tz = getattr(city_record, "tz", None) or getattr(recruiter, "tz", None) or DEFAULT_TZ
    dt_utc = recruiter_time_to_utc(date_str, time_str, slot_tz)
    if not dt_utc:
        return JSONResponse(
            {
                "ok": False,
                "error": "invalid_datetime",
                "message": "Некорректная дата или время",
            },
            status_code=400,
        )

    custom_message = data.get("custom_message")
    custom_message = str(custom_message).strip() if custom_message else ""
    if not custom_message:
        template_source = await resolve_intro_day_template_source(city=city_record)
        template_context = build_intro_day_template_context(city_record)
        custom_message = render_intro_day_invitation(
            template_source,
            candidate_fio=user.fio or "Кандидат",
            date_str=str(date_str),
            time_str=str(time_str),
            **template_context,
        )

    candidate_telegram_ids = {
        value
        for value in (user.telegram_id, user.telegram_user_id, candidate_tg_id)
        if value is not None
    }
    old_interview_slot_ids: List[int] = []
    try:
        from backend.domain.slot_assignment_service import cancel_active_interview_slots_for_candidate

        cleanup_result = await cancel_active_interview_slots_for_candidate(
            candidate_id=user.candidate_id,
            candidate_tg_ids=candidate_telegram_ids,
            cancelled_by="superseded_by_intro_day",
        )
        old_interview_slot_ids = [int(slot_id) for slot_id in cleanup_result.get("slot_ids", [])]
    except Exception:
        logger.exception(
            "Failed to cancel active interview slots before intro day scheduling",
            extra={
                "candidate_id": candidate_id,
                "candidate_tg_id": candidate_tg_id,
            },
        )
        return JSONResponse(
            {
                "ok": False,
                "error": "active_slot_cleanup_failed",
                "message": "Не удалось перенести кандидата в ознакомительный день. Повторите попытку.",
            },
            status_code=409,
        )

    async with async_session() as session:
        # Create slot
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city_record.id,
            candidate_city_id=city_record.id,
            purpose="intro_day",
            tz_name=slot_tz,
            start_utc=dt_utc,
            duration_min=DEFAULT_INTRO_DAY_DURATION_MIN,
            status=SlotStatus.BOOKED,
            candidate_id=user.candidate_id,
            candidate_tg_id=candidate_tg_id,
            candidate_fio=user.fio,
            candidate_tz=slot_tz,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        if old_interview_slot_ids:
            from backend.apps.bot.services import cancel_slot_reminders

            for old_slot_id in old_interview_slot_ids:
                try:
                    await cancel_slot_reminders(old_slot_id)
                except Exception:
                    logger.warning(
                        "Failed to cancel interview reminders when intro day is scheduled: %s",
                        old_slot_id,
                    )

        # Update candidate status
        try:
            from backend.domain.candidates.status_service import set_status_intro_day_scheduled
            await set_status_intro_day_scheduled(candidate_tg_id, force=True)
        except Exception:
            pass

        # Add notification
        try:
            payload = {}
            if custom_message:
                payload["custom_message"] = custom_message

            await add_outbox_notification(
                notification_type="intro_day_invitation",
                booking_id=slot.id,
                candidate_tg_id=candidate_tg_id,
                payload=payload,
            )
        except Exception as exc:
            logger.warning("Failed to enqueue intro day notification: %s", exc)

        # Schedule reminders
        try:
            from backend.apps.bot.reminders import get_reminder_service
            reminder_service = get_reminder_service()
            await reminder_service.schedule_for_slot(slot.id, skip_confirmation_prompts=False)
        except Exception as exc:
            logger.warning("Failed to schedule reminders for intro day: %s", exc)

    hh_profile_url = None
    hh_resume_id = (getattr(user, "hh_resume_id", None) or "").strip()
    if hh_resume_id:
        hh_profile_url = f"https://hh.ru/resume/{hh_resume_id}"

    base_url = str(request.base_url).rstrip("/")
    candidate_card_url = f"{base_url}/app/candidates/{candidate_id}" if base_url else None
    max_handoff: dict[str, object]
    try:
        max_handoff = await dispatch_intro_day_handoff_to_max(
            IntroDayHandoffContext(
                candidate_id=user.id,
                candidate_fio=user.fio or f"Кандидат #{user.id}",
                slot_id=slot.id,
                slot_start_utc=slot.start_utc,
                slot_tz=slot_tz,
                recruiter_id=getattr(recruiter, "id", None),
                recruiter_name=getattr(recruiter, "name", None),
                city_id=getattr(city_record, "id", None),
                city_name=getattr(city_record, "name", None),
                candidate_card_url=candidate_card_url,
                hh_profile_url=hh_profile_url,
            ),
            bot=getattr(request.app.state, "bot", None),
        )
    except Exception:
        logger.exception(
            "Failed to dispatch intro day handoff to Max",
            extra={"candidate_id": candidate_id, "slot_id": slot.id},
        )
        max_handoff = {"ok": False, "status": "error"}

    return JSONResponse({
        "ok": True,
        "slot_id": slot.id,
        "message": "Intro day scheduled",
        "max_handoff": max_handoff,
    })


# ---------------------------------------------------------------------------
# Vacancies API
# ---------------------------------------------------------------------------

@router.get("/vacancies")
async def api_list_vacancies(
    request: Request,
    city_id: Optional[int] = None,
) -> JSONResponse:
    _ = await require_principal(request)
    from backend.apps.admin_ui.services.vacancies import list_vacancies

    summaries = await list_vacancies(city_id=city_id)
    return JSONResponse({
        "ok": True,
        "vacancies": [
            {
                "id": v.id,
                "title": v.title,
                "slug": v.slug,
                "city_id": v.city_id,
                "city_name": v.city_name,
                "is_active": v.is_active,
                "description": v.description,
                "test1_question_count": v.test1_question_count,
                "test2_question_count": v.test2_question_count,
                "created_at": v.created_at.isoformat(),
                "updated_at": v.updated_at.isoformat(),
            }
            for v in summaries
        ],
    })


@router.post("/vacancies")
async def api_create_vacancy(request: Request) -> JSONResponse:
    _ = await require_csrf_token(request)
    data = await request.json()
    from backend.apps.admin_ui.services.vacancies import create_vacancy

    city_id_raw = data.get("city_id")
    city_id: Optional[int] = None
    if city_id_raw not in (None, "", "null"):
        try:
            city_id = int(city_id_raw)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "errors": ["city_id: некорректное значение"]}, status_code=400)

    ok, errors, vacancy = await create_vacancy(
        title=str(data.get("title") or ""),
        slug=str(data.get("slug") or ""),
        city_id=city_id,
        description=data.get("description") or None,
        is_active=bool(data.get("is_active", True)),
    )
    if not ok:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    return JSONResponse({"ok": True, "id": vacancy.id})


@router.put("/vacancies/{vacancy_id}")
async def api_update_vacancy(request: Request, vacancy_id: int) -> JSONResponse:
    _ = await require_csrf_token(request)
    data = await request.json()
    from backend.apps.admin_ui.services.vacancies import update_vacancy

    city_id_raw = data.get("city_id")
    city_id: Optional[int] = None
    if city_id_raw is not None:
        if city_id_raw in ("", "null", 0):
            city_id = -1  # clear
        else:
            try:
                city_id = int(city_id_raw)
            except (TypeError, ValueError):
                return JSONResponse({"ok": False, "errors": ["city_id: некорректное значение"]}, status_code=400)

    ok, errors, vacancy = await update_vacancy(
        vacancy_id,
        title=data.get("title"),
        slug=data.get("slug"),
        city_id=city_id,
        description=data.get("description"),
        is_active=data.get("is_active"),
    )
    if not ok:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    return JSONResponse({"ok": True, "id": vacancy.id})


@router.delete("/vacancies/{vacancy_id}")
async def api_delete_vacancy(request: Request, vacancy_id: int) -> JSONResponse:
    _ = await require_csrf_token(request)
    from backend.apps.admin_ui.services.vacancies import delete_vacancy

    deleted = await delete_vacancy(vacancy_id)
    if not deleted:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return JSONResponse({"ok": True})


@router.get("/vacancies/{vacancy_id}/questions/{test_id}")
async def api_get_vacancy_questions(
    request: Request,
    vacancy_id: int,
    test_id: str,
) -> JSONResponse:
    _ = await require_principal(request)
    from backend.apps.admin_ui.services.vacancies import get_vacancy, get_vacancy_questions

    vacancy = await get_vacancy(vacancy_id)
    if vacancy is None:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)

    questions = await get_vacancy_questions(vacancy_id, test_id)
    return JSONResponse({
        "ok": True,
        "vacancy_id": vacancy_id,
        "test_id": test_id,
        "questions": [
            {
                "id": q.id,
                "question_index": q.question_index,
                "title": q.title,
                "payload": q.payload,
                "is_active": q.is_active,
            }
            for q in questions
        ],
    })
