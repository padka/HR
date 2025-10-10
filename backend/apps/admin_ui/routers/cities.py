from typing import Dict, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from zoneinfo import available_timezones

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.cities import (
    create_city,
    list_cities,
    city_owner_field_name,
    update_city_settings as update_city_settings_service,
    delete_city,
    get_city,
)
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.apps.admin_ui.services.templates import (
    get_stage_templates,
    stage_payload_for_ui,
)
from backend.domain.template_stages import CITY_TEMPLATE_STAGES, STAGE_DEFAULTS

router = APIRouter(prefix="/cities", tags=["cities"])


def _coerce_plan(value: object) -> Optional[int]:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


@router.get("", response_class=HTMLResponse)
async def cities_list(request: Request):
    cities = await list_cities()
    owner_field = city_owner_field_name()
    recruiter_rows = await list_recruiters()
    recruiters = [row["rec"] for row in recruiter_rows]
    owners = {c.id: getattr(c, owner_field, None) if owner_field else None for c in cities}
    rec_map = {rec.id: rec for rec in recruiters}
    stage_map = await get_stage_templates(
        city_ids=[c.id for c in cities], include_global=True
    )
    city_stages: Dict[int, object] = {
        city.id: stage_payload_for_ui(stage_map.get(city.id, {})) for city in cities
    }
    context = {
        "request": request,
        "cities": cities,
        "owner_field": owner_field,
        "owners": owners,
        "rec_map": rec_map,
        "recruiter_rows": recruiter_rows,
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
    await create_city(name, tz)
    return RedirectResponse(url="/cities", status_code=303)


@router.get("/{city_id}/edit", response_class=HTMLResponse)
async def cities_edit(city_id: int, request: Request):
    city = await get_city(city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    owner_field = city_owner_field_name()
    responsible_id = getattr(city, owner_field, None) if owner_field else None

    recruiter_rows = await list_recruiters()
    recruiters = [row["rec"] for row in recruiter_rows]

    stage_map = await get_stage_templates(city_ids=[city.id], include_global=True)
    stages = stage_payload_for_ui(stage_map.get(city.id, {}))

    timezone_options = sorted(available_timezones())

    context = {
        "request": request,
        "city": city,
        "responsible_id": responsible_id,
        "recruiters": recruiters,
        "stage_meta": CITY_TEMPLATE_STAGES,
        "stages": stages,
        "stage_defaults": {key: STAGE_DEFAULTS[key] for key in STAGE_DEFAULTS},
        "timezone_options": timezone_options,
    }
    return templates.TemplateResponse("city_edit.html", context)


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

    criteria = (payload.get("criteria") or "").strip()
    experts = (payload.get("experts") or "").strip()
    plan_week = _coerce_plan(payload.get("plan_week"))
    plan_month = _coerce_plan(payload.get("plan_month"))

    name = payload.get("name")
    tz = payload.get("tz")

    active_raw = payload.get("active")
    active_value: Optional[bool]
    if isinstance(active_raw, bool):
        active_value = active_raw
    elif isinstance(active_raw, str):
        lowered = active_raw.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            active_value = True
        elif lowered in {"false", "0", "no", "off"}:
            active_value = False
        else:
            active_value = None
    else:
        active_value = None

    error = await update_city_settings_service(
        city_id,
        name=name,
        tz=tz,
        active=active_value,
        responsible_id=responsible_id,
        templates=templates_payload,
        criteria=criteria,
        experts=experts,
        plan_week=plan_week,
        plan_month=plan_month,
    )
    if error:
        status = 404 if "not found" in error.lower() else 400
        return JSONResponse({"ok": False, "error": error}, status_code=status)
    return JSONResponse({"ok": True})


@router.post("/{city_id}/delete")
async def cities_delete(city_id: int):
    ok = await delete_city(city_id)
    if not ok:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return JSONResponse({"ok": True})
