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

router = APIRouter(prefix="/recruiters", tags=["recruiters"])


@router.get("", response_class=HTMLResponse)
async def recruiters_list(request: Request):
    recruiters = await list_recruiters()
    return templates.TemplateResponse("recruiters_list.html", {"request": request, "recruiters": recruiters})


@router.get("/new", response_class=HTMLResponse)
async def recruiters_new(request: Request):
    cities = await list_cities()
    return templates.TemplateResponse("recruiters_new.html", {"request": request, "cities": cities})


@router.post("/create")
async def recruiters_create(
    name: str = Form(...),
    tz: str = Form("Europe/Moscow"),
    telemost: str = Form(""),
    tg_chat_id: str = Form(""),
    active: Optional[str] = Form(None),
    cities: Optional[List[str]] = Form(None),
):
    payload: Dict[str, object] = build_recruiter_payload(
        name=name,
        tz=tz,
        telemost=telemost,
        tg_chat_id=tg_chat_id,
        active=active,
    )
    await create_recruiter(payload, cities=cities)
    return RedirectResponse(url="/recruiters", status_code=303)


@router.get("/{rec_id}/edit", response_class=HTMLResponse)
async def recruiters_edit(request: Request, rec_id: int):
    data = await get_recruiter_detail(rec_id)
    if not data:
        return RedirectResponse(url="/recruiters", status_code=303)
    return templates.TemplateResponse("recruiters_edit.html", {"request": request, **data})


@router.post("/{rec_id}/update")
async def recruiters_update(
    rec_id: int,
    name: str = Form(...),
    tz: str = Form("Europe/Moscow"),
    telemost: str = Form(""),
    tg_chat_id: str = Form(""),
    active: Optional[str] = Form(None),
    cities: Optional[List[str]] = Form(None),
):
    payload: Dict[str, object] = build_recruiter_payload(
        name=name,
        tz=tz,
        telemost=telemost,
        tg_chat_id=tg_chat_id,
        active=active,
    )
    await update_recruiter(rec_id, payload, cities=cities)
    return RedirectResponse(url="/recruiters", status_code=303)


@router.post("/{rec_id}/delete")
async def recruiters_delete(rec_id: int):
    await delete_recruiter(rec_id)
    return RedirectResponse(url="/recruiters", status_code=303)
