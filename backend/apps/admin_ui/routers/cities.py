from typing import Dict, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.cities import (
    create_city,
    get_city,
    list_cities,
    update_city_settings as update_city_settings_service,
    update_city_owner as update_city_owner_service,
    set_city_active as set_city_active_service,
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


def _coerce_bool(raw: object) -> Optional[bool]:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value == "":
            return None
        if value in {"1", "true", "yes", "on", "active"}:
            return True
        if value in {"0", "false", "no", "off", "inactive"}:
            return False
    raise ValueError


def _build_city_form_state(
    city,
    owner_id: Optional[int],
    city_templates: Dict[str, str],
    overrides: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    recruiter_ids = [rec.id for rec in (city.recruiters or [])]
    state: Dict[str, object] = {
        "name": city.name_plain,
        "responsible_recruiter_id": str(owner_id) if owner_id is not None else "",
        "recruiter_ids": recruiter_ids,
        "criteria": city.criteria or "",
        "experts": city.experts or "",
        "plan_week": "" if city.plan_week is None else str(city.plan_week),
        "plan_month": "" if city.plan_month is None else str(city.plan_month),
        "tz": city.tz or "Europe/Moscow",
        "active": bool(city.active),
        "templates": dict(city_templates),
    }
    if overrides:
        for key, value in overrides.items():
            if key == "templates":
                state["templates"] = dict(value or {})
            else:
                state[key] = value
    return state


async def _prepare_city_edit_context(
    city_id: int,
    request: Request,
    *,
    form_state: Optional[Dict[str, object]] = None,
    form_error: Optional[str] = None,
    success_message: Optional[str] = None,
) -> Dict[str, object]:
    city = await get_city(city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    stage_map = await get_stage_templates(city_ids=[city_id], include_global=True)
    recruiter_rows = await list_recruiters()
    owner_id = _primary_recruiter_id(city)
    city_templates = stage_map.get(city.id, {})
    rec_map = {row["rec"].id: row["rec"] for row in recruiter_rows if row.get("rec")}
    owner_lookup = rec_map.get(owner_id)

    context = {
        "request": request,
        "city": city,
        "form_state": _build_city_form_state(city, owner_id, city_templates, overrides=form_state),
        "form_error": form_error,
        "success_message": success_message,
        "stage_meta": CITY_TEMPLATE_STAGES,
        "global_templates": stage_map.get(None, {}),
        "recruiter_rows": recruiter_rows,
        "owner_lookup": owner_lookup,
    }
    return context


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
        "city_count": len(cities),
        "owners": owners,
        "rec_map": rec_map,
        "recruiter_rows": recruiter_rows,
        "recruiters": recruiters,
        "stage_meta": CITY_TEMPLATE_STAGES,
        "city_stages": city_stages,
        "global_defaults": {key: STAGE_DEFAULTS[key] for key in STAGE_DEFAULTS},
    }
    return templates.TemplateResponse(request, "cities_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def cities_new(request: Request):
    return templates.TemplateResponse(request, "cities_new.html", {"request": request})


@router.get("/{city_id}/edit", response_class=HTMLResponse)
async def cities_edit_page(city_id: int, request: Request):
    success = None
    if request.query_params.get("saved") == "1":
        success = "Настройки города обновлены"
    context = await _prepare_city_edit_context(
        city_id,
        request,
        success_message=success,
    )
    return templates.TemplateResponse(request, "cities_edit.html", context)


@router.post("/{city_id}/edit", response_class=HTMLResponse)
async def cities_edit_submit(city_id: int, request: Request):
    form = await request.form()
    form_data = dict(form)

    recruiter_ids_raw = form.getlist("recruiter_ids") if hasattr(form, "getlist") else []
    recruiter_ids: List[int] = []
    for raw_id in recruiter_ids_raw:
        try:
            recruiter_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    override_state = {
        "name": form_data.get("name", ""),
        "recruiter_ids": recruiter_ids,
        "criteria": form_data.get("criteria", ""),
        "experts": form_data.get("experts", ""),
        "plan_week": form_data.get("plan_week", ""),
        "plan_month": form_data.get("plan_month", ""),
        "tz": form_data.get("tz", ""),
        "active": bool(form_data.get("active")),
        "templates": {
            stage.key: form_data.get(f"template_{stage.key}", "")
            for stage in CITY_TEMPLATE_STAGES
        },
    }

    name_raw = (form_data.get("name") or "").strip()
    name_clean = sanitize_plain_text(name_raw)
    if not name_clean:
        context = await _prepare_city_edit_context(
            city_id,
            request,
            form_state=override_state,
            form_error="Название города не может быть пустым",
        )
        return templates.TemplateResponse(request, "cities_edit.html", context, status_code=400)

    try:
        plan_week = _parse_plan_value(form_data.get("plan_week"))
    except ValueError:
        context = await _prepare_city_edit_context(
            city_id,
            request,
            form_state=override_state,
            form_error="Неделя: " + PLAN_ERROR_MESSAGE,
        )
        return templates.TemplateResponse(request, "cities_edit.html", context, status_code=422)

    try:
        plan_month = _parse_plan_value(form_data.get("plan_month"))
    except ValueError:
        context = await _prepare_city_edit_context(
            city_id,
            request,
            form_state=override_state,
            form_error="Месяц: " + PLAN_ERROR_MESSAGE,
        )
        return templates.TemplateResponse(request, "cities_edit.html", context, status_code=422)

    tz_value = (form_data.get("tz") or "").strip()
    if not tz_value:
        context = await _prepare_city_edit_context(
            city_id,
            request,
            form_state=override_state,
            form_error="Укажите часовой пояс города",
        )
        return templates.TemplateResponse(request, "cities_edit.html", context, status_code=400)

    criteria = (form_data.get("criteria") or "").strip()
    experts = (form_data.get("experts") or "").strip()
    templates_payload = override_state["templates"]

    error, _, _ = await update_city_settings_service(
        city_id,
        name=name_clean,
        recruiter_ids=recruiter_ids,
        templates=templates_payload,
        criteria=criteria,
        experts=experts,
        plan_week=plan_week,
        plan_month=plan_month,
        tz=tz_value,
        active=bool(form_data.get("active")),
    )
    if error:
        context = await _prepare_city_edit_context(
            city_id,
            request,
            form_state=override_state,
            form_error=error,
        )
        return templates.TemplateResponse(request, "cities_edit.html", context, status_code=400)

    return RedirectResponse(url=f"/cities/{city_id}/edit?saved=1", status_code=303)


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
        return templates.TemplateResponse(request, "cities_new.html", context, status_code=422)

    try:
        await create_city(name, normalized_tz)
    except ValueError as exc:
        context = {
            "request": request,
            "form_error": str(exc),
            "form_data": {"name": (name or "").strip(), "tz": tz_value or ""},
        }
        return templates.TemplateResponse(request, "cities_new.html", context, status_code=422)
    return RedirectResponse(url="/cities", status_code=303)


@router.post("/{city_id}/settings")
async def update_city_settings(city_id: int, request: Request):
    payload = await request.json()
    name_raw = (payload.get("name") or "").strip()
    name_clean = sanitize_plain_text(name_raw) if name_raw else None
    if name_raw and not name_clean:
        return JSONResponse({"ok": False, "error": {"field": "name", "message": "Название города не может быть пустым"}}, status_code=422)
    recruiter_ids_payload = payload.get("recruiter_ids")
    recruiter_ids: List[int] = []
    if recruiter_ids_payload is None:
        recruiter_raw = payload.get("responsible_recruiter_id")
        if recruiter_raw not in (None, "", "null"):
            try:
                recruiter_ids = [int(recruiter_raw)]
            except (TypeError, ValueError):
                return JSONResponse({"ok": False, "error": "invalid_recruiter"}, status_code=400)
    else:
        if not isinstance(recruiter_ids_payload, list):
            return JSONResponse({"ok": False, "error": "invalid_recruiter_ids"}, status_code=400)
        for raw in recruiter_ids_payload:
            try:
                recruiter_ids.append(int(raw))
            except (TypeError, ValueError):
                continue

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

    tz_normalized: Optional[str] = None
    if "tz" in payload:
        try:
            tz_normalized = normalize_city_timezone(payload.get("tz"))
        except ValueError as exc:
            return JSONResponse(
                {"ok": False, "error": {"field": "tz", "message": str(exc)}},
                status_code=422,
            )

    try:
        active_value = _coerce_bool(payload.get("active"))
    except ValueError:
        return JSONResponse(
            {
                "ok": False,
                "error": {"field": "active", "message": "Укажите корректный статус активности"},
            },
            status_code=422,
        )

    error, city, owner = await update_city_settings_service(
        city_id,
        recruiter_ids=recruiter_ids,
        templates=templates_payload,
        criteria=criteria,
        experts=experts,
        plan_week=plan_week,
        plan_month=plan_month,
        tz=tz_normalized,
        active=active_value,
        name=name_clean,
    )
    if error:
        status = 404 if "not found" in error.lower() else 400
        return JSONResponse({"ok": False, "error": error}, status_code=status)
    effective_owner = owner or (_primary_recruiter(city) if city else None)
    owner_id = effective_owner.id if effective_owner else None
    recruiter_ids_resp = [rec.id for rec in getattr(city, "recruiters", [])] if city else []
    city_payload: Dict[str, object] = {
        "id": city.id if city else city_id,
        "name": city.name_plain if city else "",
        "name_html": sanitize_plain_text(city.name_plain) if city else "",
        "tz": getattr(city, "tz", None) if city else None,
        "active": getattr(city, "active", None) if city else None,
        "criteria": getattr(city, "criteria", None) if city else None,
        "experts": getattr(city, "experts", None) if city else None,
        "plan_week": getattr(city, "plan_week", None) if city else None,
        "plan_month": getattr(city, "plan_month", None) if city else None,
        "recruiter_ids": recruiter_ids_resp,
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


@router.post("/{city_id}/owner")
async def update_city_owner(city_id: int, request: Request):
    payload = await request.json()
    recruiter_raw = payload.get("responsible_id")
    if recruiter_raw in (None, "", "null"):
        responsible_id: Optional[int] = None
    else:
        try:
            responsible_id = int(recruiter_raw)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "invalid_recruiter"}, status_code=400)

    error, city, owner = await update_city_owner_service(city_id, responsible_id)
    if error:
        status_code = 404 if "City not found" in error else 400
        return JSONResponse({"ok": False, "error": error}, status_code=status_code)

    owner_payload = {"id": owner.id, "name": owner.name} if owner else None
    return JSONResponse(
        {
            "ok": True,
            "city": {
                "id": city.id,
                "active": city.active,
                "responsible_recruiter_id": owner.id if owner else None,
                "responsible_recruiter": owner_payload,
            },
            "owner": owner_payload,
        }
    )


@router.post("/{city_id}/status")
async def update_city_status_api(city_id: int, request: Request):
    payload = await request.json()
    try:
        active_value = _coerce_bool(payload.get("active"))
    except ValueError:
        return JSONResponse(
            {
                "ok": False,
                "error": {"field": "active", "message": "Укажите корректный статус"},
            },
            status_code=422,
        )
    if active_value is None:
        return JSONResponse(
            {
                "ok": False,
                "error": {"field": "active", "message": "Укажите корректный статус"},
            },
            status_code=422,
        )

    error, city = await set_city_active_service(city_id, active_value)
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=404)
    return JSONResponse({"ok": True, "city": {"id": city.id, "active": city.active}})


@router.post("/{city_id}/delete")
async def cities_delete(city_id: int, request: Request):
    ok = await delete_city(city_id)
    wants_json = "application/json" in (request.headers.get("accept") or "").lower()
    if not ok:
        if wants_json:
            return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
        return RedirectResponse(url="/cities?deleted=0", status_code=303)
    if wants_json:
        return JSONResponse({"ok": True})
    return RedirectResponse(url="/cities?deleted=1", status_code=303)
