from datetime import date as date_type, datetime, time, timezone, timedelta
from pathlib import Path
from typing import Optional, List
from zoneinfo import ZoneInfo
import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile, File, Form
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.cities import (
    api_city_owners_payload,
    list_cities,
    get_city,
    create_city,
    update_city_settings,
    city_experts_items,
    delete_city,
)
from backend.apps.admin_ui.services.dashboard import (
    dashboard_counts,
    get_bot_funnel_stats,
    get_recruiter_leaderboard,
    get_waiting_candidates,
)
from backend.apps.admin_ui.services.dashboard_calendar import (
    dashboard_calendar_snapshot,
)
from backend.apps.admin_ui.services.calendar_events import (
    get_calendar_events,
)
from backend.apps.admin_ui.services.candidates import (
    get_candidate_detail,
    api_candidate_detail_payload,
    assign_candidate_recruiter,
    update_candidate_status,
    list_candidates,
)
from backend.apps.admin_ui.services.chat import (
    list_chat_history,
    retry_chat_message,
    send_chat_message,
)
from backend.apps.admin_ui.services.slots import execute_bot_dispatch
from backend.apps.admin_ui.services.slots import (
    approve_slot_booking,
    reject_slot_booking,
    reschedule_slot_booking,
    set_slot_outcome,
    delete_slot,
)
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.recruiters import (
    api_recruiters_payload,
    api_get_recruiter,
    create_recruiter,
    delete_recruiter,
    update_recruiter,
    reset_recruiter_password,
)
from backend.apps.admin_ui.services.slots.core import api_slots_payload, bulk_delete_slots, bulk_schedule_reminders
from backend.apps.admin_ui.services.message_templates_presets import (
    list_known_template_keys,
    known_template_presets,
)
from backend.apps.admin_ui.services.kpis import (
    get_weekly_kpis,
    list_weekly_history,
)
from backend.core.audit import log_audit_action
from backend.apps.admin_ui.perf.cache import keys as cache_keys
from backend.apps.admin_ui.perf.cache.readthrough import get_cached, get_or_compute
from backend.apps.admin_ui.services.message_templates import (
    list_message_templates,
    create_message_template,
    update_message_template,
    delete_message_template,
    get_template_history,
)
from backend.apps.admin_ui.services.staff_chat import (
    list_threads as staff_list_threads,
    create_or_get_direct_thread,
    create_group_thread,
    list_messages as staff_list_messages,
    send_message as staff_send_message,
    mark_read as staff_mark_read,
    get_attachment as staff_get_attachment,
    list_thread_members as staff_list_thread_members,
    add_thread_members as staff_add_thread_members,
    remove_thread_member as staff_remove_thread_member,
    wait_for_thread_updates as staff_wait_thread_updates,
    wait_for_message_updates as staff_wait_message_updates,
    send_candidate_task as staff_send_candidate_task,
    decide_candidate_task as staff_decide_candidate_task,
)
from backend.apps.admin_ui.services.recruiter_plan import (
    get_recruiter_plan,
    add_recruiter_plan_entry,
    delete_recruiter_plan_entry,
)
from backend.apps.admin_ui.services.questions import (
    list_test_questions,
    get_test_question_detail,
    update_test_question,
    create_test_question,
    clone_test_question,
)
from backend.core.db import async_session
from backend.domain.models import Recruiter, Slot, City, SlotStatus, SlotAssignment, ActionToken, MessageTemplate, recruiter_city_association
from backend.domain.candidates.models import User
from backend.apps.admin_ui.utils import parse_optional_int, status_filter, recruiter_time_to_utc, norm_status
from backend.core.guards import ensure_slot_scope
from backend.apps.admin_ui.security import require_csrf_token, require_principal, require_admin, Principal
from starlette_wtf import csrf_token
from backend.domain.errors import CityAlreadyExistsError
from backend.core.settings import get_settings
from backend.core.sanitizers import sanitize_plain_text
from backend.apps.bot.reminders import get_reminder_service
from backend.apps.bot.runtime_config import (
    get_reminder_policy_config,
    save_reminder_policy_config,
)
from backend.apps.admin_ui.timezones import timezone_options

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger(__name__)


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


def _avatar_dir() -> Path:
    settings = get_settings()
    base_dir = Path(settings.data_dir).resolve()
    avatar_dir = base_dir / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    return avatar_dir


def _avatar_prefix(principal: Principal) -> str:
    return f"{principal.type}_{principal.id}"


def _find_avatar_file(prefix: str) -> Optional[Path]:
    avatar_dir = _avatar_dir()
    for ext in ("png", "jpg", "jpeg", "webp"):
        candidate = avatar_dir / f"{prefix}.{ext}"
        if candidate.exists():
            return candidate
    matches = list(avatar_dir.glob(f"{prefix}.*"))
    return matches[0] if matches else None


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
            ttl_seconds=2.0,
            stale_seconds=10.0,
        )
        if cached_payload is not None and isinstance(cached_payload[0], dict):
            return JSONResponse(cached_payload[0])
        return JSONResponse({"status": "degraded", "reason": "database_unavailable"}, status_code=503)

    return JSONResponse(await dashboard_counts(principal=principal))


