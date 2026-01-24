from datetime import date as date_type, datetime, time, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from backend.apps.admin_ui.services.cities import (
    api_city_owners_payload,
    list_cities,
    get_city,
    create_city,
    update_city_settings,
    delete_city,
)
from backend.apps.admin_ui.services.dashboard import dashboard_counts, get_bot_funnel_stats
from backend.apps.admin_ui.services.dashboard_calendar import (
    dashboard_calendar_snapshot,
)
from backend.apps.admin_ui.services.candidates import (
    get_candidate_detail,
    api_candidate_detail_payload,
    update_candidate_status,
    list_candidates,
)
from backend.apps.admin_ui.services.chat import (
    list_chat_history,
    retry_chat_message,
    send_chat_message,
)
from backend.apps.admin_ui.services.slots import execute_bot_dispatch
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.recruiters import (
    api_recruiters_payload,
    api_get_recruiter,
    create_recruiter,
    delete_recruiter,
    update_recruiter,
)
from backend.apps.admin_ui.services.slots.core import api_slots_payload
from backend.apps.admin_ui.services.templates import (
    api_templates_payload,
    list_templates,
    create_template,
    get_template,
    update_template,
    delete_template,
    list_known_template_keys,
    known_template_presets,
    update_templates_for_city,
    notify_templates_changed,
)
from backend.apps.admin_ui.services.message_templates import (
    list_message_templates,
    create_message_template,
    update_message_template,
    delete_message_template,
    get_template_history,
)
from backend.apps.admin_ui.services.questions import (
    list_test_questions,
    get_test_question_detail,
    update_test_question,
    create_test_question,
    clone_test_question,
)
from backend.core.db import async_session
from backend.domain.models import Recruiter, Slot, City, recruiter_city_association
from backend.domain.candidates.models import User
from backend.apps.admin_ui.utils import parse_optional_int, status_filter
from backend.apps.admin_ui.security import require_csrf_token, require_principal, require_admin, Principal
from backend.domain.errors import CityAlreadyExistsError
from backend.core.settings import get_settings
from backend.core.sanitizers import sanitize_plain_text
from backend.apps.bot.reminders import get_reminder_service
from zoneinfo import ZoneInfo
from backend.apps.admin_ui.timezones import timezone_options

router = APIRouter(prefix="/api", tags=["api"])


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


@router.get("/health")
async def api_health():
    counts = await dashboard_counts()
    return counts


@router.get("/dashboard/summary")
async def api_dashboard_summary(principal: Principal = Depends(require_principal)):
    return JSONResponse(await dashboard_counts(principal=principal))


