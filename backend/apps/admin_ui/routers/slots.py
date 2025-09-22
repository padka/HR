from typing import Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui import services
from backend.apps.admin_ui.utils import parse_optional_int, status_filter

router = APIRouter(prefix="/slots", tags=["slots"])


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
    result = await services.list_slots(recruiter, status_norm, page, per_page)
    recruiters = await services.list_recruiters()
    context = {
        "request": request,
        "slots": result["items"],
        "filter_recruiter_id": recruiter,
        "filter_status": status_norm,
        "page": result["page"],
        "pages_total": result["pages_total"],
        "per_page": per_page,
        "recruiters": recruiters,
    }
    return templates.TemplateResponse("slots_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def slots_new(request: Request):
    recruiters = await services.recruiters_for_slot_form()
    return templates.TemplateResponse("slots_new.html", {"request": request, "recruiters": recruiters})


@router.post("/create")
async def slots_create(
    recruiter_id: int = Form(...),
    date: str = Form(...),
    time: str = Form(...),
):
    ok = await services.create_slot(recruiter_id, date, time)
    redirect = "/slots" if ok else "/slots/new"
    return RedirectResponse(url=redirect, status_code=303)
