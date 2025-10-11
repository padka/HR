import base64
import hashlib
import hmac
import json
from typing import Dict, Optional

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.cities import list_cities
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.apps.admin_ui.services.slots import (
    bulk_create_slots,
    create_slot,
    list_slots,
    recruiters_for_slot_form,
    delete_slot,
    delete_all_slots,
    set_slot_outcome,
    execute_bot_dispatch,
    reschedule_slot_booking,
    reject_slot_booking,
)
from backend.apps.admin_ui.utils import (
    ensure_utc,
    local_naive_to_utc,
    norm_status,
    parse_optional_int,
    status_filter,
    utc_to_local_naive,
    validate_timezone_name,
)
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.models import City, Recruiter, Slot, SlotStatus

router = APIRouter(prefix="/slots", tags=["slots"])

_FLASH_COOKIE = "admin_flash"
_SETTINGS = get_settings()
_SECRET = _SETTINGS.session_secret.encode()


def _parse_checkbox(value: Optional[str]) -> bool:
    return value not in (None, "", "0", "false", "False")


def _pop_flash(request: Request) -> Optional[Dict[str, str]]:
    raw = request.cookies.get(_FLASH_COOKIE)
    if not raw:
        return None
    try:
        padding = "=" * (-len(raw) % 4)
        data = base64.urlsafe_b64decode((raw + padding).encode())
        payload, sig = data.rsplit(b".", 1)
        expected = hmac.new(_SECRET, payload, hashlib.sha256).hexdigest().encode()
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None


def _set_flash(response: RedirectResponse, status: str, message: str) -> None:
    payload = json.dumps({"status": status, "message": message}, ensure_ascii=False).encode("utf-8")
    digest = hmac.new(_SECRET, payload, hashlib.sha256).hexdigest().encode()
    token = base64.urlsafe_b64encode(payload + b"." + digest).decode("ascii").rstrip("=")
    response.set_cookie(
        _FLASH_COOKIE,
        token,
        max_age=300,
        path="/",
        httponly=True,
        secure=_SETTINGS.session_cookie_secure,
        samesite=_SETTINGS.session_cookie_samesite,
    )


def _slot_payload(slot: Slot, tz_name: Optional[str]) -> Dict[str, object]:
    starts_at_local: Optional[datetime] = None
    if tz_name:
        try:
            starts_at_local = utc_to_local_naive(slot.start_utc, tz_name)
        except ValueError:
            starts_at_local = None
    return {
        "id": slot.id,
        "recruiter_id": slot.recruiter_id,
        "city_id": slot.city_id,
        "region_id": slot.city_id,
        "starts_at_utc": ensure_utc(slot.start_utc),
        "starts_at_local": starts_at_local,
        "duration_min": slot.duration_min,
        "status": norm_status(slot.status),
    }


