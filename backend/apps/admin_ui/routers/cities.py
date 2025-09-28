from typing import Dict, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui import services
from backend.domain.template_stages import CITY_TEMPLATE_STAGES, STAGE_DEFAULTS

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("", response_class=HTMLResponse)
async def cities_list(request: Request):
    cities = await services.list_cities()
    owner_field = services.city_owner_field_name()
    recruiters = await services.list_recruiters()
    owners = {c.id: getattr(c, owner_field, None) if owner_field else None for c in cities}
    rec_map = {r.id: r for r in recruiters}
    stage_map = await services.get_stage_templates(
        city_ids=[c.id for c in cities], include_global=True
    )
    city_stages: Dict[int, object] = {
        city.id: services.stage_payload_for_ui(stage_map.get(city.id, {})) for city in cities
    }
    context = {
        "request": request,
        "cities": cities,
        "owner_field": owner_field,
        "owners": owners,
        "rec_map": rec_map,
        "recruiters": recruiters,
        "stage_meta": CITY_TEMPLATE_STAGES,
        "city_stages": city_stages,
        "global_defaults": {key: STAGE_DEFAULTS[key] for key in STAGE_DEFAULTS},
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


@router.post("/{city_id}/settings")
async def update_city_settings(city_id: int, request: Request):
    payload = await request.json()
    recruiter_raw = payload.get("responsible_recruiter_id")
    if recruiter_raw in (None, "", "null"):
        responsible_id: Optional[int] = None
    else:
        try:
            responsible_id = int(recruiter_raw)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "invalid_recruiter"}, status_code=400)

    templates_payload = payload.get("templates") or {}
    if not isinstance(templates_payload, dict):
        templates_payload = {}

    error = await services.update_city_settings(
        city_id,
        responsible_id=responsible_id,
        templates=templates_payload,
    )
    if error:
        status = 404 if "not found" in error.lower() else 400
        return JSONResponse({"ok": False, "error": error}, status_code=status)
    return JSONResponse({"ok": True})
