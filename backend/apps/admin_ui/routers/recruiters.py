from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.cities import list_cities
from backend.apps.admin_ui.services.recruiters import (
    create_recruiter,
    delete_recruiter,
    empty_recruiter_form_data,
    get_recruiter_detail,
    list_recruiters,
    parse_recruiter_form,
    update_recruiter,
)

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
        "form_data": empty_recruiter_form_data(),
        "form_errors": [],
    }
    return templates.TemplateResponse("recruiters_new.html", context)


@router.post("/create")
async def recruiters_create(request: Request):
    form = await request.form()
    result = parse_recruiter_form(form)
    if result.errors or result.payload is None:
        cities = await list_cities()
        context = {
            "request": request,
            "cities": cities,
            "form_data": result.form_data,
            "form_errors": result.errors,
        }
        return templates.TemplateResponse("recruiters_new.html", context, status_code=400)

    await create_recruiter(result.payload, cities=result.cities_raw or None)
    return RedirectResponse(url="/recruiters", status_code=303)


@router.get("/{rec_id}/edit", response_class=HTMLResponse)
async def recruiters_edit(request: Request, rec_id: int):
    data = await get_recruiter_detail(rec_id)
    if not data:
        return RedirectResponse(url="/recruiters", status_code=303)
    context = {
        "request": request,
        **data,
        "form_errors": [],
        "form_data": {
            "name": data["recruiter"].name,
            "tz": getattr(data["recruiter"], "tz", None) or empty_recruiter_form_data()["tz"],
            "telemost": getattr(data["recruiter"], "telemost_url", None) or "",
            "tg_chat_id": str(getattr(data["recruiter"], "tg_chat_id", "") or ""),
            "active": bool(getattr(data["recruiter"], "active", True)),
            "city_ids": data.get("selected_ids", set()),
        },
    }
    return templates.TemplateResponse("recruiters_edit.html", context)


@router.post("/{rec_id}/update")
async def recruiters_update(request: Request, rec_id: int):
    form = await request.form()
    result = parse_recruiter_form(form)
    if result.errors or result.payload is None:
        data = await get_recruiter_detail(rec_id)
        if not data:
            return RedirectResponse(url="/recruiters", status_code=303)
        context = {
            "request": request,
            **data,
            "form_errors": result.errors,
            "form_data": result.form_data,
        }
        return templates.TemplateResponse("recruiters_edit.html", context, status_code=400)

    await update_recruiter(rec_id, result.payload, cities=result.cities_raw or None)
    return RedirectResponse(url="/recruiters", status_code=303)


@router.post("/{rec_id}/delete")
async def recruiters_delete(rec_id: int):
    await delete_recruiter(rec_id)
    return RedirectResponse(url="/recruiters", status_code=303)