class SlotPayloadBase(BaseModel):
    region_id: Optional[int] = Field(default=None, alias="city_id")
    starts_at_local: Optional[datetime] = None
    starts_at_utc: Optional[datetime] = None
    duration_min: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("starts_at_local", mode="before")
    @classmethod
    def _parse_local(cls, value: object) -> Optional[datetime]:
        if value in (None, "", b"", []):
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("starts_at_local must be ISO8601 without timezone") from exc
        if isinstance(value, datetime):
            return value
        raise ValueError("starts_at_local must be a datetime string")

    @field_validator("starts_at_local")
    @classmethod
    def _ensure_naive(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and value.tzinfo is not None:
            raise ValueError("starts_at_local must not include timezone information")
        return value


class SlotCreatePayload(SlotPayloadBase):
    recruiter_id: int
    region_id: int = Field(..., alias="city_id")


class SlotUpdatePayload(SlotPayloadBase):
    recruiter_id: Optional[int] = None
    region_id: int = Field(..., alias="city_id")


@router.get("", response_class=HTMLResponse)
async def slots_list(
    request: Request,
    recruiter_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    city_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    recruiter = parse_optional_int(recruiter_id)
    status_norm = status_filter(status)
    city_filter = parse_optional_int(city_id)
    result = await list_slots(recruiter, status_norm, page, per_page, city_id=city_filter)
    recruiter_rows = await list_recruiters()
    recruiter_options = [row["rec"] for row in recruiter_rows]
    slots = result["items"]
    aggregated = result.get("status_counts") or {}
    status_counts: Dict[str, int] = {
        "total": result.get("total", len(slots)),
        "FREE": int(aggregated.get("FREE", 0)),
        "PENDING": int(aggregated.get("PENDING", 0)),
        "BOOKED": int(aggregated.get("BOOKED", 0)),
        "CONFIRMED_BY_CANDIDATE": int(
            aggregated.get("CONFIRMED_BY_CANDIDATE", 0)
        ),
    }
    flash = _pop_flash(request)
    city_options = await list_cities(order_by_name=True)

    context = {
        "request": request,
        "slots": slots,
        "filter_recruiter_id": recruiter,
        "filter_status": status_norm,
        "filter_city_id": city_filter,
        "page": result["page"],
        "pages_total": result["pages_total"],
        "per_page": per_page,
        "recruiter_options": recruiter_options,
        "city_options": city_options,
        "status_counts": status_counts,
        "flash": flash,
    }
    response = templates.TemplateResponse("slots_list.html", context)
    if flash:
        response.delete_cookie(
            _FLASH_COOKIE,
            path="/",
            secure=_SETTINGS.session_cookie_secure,
            httponly=True,
            samesite=_SETTINGS.session_cookie_samesite,
        )
    return response


@router.get("/new", response_class=HTMLResponse)
async def slots_new(request: Request):
    recruiters = await recruiters_for_slot_form()
    flash = _pop_flash(request)
    response = templates.TemplateResponse(
        "slots_new.html",
        {"request": request, "recruiters": recruiters, "flash": flash},
    )
    if flash:
        response.delete_cookie(
            _FLASH_COOKIE,
            path="/",
            secure=_SETTINGS.session_cookie_secure,
            httponly=True,
            samesite=_SETTINGS.session_cookie_samesite,
        )
    return response


@router.post("/create")
async def slots_create(
    recruiter_id: int = Form(...),
    city_id: int = Form(...),
    date: str = Form(...),
    time: str = Form(...),
):
    ok, _ = await create_slot(recruiter_id, date, time, city_id=city_id)
    redirect = "/slots" if ok else "/slots/new"
    response = RedirectResponse(url=redirect, status_code=303)
    if ok:
        _set_flash(response, "success", "Слот создан")
    else:
        _set_flash(response, "error", "Не удалось создать слот. Проверьте город, дату и время.")
    return response


@router.post("/bulk_create")
async def slots_bulk_create(
    request: Request,
    recruiter_id: int = Form(...),
    city_id: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    break_start: str = Form(...),
    break_end: str = Form(...),
    step_min: int = Form(...),
    include_weekends: Optional[str] = Form(default=None),
    use_break: Optional[str] = Form(default=None),
):
    created, error = await bulk_create_slots(
        recruiter_id=recruiter_id,
        city_id=city_id,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        break_start=break_start,
        break_end=break_end,
        step_min=step_min,
        include_weekends=_parse_checkbox(include_weekends),
        use_break=_parse_checkbox(use_break),
    )

    response = RedirectResponse(url="/slots", status_code=303)
    if error:
        _set_flash(response, "error", error)
    elif created == 0:
        _set_flash(response, "info", "Новые слоты не созданы — все уже существуют.")
    else:
        _set_flash(response, "success", f"Создано {created} слот(ов).")

    return response


@router.post("", status_code=status.HTTP_201_CREATED)
async def slots_api_create(payload: SlotCreatePayload):
    async with async_session() as session:
        recruiter = await session.get(Recruiter, payload.recruiter_id)
        if recruiter is None:
            raise HTTPException(status_code=404, detail="Recruiter not found")

        region_id = payload.region_id
        if region_id is None:
            raise HTTPException(status_code=422, detail="region_id is required")

        city = await session.get(City, region_id)
        if city is None:
            raise HTTPException(status_code=422, detail="Region not found")
        if city.responsible_recruiter_id != recruiter.id:
            raise HTTPException(
                status_code=422,
                detail="Region is not assigned to the recruiter",
            )

        try:
            tz_name = validate_timezone_name(city.tz)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Region timezone is invalid",
            )

        if payload.starts_at_local is not None:
            start_utc = local_naive_to_utc(payload.starts_at_local, tz_name)
        elif payload.starts_at_utc is not None:
            start_utc = ensure_utc(payload.starts_at_utc)
        else:
            raise HTTPException(
                status_code=422,
                detail="starts_at_local is required",
            )

        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=start_utc,
            status=status_free,
        )
        if payload.duration_min is not None:
            slot.duration_min = max(int(payload.duration_min), 1)

        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    return _slot_payload(slot, tz_name)


