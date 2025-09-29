from collections import Counter
from typing import Dict, Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.apps.admin_ui.services.slots import (
    bulk_create_slots,
    create_slot,
    list_slots,
    recruiters_for_slot_form,
)
from backend.apps.admin_ui.utils import norm_status, parse_optional_int, status_filter

router = APIRouter(prefix="/slots", tags=["slots"])


def _parse_checkbox(value: Optional[str]) -> bool:
    return value not in (None, "", "0", "false", "False")


def _pop_flash(request: Request) -> Optional[Dict[str, str]]:
    if hasattr(request, "session"):
        return request.session.pop("flash", None)
    return None


def _set_flash(request: Request, status: str, message: str) -> None:
    if hasattr(request, "session"):
        request.session["flash"] = {"status": status, "message": message}


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
    return templates.TemplateResponse("slots_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def slots_new(request: Request):
    recruiters = await recruiters_for_slot_form()
    flash = _pop_flash(request)
    return templates.TemplateResponse(
        "slots_new.html",
        {"request": request, "recruiters": recruiters, "flash": flash},
    )


@router.post("/create")
async def slots_create(
    recruiter_id: int = Form(...),
    date: str = Form(...),
    time: str = Form(...),
):
    ok = await create_slot(recruiter_id, date, time)
    redirect = "/slots" if ok else "/slots/new"
    return RedirectResponse(url=redirect, status_code=303)


@router.post("/bulk_create")
async def slots_bulk_create(
    request: Request,
    recruiter_id: int = Form(...),
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

    if error:
        _set_flash(request, "error", error)
    elif created == 0:
        _set_flash(request, "info", "Новые слоты не созданы — все уже существуют.")
    else:
        _set_flash(request, "success", f"Создано {created} слот(ов).")

    return RedirectResponse(url="/slots", status_code=303)