async def _profile_snapshot(principal: Principal, request: Request) -> dict:
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
                select(Slot)
                .where(Slot.recruiter_id == principal.id)
                .order_by(Slot.start_utc.asc())
                .limit(10)
            )
            slots = slot_rows.scalars().all()
            now_utc = datetime.now(timezone.utc)
            for s in slots:
                status_value = s.status.name if hasattr(s.status, "name") else s.status
                item = {
                    "id": s.id,
                    "status": status_value,
                    "start_utc": s.start_utc.isoformat() if s.start_utc else None,
                    "city_id": s.city_id,
                }
                if s.start_utc:
                    minutes = int((s.start_utc - now_utc).total_seconds() / 60)
                    if minutes > 0:
                        nearest_minutes = minutes if nearest_minutes is None else min(nearest_minutes, minutes)
                start_local_date = s.start_utc.astimezone(tzinfo).date() if s.start_utc else None
                if start_local_date and start_local_date == now_utc.astimezone(tzinfo).date():
                    today_meetings.append(item)
                else:
                    upcoming_meetings.append(item)

            # planner for 7 days
            planner_rows = await session.execute(
                select(Slot)
                .where(
                    Slot.recruiter_id == principal.id,
                    Slot.start_utc >= datetime.now(timezone.utc),
                    Slot.start_utc <= datetime.now(timezone.utc) + timedelta(days=7),
                )
                .order_by(Slot.start_utc.asc())
            )
            planner_items = planner_rows.scalars().all()
            day_map: dict[str, list[dict]] = {}
            for s in planner_items:
                local = s.start_utc.astimezone(tzinfo) if s.start_utc else None
                day_key = local.strftime("%Y-%m-%d") if local else "unknown"
                payload = {
                    "id": s.id,
                    "time": local.strftime("%H:%M") if local else "",
                    "status": s.status.name if hasattr(s.status, "name") else s.status,
                    "city": s.city_id,
                }
                day_map.setdefault(day_key, []).append(payload)
            for day, items in sorted(day_map.items()):
                planner_days.append({"date": day, "entries": items})

            if planner_items:
                deltas = [
                    (slot.start_utc - now_utc).total_seconds() / 3600
                    for slot in planner_items
                    if slot.start_utc and slot.start_utc > now_utc
                ]
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

            now_utc = datetime.now(timezone.utc)
            global_slots = await session.execute(
                select(Slot)
                .where(Slot.start_utc >= now_utc)
                .order_by(Slot.start_utc.asc())
                .limit(8)
            )
            for s in global_slots.scalars().all():
                upcoming_global.append(
                    {
                        "id": s.id,
                        "status": s.status.name if hasattr(s.status, "name") else s.status,
                        "start_utc": s.start_utc.isoformat() if s.start_utc else None,
                        "city_id": s.city_id,
                        "recruiter_id": s.recruiter_id,
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
    }


@router.get("/profile")
async def api_profile(request: Request, principal: Principal = Depends(require_principal)):
    recruiter_payload = None
    if principal.type == "recruiter":
        async with async_session() as session:
            recruiter = await session.get(Recruiter, principal.id)
            if recruiter:
                rows = await session.execute(
                    select(City)
                    .join(recruiter_city_association)
                    .where(recruiter_city_association.c.recruiter_id == recruiter.id)
                )
                cities = rows.scalars().all()
                recruiter_payload = {
                    "id": recruiter.id,
                    "name": recruiter.name,
                    "tz": recruiter.tz,
                    "active": recruiter.active,
                    "cities": [{"id": city.id, "name": city.name} for city in cities],
                }

    stats = await dashboard_counts(principal=principal)
    profile_payload = await _profile_snapshot(principal, request)
    return JSONResponse(
        {
            "principal": {"type": principal.type, "id": principal.id},
            "recruiter": recruiter_payload,
            "stats": stats,
            "profile": profile_payload,
        }
    )


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
                "plan_week": getattr(city, "plan_week", None),
                "plan_month": getattr(city, "plan_month", None),
                "recruiter_ids": [rec.id for rec in getattr(city, "recruiters", [])],
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
        "plan_week": getattr(city, "plan_week", None),
        "plan_month": getattr(city, "plan_month", None),
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
        await create_city(name=str(data.get("name") or ""), tz=str(data.get("tz") or "Europe/Moscow"))
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
        templates={},
        criteria=data.get("criteria"),
        experts=data.get("experts"),
        plan_week=data.get("plan_week"),
        plan_month=data.get("plan_month"),
        tz=data.get("tz"),
        active=data.get("active"),
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


@router.get("/templates")
async def api_templates(city_id: Optional[int] = None, key: Optional[str] = None):
    payload = await api_templates_payload(city_id, key)
    status_code = 200
    if isinstance(payload, dict) and payload.get("found") is False:
        status_code = 404
    return JSONResponse(payload, status_code=status_code)


@router.get("/templates/list")
async def api_templates_list(_: Principal = Depends(require_admin)):
    return JSONResponse(await list_templates())


@router.post("/templates/save")
async def api_templates_save(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    payload = await request.json()
    city_raw = payload.get("city_id")
    if city_raw in (None, "", "null"):
        city_id: Optional[int] = None
    else:
        try:
            city_id = int(city_raw)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "invalid_city"}, status_code=400)

    templates_payload = payload.get("templates") or {}
    if not isinstance(templates_payload, dict):
        templates_payload = {}

    error = await update_templates_for_city(city_id, templates_payload)
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    notify_templates_changed()
    return JSONResponse({"ok": True})

@router.post("/templates", status_code=201)
async def api_create_template(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    text = str(data.get("text") or "")
    if not text.strip():
        return JSONResponse({"ok": False, "error": "empty_text"}, status_code=400)
    city_id = data.get("city_id")
    if city_id in ("", "null", None):
        city_id = None
    else:
        city_id = int(city_id)
    key = data.get("key")
    try:
        final_key = await create_template(text, city_id, key=key)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "key": final_key}, status_code=201)