@router.put("/{slot_id}")
async def slots_api_update(slot_id: int, payload: SlotUpdatePayload):
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Slot not found")

        recruiter_id = payload.recruiter_id or slot.recruiter_id
        recruiter = await session.get(Recruiter, recruiter_id)
        if recruiter is None:
            raise HTTPException(status_code=404, detail="Recruiter not found")

        region_id = payload.region_id
        if region_id is None:
            raise HTTPException(status_code=422, detail="region_id is required")

        city = await session.get(City, region_id)
        if city is None:
            raise HTTPException(status_code=422, detail="Region not found")
        if city.responsible_recruiter_id != recruiter.id:
            raise HTTPException(
                status_code=422,
                detail="Region is not assigned to the recruiter",
            )

        try:
            tz_name = validate_timezone_name(city.tz)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Region timezone is invalid",
            )

        if payload.starts_at_local is not None:
            start_utc = local_naive_to_utc(payload.starts_at_local, tz_name)
        elif payload.starts_at_utc is not None:
            start_utc = ensure_utc(payload.starts_at_utc)
        else:
            raise HTTPException(
                status_code=422,
                detail="starts_at_local is required",
            )

        slot.recruiter_id = recruiter.id
        slot.city_id = city.id
        slot.start_utc = start_utc
        if payload.duration_min is not None:
            slot.duration_min = max(int(payload.duration_min), 1)

        await session.commit()
        await session.refresh(slot)

    return _slot_payload(slot, tz_name)


@router.get("/{slot_id}")
async def slots_api_detail(slot_id: int):
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Slot not found")

        tz_name: Optional[str] = None
        if slot.city_id is not None:
            city = await session.get(City, slot.city_id)
            if city is not None:
                try:
                    tz_name = validate_timezone_name(city.tz)
                except ValueError:
                    tz_name = None

    return _slot_payload(slot, tz_name)


@router.post("/{slot_id}/delete")
async def slots_delete_form(slot_id: int, force: Optional[str] = Form(default=None)):
    force_flag = str(force).lower() not in {"", "none", "0", "false"}
    ok, error = await delete_slot(slot_id, force=force_flag)
    response = RedirectResponse(url="/slots", status_code=303)
    if ok:
        _set_flash(response, "success", "Слот удалён")
    else:
        _set_flash(response, "error", error or "Не удалось удалить слот.")
    return response


@router.delete("/{slot_id}")
async def slots_delete(slot_id: int, force: Optional[bool] = Query(default=False)):
    ok, error = await delete_slot(slot_id, force=bool(force))
    if ok:
        return JSONResponse({"ok": True, "message": "Слот удалён"})
    payload: Dict[str, object] = {"ok": False, "message": error or "Не удалось удалить слот."}
    if error and "Нельзя удалить" in error:
        payload["code"] = "requires_force"
    status_code = 404 if error == "Слот не найден" else 400
    return JSONResponse(payload, status_code=status_code)


class BulkDeletePayload(BaseModel):
    force: Optional[bool] = False


@router.post("/delete_all")
async def slots_delete_all(payload: BulkDeletePayload):
    deleted, remaining = await delete_all_slots(force=bool(payload.force))
    return JSONResponse({"ok": True, "deleted": deleted, "remaining": remaining})


class OutcomePayload(BaseModel):
    outcome: str


@router.post("/{slot_id}/outcome")
async def slots_set_outcome(
    slot_id: int,
    payload: OutcomePayload,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
):
    ok, message, stored, dispatch = await set_slot_outcome(
        slot_id,
        payload.outcome,
        bot_service=bot_service,
    )
    status_code = 200
    bot_status = dispatch.status if dispatch is not None else "skipped:not_applicable"
    if ok and dispatch and dispatch.plan is not None:
        background_tasks.add_task(execute_bot_dispatch, dispatch.plan, stored or "", bot_service)
    if not ok:
        if message and "не найден" in message.lower():
            status_code = 404
        else:
            status_code = 400
    response = JSONResponse(
        {"ok": ok, "message": message, "outcome": stored},
        status_code=status_code,
    )
    response.headers["X-Bot"] = bot_status
    return response


@router.post("/{slot_id}/reschedule")
async def slots_reschedule(slot_id: int):
    ok, message, notified = await reschedule_slot_booking(slot_id)
    status_code = 200 if ok else (404 if "не найден" in message.lower() else 400)
    return JSONResponse(
        {"ok": ok, "message": message, "bot_notified": notified},
        status_code=status_code,
    )


@router.post("/{slot_id}/reject_booking")
async def slots_reject_booking(slot_id: int):
    ok, message, notified = await reject_slot_booking(slot_id)
    status_code = 200 if ok else (404 if "не найден" in message.lower() else 400)
    return JSONResponse(
        {"ok": ok, "message": message, "bot_notified": notified},
        status_code=status_code,
    )
