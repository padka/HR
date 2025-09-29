from collections import Counter
import base64
import hashlib
import hmac
import json
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.apps.admin_ui.services.slots import (
    bulk_create_slots,
    create_slot,
    list_slots,
    recruiters_for_slot_form,
    delete_slot,
    set_slot_outcome,
)
from backend.apps.admin_ui.utils import norm_status, parse_optional_int, status_filter
from backend.core.settings import get_settings

router = APIRouter(prefix="/slots", tags=["slots"])

_FLASH_COOKIE = "admin_flash"
_SECRET = get_settings().session_secret.encode()


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
        httponly=False,
        samesite="lax",
    )


@router.get("", response_class=HTMLResponse)
async def slots_list(
    request: Request,
    recruiter_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    recruiter = parse_optional_int(recruiter_id)
    status_norm = status_filter(status)
    result = await list_slots(recruiter, status_norm, page, per_page)
    recruiter_rows = await list_recruiters()
    recruiter_options = [row["rec"] for row in recruiter_rows]
    slots = result["items"]
    status_counter: Counter[str] = Counter()
    for slot in slots:
        status_counter[norm_status(slot.status)] += 1
    status_counts: Dict[str, int] = {
        "total": len(slots),
        "FREE": status_counter.get("FREE", 0),
        "PENDING": status_counter.get("PENDING", 0),
        "BOOKED": status_counter.get("BOOKED", 0),
    }
    flash = _pop_flash(request)
    context = {
        "request": request,
        "slots": slots,
        "filter_recruiter_id": recruiter,
        "filter_status": status_norm,
        "page": result["page"],
        "pages_total": result["pages_total"],
        "per_page": per_page,
        "recruiter_options": recruiter_options,
        "status_counts": status_counts,
        "flash": flash,
    }
    response = templates.TemplateResponse("slots_list.html", context)
    if flash:
        response.delete_cookie(_FLASH_COOKIE, path="/")
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
        response.delete_cookie(_FLASH_COOKIE, path="/")
    return response


@router.post("/create")
async def slots_create(
    recruiter_id: int = Form(...),
    city_id: int = Form(...),
    date: str = Form(...),
    time: str = Form(...),
):
    ok = await create_slot(recruiter_id, date, time, city_id=city_id)
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


@router.post("/{slot_id}/delete")
async def slots_delete_form(slot_id: int):
    ok, error = await delete_slot(slot_id)
    response = RedirectResponse(url="/slots", status_code=303)
    if ok:
        _set_flash(response, "success", "Слот удалён")
    else:
        _set_flash(response, "error", error or "Не удалось удалить слот.")
    return response


@router.delete("/{slot_id}")
async def slots_delete(slot_id: int):
    ok, error = await delete_slot(slot_id)
    if ok:
        return JSONResponse({"ok": True, "message": "Слот удалён"})
    status_code = 404 if error == "Слот не найден" else 400
    return JSONResponse({"ok": False, "message": error or "Не удалось удалить слот."}, status_code=status_code)


class OutcomePayload(BaseModel):
    outcome: str


@router.post("/{slot_id}/outcome")
async def slots_set_outcome(
    slot_id: int,
    payload: OutcomePayload,
    bot_service: BotService = Depends(provide_bot_service),
):
    ok, message, stored = await set_slot_outcome(
        slot_id,
        payload.outcome,
        bot_service=bot_service,
    )
    status_code = 200
    if not ok:
        if message and "не найден" in message.lower():
            status_code = 404
        elif message and "бот недоступен" in message.lower():
            status_code = 503
        else:
            status_code = 400
    return JSONResponse(
        {"ok": ok, "message": message, "outcome": stored},
        status_code=status_code,
    )