@router.get("/templates/{template_id}")
async def api_template_detail(
    template_id: int,
    _: Principal = Depends(require_admin),
):
    tmpl = await get_template(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return JSONResponse(
        {
            "id": tmpl.id,
            "key": tmpl.key,
            "text": tmpl.content,
            "city_id": tmpl.city_id,
            "is_global": tmpl.city_id is None,
        }
    )


@router.put("/templates/{template_id}")
async def api_update_template(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    key = str(data.get("key") or "").strip()
    text = str(data.get("text") or "")
    city_id = data.get("city_id")
    if city_id in ("", "null", None):
        city_id = None
    else:
        city_id = int(city_id)
    ok = await update_template(template_id, key=key, text=text, city_id=city_id)
    if not ok:
        return JSONResponse({"ok": False, "error": "update_failed"}, status_code=400)
    return JSONResponse({"ok": True})


@router.delete("/templates/{template_id}")
async def api_delete_template(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    await delete_template(template_id)
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
    return JSONResponse(payload)


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
        version=data.get("version"),
    )
    if not ok:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    return JSONResponse({"ok": True, "id": tmpl.id if tmpl else None})


@router.delete("/message-templates/{template_id}")
async def api_delete_message_template(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    await delete_message_template(template_id)
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
            "body": item.body,
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
    return JSONResponse(
        await get_weekly_kpis(company_tz, principal=principal, recruiter_id=recruiter_id)
    )


@router.get("/kpis/history")
async def api_weekly_history(
    limit: int = Query(default=12, ge=1, le=104),
    offset: int = Query(default=0, ge=0),
):
    return JSONResponse(await list_weekly_history(limit=limit, offset=offset))


@router.get("/template_keys")
async def api_template_keys():
    return JSONResponse(list_known_template_keys())


@router.get("/template_presets")
async def api_template_presets():
    return JSONResponse(known_template_presets())


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
):
    if getattr(request.app.state, "db_available", True) is False:
        return JSONResponse({"items": [], "latest_id": after_id, "degraded": True})
    return JSONResponse({"items": [], "latest_id": after_id, "degraded": False})


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
    return JSONResponse(payload)


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
    from backend.apps.admin_ui.services.candidates import get_candidate_detail
    from backend.apps.admin_ui.services.slots import (
        schedule_manual_candidate_slot,
        ManualSlotError,
    )
    from backend.core.time_utils import parse_form_datetime
    from backend.apps.admin_ui.timezones import DEFAULT_TZ
    from backend.core.guards import ensure_candidate_scope

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        raise HTTPException(status_code=404, detail={"message": "Candidate not found"})

    user = detail["user"]
    if not user.telegram_id:
        return JSONResponse({"ok": False, "error": "missing_telegram"}, status_code=400)

    recruiter_id = data.get("recruiter_id")
    city_id = data.get("city_id")
    date_str = data.get("date")
    time_str = data.get("time")
    custom_message = data.get("custom_message")

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
    from backend.apps.admin_ui.services.candidates import get_candidate_detail
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
    if not user.telegram_id:
        return JSONResponse({"ok": False, "error": "missing_telegram"}, status_code=400)

    date_str = data.get("date")
    time_str = data.get("time")

    if not date_str or not time_str:
        return JSONResponse({"ok": False, "error": "missing_datetime"}, status_code=400)

    # Find city and recruiter
    city_record = None
    if user.city:
        city_record = await find_city_by_plain_name(user.city)
        if city_record:
            async with async_session() as session:
                city_record = await session.get(
                    City,
                    city_record.id,
                    options=(selectinload(City.recruiters),),
                )

    if not city_record:
        return JSONResponse({"ok": False, "error": "city_not_found"}, status_code=400)

    recruiter = None
    if getattr(city_record, "recruiters", None):
        for rec in city_record.recruiters:
            if rec is not None and getattr(rec, "active", True):
                recruiter = rec
                break

    if not recruiter:
        return JSONResponse({"ok": False, "error": "no_recruiter_for_city"}, status_code=400)

    # Recruiter scoping
    if principal.type == "recruiter" and recruiter.id != principal.id:
        return JSONResponse({"ok": False, "error": "permission_denied"}, status_code=403)

    slot_tz = getattr(city_record, "tz", None) or getattr(recruiter, "tz", None) or DEFAULT_TZ
    dt_utc = recruiter_time_to_utc(date_str, time_str, slot_tz)
    if not dt_utc:
        return JSONResponse({"ok": False, "error": "invalid_datetime"}, status_code=400)

    async with async_session() as session:
        # Check for existing intro_day slot
        from sqlalchemy import select as sql_select
        existing = await session.scalar(
            sql_select(Slot).where(
                Slot.candidate_tg_id == user.telegram_id,
                Slot.recruiter_id == recruiter.id,
                Slot.purpose == "intro_day",
            )
        )
        if existing:
            return JSONResponse({"ok": False, "error": "intro_day_already_scheduled"}, status_code=409)

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
            candidate_tg_id=user.telegram_id,
            candidate_fio=user.fio,
            candidate_tz=slot_tz,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        # Update candidate status
        try:
            from backend.domain.candidates.status_service import set_status_intro_day_scheduled
            await set_status_intro_day_scheduled(user.telegram_id, force=True)
        except Exception:
            pass

        # Add notification
        try:
            await add_outbox_notification(
                notification_type="intro_day_invitation",
                booking_id=slot.id,
                candidate_tg_id=user.telegram_id,
                payload={},
            )
        except Exception:
            pass

        # Schedule reminders
        try:
            from backend.apps.bot.reminders import get_reminder_service
            reminder_service = get_reminder_service()
            await reminder_service.schedule_for_slot(slot.id, skip_confirmation_prompts=False)
        except Exception:
            pass

    return JSONResponse({
        "ok": True,
        "slot_id": slot.id,
        "message": "Intro day scheduled",
    })