@router.get("/dashboard/incoming")
async def api_dashboard_incoming(
    request: Request,
    limit: int = Query(default=6, ge=1, le=500),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    """Candidates who passed test1 and are waiting for a free interview slot."""
    if not getattr(request.app.state, "db_available", True):
        cache_key = cache_keys.dashboard_incoming(principal=principal, limit=limit).value
        cached_payload = await get_cached(
            cache_key,
            expected_type=list,
            ttl_seconds=2.0,
            stale_seconds=10.0,
        )
        if cached_payload is not None and isinstance(cached_payload[0], list):
            return JSONResponse({"items": cached_payload[0]})
        return JSONResponse({"status": "degraded", "reason": "database_unavailable"}, status_code=503)

    payload = await get_waiting_candidates(limit=limit, principal=principal)
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


async def _profile_snapshot(principal: Principal, request: Request) -> tuple[dict, Optional[dict]]:
    recruiter = None
    city_names: list[str] = []
    candidate_count = 0
    slot_count = 0
    city_count = 0
    recruiter_count = 0
    slots_by_status: dict[str, int] = {}
    upcoming_global: list[dict] = []
    health: dict[str, Optional[str | bool]] = {}
    today_meetings: list[dict] = []
    upcoming_meetings: list[dict] = []
    active_candidates: list[dict] = []
    reminders: list[dict] = []
    tzinfo: Optional[ZoneInfo] = None
    planner_days: list[dict] = []
    city_options: list[dict] = []

    pending_count = 0
    booked_count = 0
    nearest_minutes: Optional[int] = None
    avg_lead_hours: Optional[float] = None
    recruiter_payload: Optional[dict] = None
    now_utc = datetime.now(timezone.utc)

    async with async_session() as session:
        if principal.type == "recruiter":
            recruiter = await session.get(Recruiter, principal.id)
            if recruiter and recruiter.tz:
                try:
                    tzinfo = ZoneInfo(recruiter.tz)
                except Exception:
                    tzinfo = ZoneInfo("UTC")
            else:
                tzinfo = ZoneInfo("UTC")

            candidate_count = await session.scalar(
                select(func.count()).select_from(User).where(User.responsible_recruiter_id == principal.id)
            ) or 0
            slot_count = await session.scalar(
                select(func.count()).select_from(Slot).where(Slot.recruiter_id == principal.id)
            ) or 0
            city_rows = await session.execute(
                select(City.id, City.name, City.tz)
                .join(recruiter_city_association, recruiter_city_association.c.city_id == City.id)
                .where(recruiter_city_association.c.recruiter_id == principal.id)
                .order_by(City.name.asc())
            )
            for cid, cname, ctz in city_rows:
                city_names.append(cname)
                city_options.append({"id": cid, "name": cname, "tz": ctz})

            slot_rows = await session.execute(
                select(Slot.id, Slot.status, Slot.start_utc, Slot.city_id)
                .where(Slot.recruiter_id == principal.id)
                .order_by(Slot.start_utc.asc(), Slot.id.asc())
                .limit(10)
            )
            slots = slot_rows.all()
            for slot_id, slot_status, slot_start_utc, slot_city_id in slots:
                start_utc = slot_start_utc
                if start_utc and start_utc.tzinfo is None:
                    start_utc = start_utc.replace(tzinfo=timezone.utc)
                status_value = slot_status.name if hasattr(slot_status, "name") else slot_status
                item = {
                    "id": slot_id,
                    "status": status_value,
                    "start_utc": start_utc.isoformat() if start_utc else None,
                    "city_id": slot_city_id,
                }
                if start_utc:
                    minutes = int((start_utc - now_utc).total_seconds() / 60)
                    if minutes > 0:
                        nearest_minutes = minutes if nearest_minutes is None else min(nearest_minutes, minutes)
                start_local_date = start_utc.astimezone(tzinfo).date() if start_utc else None
                if start_local_date and start_local_date == now_utc.astimezone(tzinfo).date():
                    today_meetings.append(item)
                else:
                    upcoming_meetings.append(item)

            # planner for 7 days
            planner_rows = await session.execute(
                select(Slot.id, Slot.status, Slot.start_utc, Slot.city_id)
                .where(
                    Slot.recruiter_id == principal.id,
                    Slot.start_utc >= now_utc,
                    Slot.start_utc <= now_utc + timedelta(days=7),
                )
                .order_by(Slot.start_utc.asc(), Slot.id.asc())
            )
            planner_items = planner_rows.all()
            day_map: dict[str, list[dict]] = {}
            for slot_id, slot_status, slot_start_utc, slot_city_id in planner_items:
                start_utc = slot_start_utc
                if start_utc and start_utc.tzinfo is None:
                    start_utc = start_utc.replace(tzinfo=timezone.utc)
                local = start_utc.astimezone(tzinfo) if start_utc else None
                day_key = local.strftime("%Y-%m-%d") if local else "unknown"
                payload = {
                    "id": slot_id,
                    "time": local.strftime("%H:%M") if local else "",
                    "status": slot_status.name if hasattr(slot_status, "name") else slot_status,
                    "city": slot_city_id,
                }
                day_map.setdefault(day_key, []).append(payload)
            for day, items in sorted(day_map.items()):
                planner_days.append({"date": day, "entries": items})

            if planner_items:
                deltas: list[float] = []
                for _, _, slot_start_utc, _ in planner_items:
                    start_utc = slot_start_utc
                    if start_utc and start_utc.tzinfo is None:
                        start_utc = start_utc.replace(tzinfo=timezone.utc)
                    if start_utc and start_utc > now_utc:
                        deltas.append((start_utc - now_utc).total_seconds() / 3600)
                if deltas:
                    avg_lead_hours = round(sum(deltas) / len(deltas), 1)

            cand_rows = await session.execute(
                select(User)
                .where(User.responsible_recruiter_id == principal.id)
                .order_by(User.id.desc())
                .limit(6)
            )
            for u in cand_rows.scalars().all():
                active_candidates.append(
                    {
                        "id": u.id,
                        "name": u.fio or u.telegram_username or f"Кандидат {u.id}",
                        "city": u.city,
                        "status": getattr(u, "status", None) or getattr(u, "candidate_status", None),
                    }
                )
        else:
            candidate_count = await session.scalar(select(func.count()).select_from(User)) or 0
            slot_count = await session.scalar(select(func.count()).select_from(Slot)) or 0
            recruiter_count = await session.scalar(select(func.count()).select_from(Recruiter)) or 0
            city_count = await session.scalar(select(func.count()).select_from(City)) or 0

            status_rows = await session.execute(
                select(Slot.status, func.count()).group_by(Slot.status)
            )
            for status, cnt in status_rows:
                slots_by_status[str(status).lower()] = cnt

            global_slots = await session.execute(
                select(Slot.id, Slot.status, Slot.start_utc, Slot.city_id, Slot.recruiter_id)
                .where(Slot.start_utc >= now_utc)
                .order_by(Slot.start_utc.asc(), Slot.id.asc())
                .limit(8)
            )
            for slot_id, slot_status, slot_start_utc, slot_city_id, slot_recruiter_id in global_slots:
                upcoming_global.append(
                    {
                        "id": slot_id,
                        "status": slot_status.name if hasattr(slot_status, "name") else slot_status,
                        "start_utc": slot_start_utc.isoformat() if slot_start_utc else None,
                        "city_id": slot_city_id,
                        "recruiter_id": slot_recruiter_id,
                    }
                )

            app_state = getattr(request, "app", None) and getattr(request.app, "state", None)
            if app_state:
                health = {
                    "db": getattr(app_state, "db_available", None),
                    "redis": getattr(app_state, "redis_available", None),
                    "cache": getattr(app_state, "cache_status", None),
                    "bot": getattr(app_state, "bot_enabled", None),
                    "notifications": getattr(app_state, "notification_broker_available", None),
                }

        if principal.type == "recruiter" and recruiter is not None:
            recruiter_payload = {
                "id": recruiter.id,
                "name": recruiter.name,
                "tz": recruiter.tz,
                "active": recruiter.active,
                "cities": [{"id": c.get("id"), "name": c.get("name")} for c in city_options],
            }

    pending_count = len([m for m in today_meetings + upcoming_meetings if str(m.get("status")).upper() in {"PENDING"}])
    booked_count = len([m for m in today_meetings + upcoming_meetings if str(m.get("status")).upper() in {"BOOKED"}])
    if pending_count:
        reminders.append({"title": f"Подтвердите {pending_count} бронирований", "when": "как можно скорее"})
    if booked_count:
        reminders.append({"title": f"Проверьте {booked_count} слота со статусом BOOKED", "when": "до ближайшего времени"})

    try:
        reminder_service = get_reminder_service()
    except Exception:
        reminder_service = None
    if reminder_service:
        try:
            snapshot = reminder_service.stats()
            if snapshot.get("reminders", 0):
                reminders.append({"title": f"Активных напоминаний: {snapshot.get('reminders')}", "when": "в очереди"})
            if snapshot.get("confirm_prompts", 0):
                reminders.append({"title": f"Запросов подтверждения: {snapshot.get('confirm_prompts')}", "when": "в очереди"})
        except Exception:
            pass

    total_slots = len(today_meetings) + len(upcoming_meetings)
    conversion = 0
    if total_slots:
        conversion = round(
            (len([m for m in today_meetings + upcoming_meetings if str(m.get("status")).upper() in {"BOOKED", "CONFIRMED_BY_CANDIDATE"}]) / total_slots)
            * 100
        )

    return {
        "candidate_count": candidate_count,
        "slot_count": slot_count,
        "city_count": city_count,
        "recruiter_count": recruiter_count,
        "city_names": city_names,
        "today_meetings": today_meetings,
        "upcoming_meetings": upcoming_meetings,
        "active_candidates": active_candidates,
        "reminders": reminders,
        "planner_days": planner_days,
        "city_options": city_options,
        "admin_stats": {
            "slots_by_status": slots_by_status,
            "upcoming_global": upcoming_global,
            "health": health,
        },
        "kpi": {
            "today": len(today_meetings),
            "upcoming": len(upcoming_meetings),
            "pending": pending_count,
            "conversion": conversion,
            "nearest_minutes": nearest_minutes,
            "avg_lead_hours": avg_lead_hours,
        },
    }, recruiter_payload


@router.get("/profile")
async def api_profile(request: Request, principal: Principal = Depends(require_principal)):
    cache_key = cache_keys.profile_payload(principal=principal).value
    if not getattr(request.app.state, "db_available", True):
        snapshot = await get_cached(
            cache_key,
            expected_type=dict,
            ttl_seconds=2.0,
            stale_seconds=10.0,
        )
        if snapshot is None:
            return JSONResponse({"status": "degraded", "reason": "database_unavailable"}, status_code=503)
        snapshot = snapshot[0]
    else:
        async def _compute() -> dict:
            stats = await dashboard_counts(principal=principal)
            profile_payload, recruiter_payload = await _profile_snapshot(principal, request)
            return {
                "recruiter": recruiter_payload,
                "stats": stats,
                "profile": profile_payload,
            }

        snapshot = await get_or_compute(
            cache_key,
            expected_type=dict,
            ttl_seconds=2.0,
            stale_seconds=10.0,
            compute=_compute,
        )

    avatar_file = _find_avatar_file(_avatar_prefix(principal))
    avatar_url = None
    if avatar_file is not None:
        avatar_url = f"/api/profile/avatar?v={int(avatar_file.stat().st_mtime)}"
    return JSONResponse(
        {
            "principal": {"type": principal.type, "id": principal.id},
            **snapshot,
            "avatar_url": avatar_url,
        }
    )


@router.get("/profile/avatar")
async def api_profile_avatar(principal: Principal = Depends(require_principal)) -> FileResponse:
    avatar_file = _find_avatar_file(_avatar_prefix(principal))
    if avatar_file is None:
        raise HTTPException(status_code=404, detail={"message": "Аватар не найден"})
    return FileResponse(avatar_file)


@router.post("/profile/avatar")
async def api_profile_avatar_upload(
    request: Request,
    file: UploadFile = File(...),
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail={"message": "Можно загрузить только изображение"})
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail={"message": "Файл слишком большой (до 5 МБ)"})

    ext = "png"
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
    elif file.content_type and "/" in file.content_type:
        ext = file.content_type.split("/", 1)[-1].lower()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        ext = "png"

    avatar_dir = _avatar_dir()
    prefix = _avatar_prefix(principal)
    for existing in avatar_dir.glob(f"{prefix}.*"):
        try:
            existing.unlink()
        except Exception:
            pass
    file_path = avatar_dir / f"{prefix}.{ext}"
    file_path.write_bytes(content)
    return JSONResponse({"ok": True, "url": f"/api/profile/avatar?v={int(file_path.stat().st_mtime)}"})


