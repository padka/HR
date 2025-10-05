from typing import Dict, Optional, List

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.cities import list_cities
from backend.apps.admin_ui.services.recruiters import (
    build_recruiter_payload,
    create_recruiter,
    delete_recruiter,
    get_recruiter_detail,
    list_recruiters,
    update_recruiter,
)
from backend.apps.admin_ui.timezones import DEFAULT_TZ, timezone_options

router = APIRouter(prefix="/recruiters", tags=["recruiters"])


@router.get("", response_class=HTMLResponse)
async def recruiters_list(request: Request):
    recruiter_rows = await list_recruiters()
    context = {
        "request": request,
        "recruiter_rows": recruiter_rows,
    }
    return templates.TemplateResponse("recruiters_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def recruiters_new(request: Request):
    cities = await list_cities()
    context = {
        "request": request,
        "cities": cities,
        "tz_options": timezone_options(),
    }
    return templates.TemplateResponse("recruiters_new.html", context)


@router.post("/create")
async def recruiters_create(
    request: Request,
    name: str = Form(...),
    tz: str = Form(DEFAULT_TZ),
    telemost: str = Form(""),
    tg_chat_id: str = Form(""),
    active: Optional[str] = Form(None),
    cities: Optional[List[str]] = Form(None),
):
    tz_value = (tz or DEFAULT_TZ).strip() or DEFAULT_TZ
    payload: Dict[str, object] = build_recruiter_payload(
        name=name,
        tz=tz_value,
        telemost=telemost,
        tg_chat_id=tg_chat_id,
        active=active,
    )
    form_state = {
        "name": name,
        "tz": tz_value,
        "telemost": telemost,
        "tg_chat_id": tg_chat_id,
        "active": bool(active),
        "cities": [int(cid.strip()) for cid in (cities or []) if cid and cid.strip().isdigit()],
    }
    result = await create_recruiter(payload, cities=cities)
    if not result.get("ok"):
        cities_list = await list_cities()
        context = {
            "request": request,
            "cities": cities_list,
            "tz_options": timezone_options(),
            "form_error": result.get("error", {}).get("message"),
            "error_field": result.get("error", {}).get("field"),
            "form_data": form_state,
        }
        return templates.TemplateResponse("recruiters_new.html", context, status_code=400)

    return RedirectResponse(url="/recruiters", status_code=303)


@router.get("/{rec_id}/edit", response_class=HTMLResponse)
async def recruiters_edit(request: Request, rec_id: int):
    data = await get_recruiter_detail(rec_id)
    if not data:
        return RedirectResponse(url="/recruiters", status_code=303)
    tz_current = getattr(data.get("recruiter"), "tz", None) if data else None
    context = {
        "request": request,
        **data,
        "tz_options": timezone_options(include_extra=[tz_current] if tz_current else None),
    }
    return templates.TemplateResponse("recruiters_edit.html", context)


@router.post("/{rec_id}/update")
async def recruiters_update(
    request: Request,
    rec_id: int,
    name: str = Form(...),
    tz: str = Form(DEFAULT_TZ),
    telemost: str = Form(""),
    tg_chat_id: str = Form(""),
    active: Optional[str] = Form(None),
    cities: Optional[List[str]] = Form(None),
):
    tz_value = (tz or DEFAULT_TZ).strip() or DEFAULT_TZ
    payload: Dict[str, object] = build_recruiter_payload(
        name=name,
        tz=tz_value,
        telemost=telemost,
        tg_chat_id=tg_chat_id,
        active=active,
    )
    form_state = {
        "name": name,
        "tz": tz_value,
        "telemost": telemost,
        "tg_chat_id": tg_chat_id,
        "active": bool(active) if active is not None else False,
        "cities": [int(cid.strip()) for cid in (cities or []) if cid and cid.strip().isdigit()],
    }
    result = await update_recruiter(rec_id, payload, cities=cities)
    if not result.get("ok"):
        error = result.get("error", {})
        if error.get("type") == "not_found":
            return RedirectResponse(url="/recruiters", status_code=303)
        data = await get_recruiter_detail(rec_id)
        if not data:
            return RedirectResponse(url="/recruiters", status_code=303)
        tz_current = getattr(data.get("recruiter"), "tz", None) if data else None
        context = {
            "request": request,
            **data,
            "tz_options": timezone_options(include_extra=[tz_current] if tz_current else None),
            "form_error": error.get("message"),
            "error_field": error.get("field"),
            "form_data": form_state,
        }
        return templates.TemplateResponse("recruiters_edit.html", context, status_code=400)

    return RedirectResponse(url="/recruiters", status_code=303)


@router.post("/{rec_id}/delete")
async def recruiters_delete(rec_id: int):
    await delete_recruiter(rec_id)
    return RedirectResponse(url="/recruiters", status_code=303)
