from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui import services

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("", response_class=HTMLResponse)
async def cities_list(request: Request):
    cities = await services.list_cities()
    owner_field = services.city_owner_field_name()
    recruiters = await services.list_recruiters()
    owners = {c.id: getattr(c, owner_field, None) if owner_field else None for c in cities}
    rec_map = {r.id: r for r in recruiters}
    context = {
        "request": request,
        "cities": cities,
        "owner_field": owner_field,
        "owners": owners,
        "rec_map": rec_map,
    }
    return templates.TemplateResponse("cities_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def cities_new(request: Request):
    return templates.TemplateResponse("cities_new.html", {"request": request})


@router.post("/create")
async def cities_create(
    name: str = Form(...),
    tz: str = Form("Europe/Moscow"),
):
    await services.create_city(name, tz)
    return RedirectResponse(url="/cities", status_code=303)


@router.get("/owners", response_class=HTMLResponse)
async def cities_owners_board(request: Request):
    owner_field = services.city_owner_field_name()
    recruiters = await services.list_recruiters()
    cities = await services.list_cities()
    owners = {
        c.id: getattr(c, owner_field, None) if owner_field else None
        for c in cities
    }
    context = {
        "request": request,
        "recruiters": recruiters,
        "cities": cities,
        "owner_field_exists": owner_field is not None,
        "owner_field": owner_field,
        "owners": owners,
    }
    return templates.TemplateResponse("cities_owners.html", context)


@router.post("/owners/assign")
async def cities_owner_assign(request: Request):
    payload = await request.json()
    try:
        city_id = int(payload.get("city_id"))
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid payload"}, status_code=400)

    recruiter_raw = payload.get("recruiter_id")
    recruiter_id: Optional[int]
    if recruiter_raw in (None, "", "null"):
        recruiter_id = None
    else:
        try:
            recruiter_id = int(recruiter_raw)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "Invalid recruiter id"}, status_code=400)

    error = await services.assign_city_owner(city_id, recruiter_id)
    if error:
        status = 404 if "not found" in error.lower() else 400
        return JSONResponse({"ok": False, "error": error}, status_code=status)
    return JSONResponse({"ok": True})