@router.delete("/profile/avatar")
async def api_profile_avatar_delete(
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    avatar_dir = _avatar_dir()
    prefix = _avatar_prefix(principal)
    removed = False
    for existing in avatar_dir.glob(f"{prefix}.*"):
        try:
            existing.unlink()
            removed = True
        except Exception:
            pass
    return JSONResponse({"ok": True, "removed": removed})


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


@router.get("/staff/threads")
async def api_staff_threads(principal: Principal = Depends(require_principal)) -> JSONResponse:
    return JSONResponse(await staff_list_threads(principal))


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
    )
    return JSONResponse({"ok": True, **result})


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


@router.get("/recruiters")
async def api_recruiters(principal: Principal = Depends(require_principal)):
    if principal.type == "recruiter":
        payload = await api_get_recruiter(principal.id)
        return JSONResponse([payload] if payload else [])
    return JSONResponse(await api_recruiters_payload())


@router.get("/recruiters/{recruiter_id}")
async def api_recruiter_detail(
    recruiter_id: int,
    _: Principal = Depends(require_admin),
):
    payload = await api_get_recruiter(recruiter_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Recruiter not found")
    return JSONResponse(payload)


@router.post("/recruiters", status_code=201)
async def api_create_recruiter(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    payload = {
        "name": sanitize_plain_text(str(data.get("name") or "")),
        "tz": data.get("tz") or "Europe/Moscow",
        "telemost_url": data.get("telemost") or data.get("telemost_url") or "",
        "tg_chat_id": data.get("tg_chat_id"),
        "active": bool(data.get("active", True)),
    }
    city_ids = data.get("city_ids") or []
    if not isinstance(city_ids, list):
        city_ids = []

    result = await create_recruiter(payload, cities=[str(cid) for cid in city_ids])
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)

    result["city_ids"] = [int(cid) for cid in city_ids]
    recruiter_id = result.get("recruiter_id")
    result["id"] = recruiter_id
    result["name"] = payload["name"]
    result["tz"] = payload["tz"]
    result["tg_chat_id"] = payload["tg_chat_id"]
    result["active"] = payload["active"]
    headers = {}
    if recruiter_id:
        headers["Location"] = f"/api/recruiters/{recruiter_id}"
    return JSONResponse(result, status_code=201, headers=headers)


@router.put("/recruiters/{recruiter_id}")
async def api_update_recruiter(
    recruiter_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    payload = {
        "name": sanitize_plain_text(str(data.get("name") or "")),
        "tz": data.get("tz") or "Europe/Moscow",
        "telemost_url": data.get("telemost") or data.get("telemost_url") or "",
        "tg_chat_id": data.get("tg_chat_id"),
        "active": bool(data.get("active", True)),
    }
    city_ids = data.get("city_ids") or []
    if not isinstance(city_ids, list):
        city_ids = []

    result = await update_recruiter(recruiter_id, payload, cities=[str(cid) for cid in city_ids])
    if not result.get("ok"):
        status_code = 404 if result.get("error", {}).get("type") == "not_found" else 400
        return JSONResponse(result, status_code=status_code)

    result["city_ids"] = [int(cid) for cid in city_ids]
    result["id"] = recruiter_id
    result["name"] = payload["name"]
    result["tz"] = payload["tz"]
    result["tg_chat_id"] = payload["tg_chat_id"]
    result["active"] = payload["active"]
    return JSONResponse(result, status_code=200)


@router.post("/recruiters/{recruiter_id}/reset-password")
async def api_reset_recruiter_password(
    recruiter_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    result = await reset_recruiter_password(recruiter_id)
    if not result.get("ok"):
        status_code = 404 if result.get("error", {}).get("type") == "not_found" else 400
        return JSONResponse(result, status_code=status_code)
    return JSONResponse(result, status_code=200)


@router.get("/cities")
async def api_cities(principal: Principal = Depends(require_principal)):
    cities = await list_cities(principal=principal)
    payload = []
    for city in cities:
        primary = city.recruiters[0] if getattr(city, "recruiters", None) else None
        payload.append(
            {
                "id": city.id,
                "name": getattr(city, "name_plain", city.name),
                "tz": getattr(city, "tz", None),
                "active": getattr(city, "active", True),
                "owner_recruiter_id": primary.id if primary else None,
                "criteria": getattr(city, "criteria", None),
                "experts": getattr(city, "experts", None),
                "experts_items": city_experts_items(city, include_inactive=False),
                "plan_week": getattr(city, "plan_week", None),
                "plan_month": getattr(city, "plan_month", None),
                "intro_address": getattr(city, "intro_address", None),
                "contact_name": getattr(city, "contact_name", None),
                "contact_phone": getattr(city, "contact_phone", None),
                "recruiter_ids": [rec.id for rec in getattr(city, "recruiters", [])],
                "recruiters": [
                    {"id": rec.id, "name": getattr(rec, "name", None) or f"Рекрутер {rec.id}"}
                    for rec in getattr(city, "recruiters", [])
                ],
            }
        )
    return JSONResponse(payload)


@router.get("/cities/{city_id}")
async def api_city_detail(
    city_id: int,
    _: Principal = Depends(require_admin),
):
    city = await get_city(city_id)
    if city is None:
        raise HTTPException(status_code=404, detail="City not found")
    primary = city.recruiters[0] if getattr(city, "recruiters", None) else None
    payload = {
        "id": city.id,
        "name": getattr(city, "name_plain", city.name),
        "tz": getattr(city, "tz", None),
        "active": getattr(city, "active", True),
        "owner_recruiter_id": primary.id if primary else None,
        "criteria": getattr(city, "criteria", None),
        "experts": getattr(city, "experts", None),
        "experts_items": city_experts_items(city, include_inactive=True),
        "plan_week": getattr(city, "plan_week", None),
        "plan_month": getattr(city, "plan_month", None),
        "intro_address": getattr(city, "intro_address", None),
        "contact_name": getattr(city, "contact_name", None),
        "contact_phone": getattr(city, "contact_phone", None),
        "recruiter_ids": [rec.id for rec in getattr(city, "recruiters", [])],
    }
    return JSONResponse(payload)


@router.post("/cities", status_code=201)
async def api_create_city(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    try:
        recruiter_ids_raw = data.get("recruiter_ids")
        recruiter_ids: Optional[List[int]] = None
        if recruiter_ids_raw is not None:
            recruiter_ids = []
            if isinstance(recruiter_ids_raw, list):
                for raw in recruiter_ids_raw:
                    try:
                        recruiter_ids.append(int(raw))
                    except (TypeError, ValueError):
                        continue

        city = await create_city(
            name=str(data.get("name") or ""),
            tz=str(data.get("tz") or "Europe/Moscow"),
            recruiter_ids=recruiter_ids,
        )
        if city is not None:
            # Persist the rest of the city settings (frontend sends full payload on create).
            error, _, _ = await update_city_settings(
                city.id,
                name=data.get("name"),
                recruiter_ids=recruiter_ids,
                responsible_id=None,
                criteria=data.get("criteria"),
                experts=data.get("experts"),
                experts_items=data.get("experts_items"),
                plan_week=data.get("plan_week"),
                plan_month=data.get("plan_month"),
                tz=data.get("tz"),
                active=data.get("active"),
                intro_address=data.get("intro_address"),
                contact_name=data.get("contact_name"),
                contact_phone=data.get("contact_phone"),
            )
            if error:
                return JSONResponse({"ok": False, "error": error}, status_code=400)
    except CityAlreadyExistsError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True}, status_code=201)


@router.put("/cities/{city_id}")
async def api_update_city(
    city_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    recruiter_ids = data.get("recruiter_ids")
    if recruiter_ids is not None and not isinstance(recruiter_ids, list):
        recruiter_ids = []
    error, city, recruiter = await update_city_settings(
        city_id,
        name=data.get("name"),
        recruiter_ids=recruiter_ids,
        responsible_id=None,
        criteria=data.get("criteria"),
        experts=data.get("experts"),
        experts_items=data.get("experts_items"),
        plan_week=data.get("plan_week"),
        plan_month=data.get("plan_month"),
        tz=data.get("tz"),
        active=data.get("active"),
        intro_address=data.get("intro_address"),
        contact_name=data.get("contact_name"),
        contact_phone=data.get("contact_phone"),
    )
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse(
        {
            "ok": True,
            "id": city.id if city else None,
            "owner_recruiter_id": recruiter.id if recruiter else None,
        }
    )


@router.delete("/cities/{city_id}")
async def api_delete_city(
    city_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    ok = await delete_city(city_id)
    if not ok:
        raise HTTPException(status_code=404, detail="City not found")
    return JSONResponse({"ok": True})


@router.delete("/recruiters/{recruiter_id}")
async def api_delete_recruiter(
    recruiter_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    payload = await api_get_recruiter(recruiter_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Recruiter not found")
    await delete_recruiter(recruiter_id)
    return JSONResponse({"ok": True})


@router.get("/slots")
async def api_slots(
    recruiter_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_principal),
):
    recruiter = parse_optional_int(recruiter_id)
    if principal.type == "recruiter":
        recruiter = principal.id
    status_norm = status_filter(status)
    payload = await api_slots_payload(recruiter, status_norm, limit)
    return JSONResponse(payload)


class SlotOutcomePayload(BaseModel):
    outcome: str


class SlotBookPayload(BaseModel):
    candidate_tg_id: int
    candidate_fio: Optional[str] = None


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

        slot.start_utc = dt_utc
        slot.status = SlotStatus.PENDING

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
        assignment = await session.scalar(
            select(SlotAssignment)
            .where(SlotAssignment.candidate_id == candidate_id)
            .where(SlotAssignment.status.in_(active_statuses))
        )
        if assignment is None:
            assignment = SlotAssignment(
                slot_id=slot.id,
                recruiter_id=slot.recruiter_id,
                candidate_id=candidate_id,
                candidate_tg_id=candidate_tg_id,
                candidate_tz=getattr(slot, "candidate_tz", None) or slot_tz,
                status="offered",
                offered_at=now,
            )
            session.add(assignment)
            await session.flush()
        else:
            assignment.slot_id = slot.id
            assignment.recruiter_id = slot.recruiter_id
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
        await session.commit()
        assignment_id = assignment.id
        confirm_token_value = confirm_token.token
        reschedule_token_value = reschedule_token.token
        decline_token_value = decline_token.token

    reason = sanitize_plain_text(payload.reason or "", max_length=400)
    candidate_tz = getattr(slot, "candidate_tz", None) or slot_tz
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
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Slot not found")
        ensure_slot_scope(slot, principal)

        if norm_status(slot.status) != "FREE":
            return JSONResponse({"ok": False, "error": "slot_not_free", "message": "Слот уже занят"}, status_code=400)

        candidate = await session.scalar(select(User).where(User.telegram_id == payload.candidate_tg_id))
        if candidate is None:
            return JSONResponse({"ok": False, "error": "candidate_not_found", "message": "Кандидат не найден"}, status_code=404)

        slot.candidate_tg_id = payload.candidate_tg_id
        slot.candidate_fio = payload.candidate_fio or candidate.fio or ""
        slot.candidate_tz = slot.tz_name
        slot.status = SlotStatus.BOOKED
        await session.commit()

    return JSONResponse({
        "ok": True,
        "message": "Кандидат забронирован на слот",
        "slot_id": slot_id,
        "candidate_tg_id": payload.candidate_tg_id,
    })


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





@router.get("/message-templates")
async def api_message_templates(
    city: Optional[str] = Query(default=None),
    key: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    _: Principal = Depends(require_admin),
):
    payload = await list_message_templates(city=city, key_query=key, channel=channel, status=status)
    return JSONResponse(jsonable_encoder(payload))


@router.post("/message-templates", status_code=201)
async def api_create_message_template(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    ok, errors, tmpl = await create_message_template(
        key=str(data.get("key") or ""),
        locale=str(data.get("locale") or "ru"),
        channel=str(data.get("channel") or "tg"),
        body=str(data.get("body") or ""),
        is_active=bool(data.get("is_active", True)),
        city_id=data.get("city_id"),
        updated_by=str(data.get("updated_by") or "admin"),
        version=data.get("version"),
    )
    if not ok:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    await log_audit_action("template_create", "message_template", tmpl.id if tmpl else None, changes={"key": data.get("key"), "city_id": data.get("city_id")})
    return JSONResponse({"ok": True, "id": tmpl.id if tmpl else None}, status_code=201)


@router.put("/message-templates/{template_id}")
async def api_update_message_template(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    ok, errors, tmpl = await update_message_template(
        template_id=template_id,
        key=str(data.get("key") or ""),
        locale=str(data.get("locale") or "ru"),
        channel=str(data.get("channel") or "tg"),
        body=str(data.get("body") or ""),
        is_active=bool(data.get("is_active", True)),
        city_id=data.get("city_id"),
        updated_by=str(data.get("updated_by") or "admin"),
        expected_version=data.get("version"),
    )
    if not ok:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    await log_audit_action("template_update", "message_template", template_id, changes={"key": data.get("key"), "city_id": data.get("city_id")})
    return JSONResponse({"ok": True, "id": tmpl.id if tmpl else None})


@router.delete("/message-templates/{template_id}")
async def api_delete_message_template(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    await delete_message_template(template_id)
    await log_audit_action("template_delete", "message_template", template_id)
    return JSONResponse({"ok": True})


@router.get("/message-templates/{template_id}/history")
async def api_message_template_history(
    template_id: int,
    _: Principal = Depends(require_admin),
):
    history = await get_template_history(template_id)
    payload = [
        {
            "id": item.id,
            "version": item.version,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "updated_by": item.updated_by,
            "body": item.body_md,
        }
        for item in history
    ]
    return JSONResponse({"items": payload})


@router.get("/questions")
async def api_questions(_: Principal = Depends(require_admin)):
    return JSONResponse(await list_test_questions())


@router.post("/questions", status_code=201)
async def api_question_create(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    ok, question_id, error = await create_test_question(
        title=str(data.get("title") or ""),
        test_id=str(data.get("test_id") or ""),
        question_index=int(data.get("question_index")) if data.get("question_index") is not None else None,
        payload=str(data.get("payload") or ""),
        is_active=bool(data.get("is_active", True)),
    )
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse({"ok": True, "id": question_id}, status_code=201)


@router.get("/questions/{question_id}")
async def api_question_detail(
    question_id: int,
    _: Principal = Depends(require_admin),
):
    detail = await get_test_question_detail(question_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Question not found")
    question = detail.get("question")
    return JSONResponse(
        {
            "id": question.id,
            "title": question.title,
            "test_id": question.test_id,
            "question_index": question.question_index,
            "payload": detail.get("payload_json"),
            "is_active": question.is_active,
            "test_choices": detail.get("test_choices"),
        }
    )


@router.put("/questions/{question_id}")
async def api_question_update(
    question_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    ok, error = await update_test_question(
        question_id,
        title=str(data.get("title") or ""),
        test_id=str(data.get("test_id") or ""),
        question_index=int(data.get("question_index") or 0),
        payload=str(data.get("payload") or ""),
        is_active=bool(data.get("is_active", True)),
    )
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse({"ok": True})


@router.post("/questions/{question_id}/clone")
async def api_question_clone(
    question_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    ok, new_id, error = await clone_test_question(question_id)
    if not ok:
        status_code = 404 if error == "not_found" else 400
        return JSONResponse({"ok": False, "error": error}, status_code=status_code)
    return JSONResponse({"ok": True, "id": new_id})


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


@router.get("/templates/list")
async def api_templates_list(
    _: Principal = Depends(require_admin),
):
    """Return all MessageTemplate rows in the shape the legacy CRM UI expects."""
    async with async_session() as session:
        rows = await session.execute(
            select(MessageTemplate)
            .options(selectinload(MessageTemplate.city))
            .order_by(MessageTemplate.key, MessageTemplate.id)
        )
        templates = list(rows.scalars())

    custom_templates = []
    for t in templates:
        city_name = None
        is_global = t.city_id is None
        if t.city and hasattr(t.city, "name"):
            city_name = getattr(t.city, "name_plain", t.city.name) or t.city.name
        custom_templates.append({
            "id": t.id,
            "key": t.key,
            "city_id": t.city_id,
            "city_name": city_name,
            "city_name_plain": city_name,
            "is_global": is_global,
            "preview": (t.body_md or "")[:120],
            "length": len(t.body_md or ""),
        })
    return JSONResponse({"custom_templates": custom_templates, "overview": None})


@router.get("/templates/{template_id:int}")
async def api_template_detail(
    template_id: int,
    _: Principal = Depends(require_admin),
):
    """Return a single template by numeric ID for the edit page."""
    async with async_session() as session:
        tmpl = await session.get(MessageTemplate, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return JSONResponse({
        "id": tmpl.id,
        "key": tmpl.key,
        "text": tmpl.body_md or "",
        "city_id": tmpl.city_id,
        "is_global": tmpl.city_id is None,
        "is_active": tmpl.is_active,
    })


@router.put("/templates/{template_id:int}")
async def api_template_update(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    async with async_session() as session:
        tmpl = await session.get(MessageTemplate, template_id)
        if not tmpl:
            raise HTTPException(status_code=404, detail="Template not found")
        if "key" in data and data["key"]:
            tmpl.key = str(data["key"]).strip()
        if "text" in data:
            tmpl.body_md = str(data["text"] or "")
        if "city_id" in data:
            tmpl.city_id = int(data["city_id"]) if data["city_id"] else None
        if "is_active" in data:
            tmpl.is_active = bool(data["is_active"])
        tmpl.updated_by = "admin"
        tmpl.updated_at = datetime.now(timezone.utc)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return JSONResponse(
                {"ok": False, "error": "Шаблон для выбранного города и типа уже существует."},
                status_code=400,
            )
    await log_audit_action("template_update", "message_template", template_id, changes={"key": data.get("key"), "city_id": data.get("city_id")})
    return JSONResponse({"ok": True, "id": tmpl.id})


@router.delete("/templates/{template_id:int}")
async def api_template_delete(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    async with async_session() as session:
        tmpl = await session.get(MessageTemplate, template_id)
        if not tmpl:
            raise HTTPException(status_code=404, detail="Template not found")
        template_key = tmpl.key
        await session.delete(tmpl)
        await session.commit()
    await log_audit_action("template_delete", "message_template", template_id, changes={"key": template_key})
    return JSONResponse({"ok": True})


@router.post("/templates", status_code=201)
async def api_template_create(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    key_value = str(data.get("key") or "").strip()
    body_value = str(data.get("text") or "").strip()
    locale_value = str(data.get("locale") or "ru").strip() or "ru"
    channel_value = str(data.get("channel") or "tg").strip() or "tg"
    version_value = data.get("version")
    try:
        version_value = int(version_value) if version_value is not None else 1
    except (TypeError, ValueError):
        version_value = 1
    is_active_value = bool(data.get("is_active", True))

    if not body_value:
        return JSONResponse({"ok": False, "error": "Введите текст шаблона."}, status_code=400)

    city_id = data.get("city_id")
    if city_id is not None:
        try:
            city_id = int(city_id)
        except (TypeError, ValueError):
            city_id = None

    if not key_value:
        key_value = f"custom_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    revived_id: Optional[int] = None
    created_id: Optional[int] = None

    async with async_session() as session:
        existing = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == key_value,
                MessageTemplate.locale == locale_value,
                MessageTemplate.channel == channel_value,
                MessageTemplate.city_id == city_id,
                MessageTemplate.version == version_value,
            )
        )
        if existing:
            # Back-compat: legacy UI uses this endpoint to create templates.
            # If a matching template exists but is inactive, "revive" it instead of failing.
            if not existing.is_active:
                existing.body_md = body_value
                existing.is_active = is_active_value
                existing.updated_by = "admin"
                existing.updated_at = datetime.now(timezone.utc)
                await session.commit()
                revived_id = existing.id
            else:
                return JSONResponse(
                    {"ok": False, "error": "Шаблон для выбранного города и типа уже существует."},
                    status_code=400,
                )
        else:
            tmpl = MessageTemplate(
                key=key_value,
                locale=locale_value,
                channel=channel_value,
                body_md=body_value,
                version=version_value,
                is_active=is_active_value,
                city_id=city_id,
                updated_by="admin",
            )
            session.add(tmpl)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return JSONResponse(
                    {"ok": False, "error": "Шаблон для выбранного города и типа уже существует."},
                    status_code=400,
                )
            await session.refresh(tmpl)
            created_id = tmpl.id
    if revived_id is not None:
        await log_audit_action("template_revive", "message_template", revived_id, changes={"key": key_value, "city_id": city_id})
        return JSONResponse({"ok": True, "id": revived_id, "revived": True}, status_code=201)

    assert created_id is not None
    await log_audit_action("template_create", "message_template", created_id, changes={"key": key_value, "city_id": city_id})
    return JSONResponse({"ok": True, "id": created_id}, status_code=201)


@router.get("/template_keys")
async def api_template_keys():
    return JSONResponse(list_known_template_keys())


@router.get("/template_presets")
async def api_template_presets():
    presets_list = known_template_presets()

    def _sanitize(s: str) -> str:
        return s.encode("utf-8", "ignore").decode("utf-8") if s else s

    result = {}
    for item in presets_list:
        result[item["key"]] = _sanitize(item["text"])
    return JSONResponse(result)


@router.get("/message-templates/context-keys")
async def api_message_template_context_keys(
    _: Principal = Depends(require_admin),
):
    from backend.domain.template_contexts import TEMPLATE_CONTEXTS
    return JSONResponse(TEMPLATE_CONTEXTS)


@router.post("/message-templates/preview")
async def api_message_template_preview(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    text = str(data.get("text") or "")
    
    from backend.utils.jinja_renderer import render_template
    from backend.apps.admin_ui.services.message_templates import MOCK_CONTEXT
    
    try:
        rendered = render_template(text, MOCK_CONTEXT)
        return JSONResponse({"ok": True, "html": rendered})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


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
        from backend.apps.bot.city_registry import invalidate_candidate_cities_cache
    except Exception:
        return JSONResponse(
            {"ok": False, "error": "bot_runtime_unavailable"}, status_code=503
        )

    try:
        await invalidate_candidate_cities_cache()
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


@router.get("/candidates/{candidate_id}")
async def api_candidate(candidate_id: int):
    detail = await api_candidate_detail_payload(candidate_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return JSONResponse(jsonable_encoder(detail))


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
    range_start = _parse_date_param(date_from)
    range_end = _parse_date_param(date_to, end=True)
    data = await list_candidates(
        page=page,
        per_page=per_page,
        search=search,
        city=None,
        is_active=_parse_bool(active),
        rating=None,
        has_tests=None,
        has_messages=None,
        stage=None,
        statuses=status,
        recruiter_id=parse_optional_int(recruiter_id),
        city_ids=None,
        date_from=range_start,
        date_to=range_end,
        test1_status=None,
        test2_status=None,
        sort=None,
        sort_dir=None,
        calendar_mode=calendar_mode,
        pipeline=pipeline or "interview",
        principal=principal,
    )
    payload = {
        "items": data.get("views", {}).get("candidates", []),
        "total": data.get("total", 0),
        "page": data.get("page", page),
        "pages_total": data.get("pages_total", 1),
        "filters": data.get("filters", {}),
    }
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
        from sqlalchemy.orm import selectinload as sl_load
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
async def api_create_candidate(
    request: Request,
    _: None = Depends(require_csrf_token),
    principal: Principal = Depends(require_principal),
):
    """Create a new candidate with optional slot scheduling (JSON API)."""
    from datetime import timedelta
    from sqlalchemy.exc import IntegrityError
    from backend.apps.admin_ui.services.candidates import upsert_candidate
    from backend.apps.admin_ui.services.slots import (
        schedule_manual_candidate_slot_silent,
        ManualSlotError,
    )
    from backend.apps.admin_ui.services.candidates import delete_candidate
    from backend.core.time_utils import parse_form_datetime
    from backend.apps.admin_ui.timezones import DEFAULT_TZ

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    fio = sanitize_plain_text(str(data.get("fio") or "")).strip()
    phone = sanitize_plain_text(str(data.get("phone") or "")).strip() or None
    city_id = data.get("city_id")
    recruiter_id = data.get("recruiter_id")
    interview_date = data.get("interview_date")
    interview_time = data.get("interview_time")

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

    # Parse interview datetime
    interview_dt = None
    interview_tz = None
    if interview_date and interview_time:
        settings = get_settings()
        app_timezone = settings.timezone or DEFAULT_TZ
        interview_tz = (
            getattr(interview_city, "tz", None)
            or getattr(interview_recruiter, "tz", None)
            or app_timezone
        )
        try:
            interview_dt = parse_form_datetime(f"{interview_date}T{interview_time}", interview_tz)
        except ValueError:
            return JSONResponse({"ok": False, "error": "invalid_datetime"}, status_code=400)
    else:
        return JSONResponse({"ok": False, "error": "interview_datetime_required"}, status_code=400)

    # Get city name for candidate
    candidate_city = None
    if interview_city:
        candidate_city = getattr(interview_city, "name_plain", None) or interview_city.name

    # Create candidate
    try:
        user = await upsert_candidate(
            telegram_id=None,
            fio=fio,
            city=candidate_city,
            phone=phone,
            is_active=True,
            responsible_recruiter_id=recruiter_id_value,
            manual_slot_from=interview_dt,
            manual_slot_to=interview_dt + timedelta(minutes=60) if interview_dt else None,
            manual_slot_timezone=interview_tz,
        )
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": "validation_error", "message": str(exc)}, status_code=400)
    except IntegrityError:
        return JSONResponse({"ok": False, "error": "duplicate_candidate"}, status_code=409)

    # Schedule slot
    admin_username = request.session.get("username", "admin")
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)

    try:
        await schedule_manual_candidate_slot_silent(
            candidate=user,
            recruiter=interview_recruiter,
            city=interview_city,
            dt_utc=interview_dt,
            slot_tz=interview_tz or DEFAULT_TZ,
            admin_username=admin_username,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except ManualSlotError as exc:
        await delete_candidate(user.id)
        return JSONResponse({"ok": False, "error": "slot_conflict", "message": str(exc)}, status_code=409)

    return JSONResponse(
        {
            "ok": True,
            "id": user.id,
            "fio": user.fio,
            "city": user.city,
            "slot_scheduled": True,
        },
        status_code=201,
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
        schedule_manual_candidate_slot,
        ManualSlotError,
    )
    from backend.core.time_utils import parse_form_datetime
    from backend.apps.admin_ui.timezones import DEFAULT_TZ
    from backend.domain.repositories import find_city_by_plain_name

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

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
            candidate_city_id = data.get("city_id")
            if candidate_city_id is not None:
                try:
                    candidate_city_id = int(candidate_city_id)
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

    if not user.telegram_id:
        return JSONResponse({"ok": False, "error": "missing_telegram"}, status_code=400)

    recruiter_id = data.get("recruiter_id")
    city_id = data.get("city_id")
    date_str = data.get("date")
    time_str = data.get("time")
    custom_message = data.get("custom_message")

    # Auto-resolve recruiter from principal when not explicitly provided
    if not recruiter_id and principal.type == "recruiter":
        recruiter_id = principal.id

    if not recruiter_id or not city_id or not date_str or not time_str:
        return JSONResponse({"ok": False, "error": "missing_fields"}, status_code=400)

    # Validate recruiter
    async with async_session() as session:
        recruiter = await session.get(Recruiter, int(recruiter_id))
        city = await session.get(City, int(city_id))

    if recruiter is None:
        return JSONResponse({"ok": False, "error": "recruiter_not_found"}, status_code=404)
    if city is None:
        return JSONResponse({"ok": False, "error": "city_not_found"}, status_code=404)

    # Recruiter scoping
    if principal.type == "recruiter" and recruiter.id != principal.id:
        return JSONResponse({"ok": False, "error": "permission_denied"}, status_code=403)

    settings = get_settings()
    slot_tz = getattr(city, "tz", None) or getattr(recruiter, "tz", None) or settings.timezone or DEFAULT_TZ

    try:
        dt_utc = parse_form_datetime(f"{date_str}T{time_str}", slot_tz)
    except ValueError:
        return JSONResponse({"ok": False, "error": "invalid_datetime"}, status_code=400)

    admin_username = request.session.get("username", "admin")
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    custom_message_sent = bool(custom_message)
    custom_message_text = custom_message.strip() if custom_message else None

    # If the candidate has an active reschedule request, reuse the existing slot assignment
    # instead of creating a new one (otherwise we block on "candidate_has_active_assignment").
    try:
        candidate_key = getattr(user, "candidate_id", None)
        assignment = None
        slot = None
        if candidate_key:
            from backend.domain.models import (
                RescheduleRequest,
                RescheduleRequestStatus,
                Slot,
                SlotAssignment,
                SlotAssignmentStatus,
            )
            from backend.domain.slot_assignment_service import propose_alternative
            from backend.domain.candidates.status_service import set_status_slot_pending
            from backend.core.time_utils import ensure_aware_utc

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
                    slot = await session.get(Slot, assignment.slot_id)
                    if slot is None:
                        assignment = None

            if assignment is not None and slot is not None:
                if int(recruiter.id) != int(assignment.recruiter_id):
                    return JSONResponse(
                        {
                            "ok": False,
                            "error": "assignment_recruiter_mismatch",
                            "message": "Запрос переноса привязан к другому рекрутёру.",
                        },
                        status_code=409,
                    )
                if getattr(slot, "city_id", None) is not None and int(city.id) != int(slot.city_id):
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
                    return JSONResponse(
                        {
                            "ok": False,
                            "error": result.status,
                            "message": result.message or "Не удалось перенести слот.",
                        },
                        status_code=result.status_code or 409,
                    )
                try:
                    await set_status_slot_pending(user.telegram_id)
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

    try:
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

    return JSONResponse({
        "ok": True,
        "status": result.status,
        "message": result.message or "Slot scheduled",
    })


@router.post("/candidates/{candidate_id}/schedule-intro-day")
async def api_schedule_intro_day(
    request: Request,
    candidate_id: int,
    _: None = Depends(require_csrf_token),
    principal: Principal = Depends(require_principal),
):
    """Schedule intro day for a candidate (JSON API)."""
    from datetime import timezone as tz_utc
    from backend.apps.admin_ui.services.candidates import (
        get_candidate_detail,
        DEFAULT_INTRO_DAY_INVITATION_TEMPLATE,
        render_intro_day_invitation,
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

    # Resolve recruiter: city FK → city M2M (no user fallback)
    recruiter = None
    if getattr(city_record, "responsible_recruiter_id", None):
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
        template_source = (
            getattr(city_record, "intro_day_template", None)
            or DEFAULT_INTRO_DAY_INVITATION_TEMPLATE
        )
        custom_message = render_intro_day_invitation(
            template_source,
            candidate_fio=user.fio or "Кандидат",
            date_str=str(date_str),
            time_str=str(time_str),
        )

    async with async_session() as session:
        # Check for existing intro_day slot
        from sqlalchemy import select as sql_select
        existing = await session.scalar(
            sql_select(Slot).where(
                Slot.candidate_tg_id == candidate_tg_id,
                Slot.recruiter_id == recruiter.id,
                Slot.purpose == "intro_day",
            )
        )
        if existing:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "intro_day_already_scheduled",
                    "message": "Ознакомительный день уже назначен для этого кандидата.",
                },
                status_code=409,
            )

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

    return JSONResponse({
        "ok": True,
        "slot_id": slot.id,
        "message": "Intro day scheduled",
    })
