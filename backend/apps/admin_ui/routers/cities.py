from typing import Dict, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.cities import (
    create_city,
    list_cities,
    update_city_settings as update_city_settings_service,
    delete_city,
    normalize_city_timezone,
)
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.apps.admin_ui.services.templates import (
    get_stage_templates,
    stage_payload_for_ui,
)
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.template_stages import CITY_TEMPLATE_STAGES, STAGE_DEFAULTS

router = APIRouter(prefix="/cities", tags=["cities"])

PLAN_ERROR_MESSAGE = "Введите целое неотрицательное число"


def _primary_recruiter(city) -> Optional[object]:
    recruiters = getattr(city, "recruiters", None)
    if not recruiters:
        return None
    for recruiter in recruiters:
        if recruiter is not None:
            return recruiter
    return None


def _primary_recruiter_id(city) -> Optional[int]:
    recruiter = _primary_recruiter(city)
    return recruiter.id if recruiter else None


def _parse_plan_value(raw: object) -> Optional[int]:
    if raw is None:
        return None
    if isinstance(raw, str):
        value = raw.strip()
        if value == "" or value.lower() == "null":
            return None
        if not value.isdigit():
            raise ValueError
        number = int(value)
    elif isinstance(raw, bool):
        raise ValueError
    elif isinstance(raw, int):
        number = raw
    else:
        raise ValueError
    if number < 0:
        raise ValueError
    return number


@router.get("", response_class=HTMLResponse)
async def cities_list(request: Request):
    cities = await list_cities()
    recruiter_rows = await list_recruiters()
    recruiters = [row["rec"] for row in recruiter_rows]
    owners = {city.id: _primary_recruiter_id(city) for city in cities}
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
    request: Request,
    name: str = Form(...),
    tz: str = Form("Europe/Moscow"),
):
    tz_value = (tz or "Europe/Moscow").strip()
    try:
        normalized_tz = normalize_city_timezone(tz_value)
    except ValueError as exc:
        context = {
            "request": request,
            "form_error": str(exc),
            "form_data": {"name": (name or "").strip(), "tz": tz_value or ""},
        }
        return templates.TemplateResponse("cities_new.html", context, status_code=422)

    try:
        await create_city(name, normalized_tz)
    except ValueError as exc:
        context = {
            "request": request,
            "form_error": str(exc),
            "form_data": {"name": (name or "").strip(), "tz": tz_value or ""},
        }
        return templates.TemplateResponse("cities_new.html", context, status_code=422)
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

    criteria = (payload.get("criteria") or "").strip()
    experts = (payload.get("experts") or "").strip()
    try:
        plan_week = _parse_plan_value(payload.get("plan_week"))
    except ValueError:
        return JSONResponse(
            {"ok": False, "error": {"field": "plan_week", "message": PLAN_ERROR_MESSAGE}},
            status_code=422,
        )
    try:
        plan_month = _parse_plan_value(payload.get("plan_month"))
    except ValueError:
        return JSONResponse(
            {"ok": False, "error": {"field": "plan_month", "message": PLAN_ERROR_MESSAGE}},
            status_code=422,
        )

    error, city, owner = await update_city_settings_service(
        city_id,
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
    effective_owner = owner or (_primary_recruiter(city) if city else None)
    owner_id = effective_owner.id if effective_owner else None
    city_payload: Dict[str, object] = {
        "id": city.id if city else city_id,
        "name": city.name_plain if city else "",
        "name_html": sanitize_plain_text(city.name_plain) if city else "",
        "tz": getattr(city, "tz", None) if city else None,
        "criteria": getattr(city, "criteria", None) if city else None,
        "experts": getattr(city, "experts", None) if city else None,
        "plan_week": getattr(city, "plan_week", None) if city else None,
        "plan_month": getattr(city, "plan_month", None) if city else None,
        "responsible_recruiter_id": owner_id,
    }
    if effective_owner:
        city_payload["responsible_recruiter"] = {
            "id": effective_owner.id,
            "name": effective_owner.name,
            "tz": getattr(effective_owner, "tz", None),
        }
    else:
        city_payload["responsible_recruiter"] = None

    return JSONResponse({"ok": True, "city": city_payload})


@router.post("/{city_id}/delete")
async def cities_delete(city_id: int):
    ok = await delete_city(city_id)
    if not ok:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return JSONResponse({"ok": True})
