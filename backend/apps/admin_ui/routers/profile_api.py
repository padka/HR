from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.perf.cache import keys as cache_keys
from backend.apps.admin_ui.perf.cache.readthrough import get_cached, get_or_compute
from backend.apps.admin_ui.security import Principal, require_csrf_token, require_principal
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.bot.reminders import get_reminder_service
from backend.core.audit import log_audit_action
from backend.core.auth import verify_password as verify_auth_password
from backend.core.db import async_session
from backend.core.passwords import hash_password
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.auth_account import AuthAccount
from backend.domain.candidates.models import User
from backend.domain.models import City, Recruiter, Slot, recruiter_city_association, validate_timezone_name

router = APIRouter(tags=["profile_api"])


def _normalize_profile_http_url(raw: Optional[str]) -> Optional[str]:
    value = (raw or "").strip()
    if not value:
        return None
    candidate = value if "://" in value else f"https://{value}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail={"message": "Ссылка должна быть валидным http/https URL"})
    return parsed.geturl()


class ProfileSettingsUpdatePayload(BaseModel):
    name: str
    tz: str
    telemost_url: Optional[str] = None


class ProfilePasswordChangePayload(BaseModel):
    current_password: str
    new_password: str


def _avatar_dir() -> Path:
    path = Path("artifacts/profile_avatars")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _avatar_prefix(principal: Principal) -> str:
    return f"{principal.type}_{principal.id}"


def _find_avatar_file(prefix: str) -> Optional[Path]:
    avatar_dir = _avatar_dir()
    for ext in ("png", "jpg", "jpeg", "webp"):
        candidate = avatar_dir / f"{prefix}.{ext}"
        if candidate.exists():
            return candidate
    return None


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
            for user in cand_rows.scalars().all():
                active_candidates.append(
                    {
                        "id": user.id,
                        "name": user.fio or user.telegram_username or f"Кандидат {user.id}",
                        "city": user.city,
                        "status": getattr(user, "status", None) or getattr(user, "candidate_status", None),
                    }
                )
        else:
            candidate_count = await session.scalar(select(func.count()).select_from(User)) or 0
            slot_count = await session.scalar(select(func.count()).select_from(Slot)) or 0
            recruiter_count = await session.scalar(select(func.count()).select_from(Recruiter)) or 0
            city_count = await session.scalar(select(func.count()).select_from(City)) or 0

            status_rows = await session.execute(select(Slot.status, func.count()).group_by(Slot.status))
            for slot_status, count in status_rows:
                slots_by_status[str(slot_status).lower()] = count

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
                "tg_chat_id": recruiter.tg_chat_id,
                "telemost_url": recruiter.telemost_url,
                "active": recruiter.active,
                "cities": [{"id": city.get("id"), "name": city.get("name")} for city in city_options],
            }

    pending_count = len([meeting for meeting in today_meetings + upcoming_meetings if str(meeting.get("status")).upper() in {"PENDING"}])
    booked_count = len([meeting for meeting in today_meetings + upcoming_meetings if str(meeting.get("status")).upper() in {"BOOKED"}])
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
            (
                len(
                    [
                        meeting
                        for meeting in today_meetings + upcoming_meetings
                        if str(meeting.get("status")).upper() in {"BOOKED", "CONFIRMED_BY_CANDIDATE"}
                    ]
                )
                / total_slots
            )
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


@router.patch("/profile/settings")
async def api_profile_settings_update(
    payload: ProfileSettingsUpdatePayload,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    if principal.type != "recruiter":
        raise HTTPException(status_code=403, detail={"message": "Настройки профиля доступны только рекрутёру"})

    cleaned_name = sanitize_plain_text(payload.name)
    if not cleaned_name:
        raise HTTPException(status_code=400, detail={"message": "Имя не может быть пустым"})
    if len(cleaned_name) > 100:
        raise HTTPException(status_code=400, detail={"message": "Имя не должно превышать 100 символов"})

    raw_tz = (payload.tz or "").strip() or "Europe/Moscow"
    try:
        normalized_tz = validate_timezone_name(raw_tz)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    telemost_url = _normalize_profile_http_url(payload.telemost_url)

    async with async_session() as session:
        recruiter = await session.scalar(
            select(Recruiter)
            .options(selectinload(Recruiter.cities))
            .where(Recruiter.id == principal.id)
        )
        if recruiter is None:
            raise HTTPException(status_code=404, detail={"message": "Рекрутёр не найден"})

        recruiter.name = cleaned_name
        recruiter.tz = normalized_tz
        recruiter.telemost_url = telemost_url
        await session.commit()
        await session.refresh(recruiter)

        city_payload = [{"id": city.id, "name": city.name_plain} for city in recruiter.cities]

    await log_audit_action(
        "profile_settings_updated",
        "recruiter",
        principal.id,
        changes={
            "tz": normalized_tz,
            "telemost_url_updated": bool(telemost_url),
        },
    )

    return JSONResponse(
        {
            "ok": True,
            "recruiter": {
                "id": principal.id,
                "name": cleaned_name,
                "tz": normalized_tz,
                "telemost_url": telemost_url,
                "cities": city_payload,
            },
        }
    )


@router.post("/profile/change-password")
async def api_profile_change_password(
    payload: ProfilePasswordChangePayload,
    request: Request,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    if principal.type != "recruiter":
        raise HTTPException(status_code=403, detail={"message": "Смена пароля доступна только рекрутёру"})

    current_password = payload.current_password or ""
    new_password = payload.new_password or ""
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail={"message": "Новый пароль должен быть не короче 8 символов"})
    if len(new_password) > 128:
        raise HTTPException(status_code=400, detail={"message": "Новый пароль слишком длинный"})
    if secrets.compare_digest(current_password, new_password):
        raise HTTPException(status_code=400, detail={"message": "Новый пароль должен отличаться от текущего"})

    async with async_session() as session:
        account = await session.scalar(
            select(AuthAccount).where(
                AuthAccount.principal_type == "recruiter",
                AuthAccount.principal_id == principal.id,
                AuthAccount.is_active.is_(True),
            )
        )
        if account is None:
            raise HTTPException(status_code=404, detail={"message": "Учётная запись рекрутёра не найдена"})
        if not verify_auth_password(current_password, account.password_hash):
            raise HTTPException(status_code=400, detail={"message": "Текущий пароль указан неверно"})

        account.password_hash = hash_password(new_password)
        await session.commit()

    await log_audit_action(
        "profile_password_changed",
        "recruiter",
        principal.id,
        changes=None,
    )
    return JSONResponse({"ok": True})


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
            continue
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
            continue
    return JSONResponse({"ok": True, "removed": removed})
