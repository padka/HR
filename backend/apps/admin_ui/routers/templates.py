from typing import Dict, List, Optional

from types import SimpleNamespace

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.apps.admin_ui.config import templates as jinja_templates
from backend.apps.admin_ui.services.cities import list_cities
from backend.apps.admin_ui.services.templates import (
    create_template,
    delete_template,
    get_template,
    list_known_template_keys,
    list_templates,
    known_template_presets,
    notify_templates_changed,
    update_template,
    update_templates_for_city,
)
from backend.apps.admin_ui.services.message_templates import list_message_templates
from backend.apps.admin_ui.utils import parse_optional_int
from backend.domain.template_stages import CITY_TEMPLATE_STAGES

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_class=HTMLResponse)
async def templates_list(request: Request):
    # Get data for stages (old system)
    stages_data = await list_templates()

    # Get data for notifications (new system)
    notifications_data = await list_message_templates()

    context = {
        "request": request,
        **stages_data,  # overview, global, cities
        "message_templates": notifications_data["templates"],
        "missing_required": notifications_data["missing_required"],
        "known_hints": notifications_data["known_hints"],
    }
    return jinja_templates.TemplateResponse(request, "templates_unified.html", context)


@router.get("/new", response_class=HTMLResponse)
async def templates_new(request: Request):
    cities = await list_cities()
    stage_titles = {stage.key: stage.title for stage in CITY_TEMPLATE_STAGES}
    template_keys = list_known_template_keys()
    template_key_options = [
        {"key": key, "title": stage_titles.get(key)} for key in template_keys
    ]
    context = {
        "request": request,
        "cities": cities,
        "errors": [],
        "form_data": {},
        "template_keys": template_keys,
        "template_key_options": template_key_options,
        "template_presets": known_template_presets(),
    }
    return jinja_templates.TemplateResponse(request, "templates_new.html", context)


@router.post("/create")
async def templates_create(
    request: Request,
    text: str = Form(...),
    city_id: Optional[str] = Form(None),
    is_global: Optional[str] = Form(None),
):
    text_value = (text or "").strip()
    global_template = bool(is_global)
    parsed_city = parse_optional_int(city_id)
    errors: List[str] = []

    if not text_value:
        errors.append("Введите текст шаблона.")

    if not global_template:
        if parsed_city is None:
            errors.append("Выберите город или отметьте шаблон как глобальный.")
    else:
        parsed_city = None

    stage_titles = {stage.key: stage.title for stage in CITY_TEMPLATE_STAGES}
    template_keys = list_known_template_keys()
    template_key_options = [
        {"key": key, "title": stage_titles.get(key)} for key in template_keys
    ]

    if errors:
        cities = await list_cities()
        context = {
            "request": request,
            "cities": cities,
            "errors": errors,
            "form_data": {
                "text": text_value,
                "city_id": parsed_city,
                "is_global": global_template,
            },
            "template_keys": template_keys,
            "template_key_options": template_key_options,
            "template_presets": known_template_presets(),
        }
        return jinja_templates.TemplateResponse(request, "templates_new.html", context, status_code=400)

    await create_template(text_value, parsed_city)
    notify_templates_changed()
    return RedirectResponse(url="/templates", status_code=303)


@router.post("/save")
async def templates_save(request: Request):
    payload = await request.json()
    city_raw = payload.get("city_id")
    if city_raw in (None, "", "null"):
        city_id: Optional[int] = None
    else:
        try:
            city_id = int(city_raw)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "invalid_city"}, status_code=400)

    templates_payload = payload.get("templates") or {}
    if not isinstance(templates_payload, dict):
        templates_payload = {}

    error = await update_templates_for_city(city_id, templates_payload)
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    notify_templates_changed()
    return JSONResponse({"ok": True})


def _build_template_payload(
    *,
    tmpl_id: int,
    key: str,
    text: str,
    city_id: Optional[int],
    is_global: bool,
) -> Dict[str, object]:
    return {
        "id": tmpl_id,
        "key": key,
        "text_field": text,
        "city_id": city_id,
        "is_global": is_global,
    }


@router.get("/{tmpl_id}/edit", response_class=HTMLResponse)
async def templates_edit(request: Request, tmpl_id: int):
    tmpl = await get_template(tmpl_id)
    if not tmpl:
        return RedirectResponse(url="/templates", status_code=303)

    cities = await list_cities()
    template_keys = list_known_template_keys()
    payload = _build_template_payload(
        tmpl_id=tmpl.id,
        key=tmpl.key,
        text=tmpl.content,
        city_id=tmpl.city_id,
        is_global=tmpl.city_id is None,
    )

    if payload["city_id"] is not None and not any(c.id == payload["city_id"] for c in cities):
        cities = list(cities) + [
            SimpleNamespace(
                id=payload["city_id"],
                name=f"Город #{payload['city_id']} (удалён)",
                tz=None,
            )
        ]

    context = {
        "request": request,
        "tmpl": payload,
        "cities": cities,
        "errors": [],
        "template_keys": template_keys,
    }
    return jinja_templates.TemplateResponse(request, "templates_edit.html", context)


@router.post("/{tmpl_id}/update")
async def templates_update(
    request: Request,
    tmpl_id: int,
    key: str = Form(...),
    text: str = Form(...),
    city_id: Optional[str] = Form(None),
    is_global: Optional[str] = Form(None),
):
    tmpl = await get_template(tmpl_id)
    if not tmpl:
        return RedirectResponse(url="/templates", status_code=303)

    text_value = (text or "").strip()
    key_value = (key or "").strip()
    global_template = bool(is_global)
    parsed_city = parse_optional_int(city_id)
    errors: List[str] = []

    if not text_value:
        errors.append("Введите текст шаблона.")

    if not key_value:
        errors.append("Введите ключ шаблона.")

    if global_template:
        parsed_city = None
    elif parsed_city is None:
        errors.append("Выберите город или отметьте шаблон как глобальный.")

    payload = _build_template_payload(
        tmpl_id=tmpl.id,
        key=key_value,
        text=text_value,
        city_id=parsed_city,
        is_global=global_template,
    )

    cities = await list_cities()
    if payload["city_id"] is not None and not any(c.id == payload["city_id"] for c in cities):
        cities = list(cities) + [
            SimpleNamespace(
                id=payload["city_id"],
                name=f"Город #{payload['city_id']} (удалён)",
                tz=None,
            )
        ]

    template_keys = list_known_template_keys()

    if errors:
        context = {
            "request": request,
            "tmpl": payload,
            "cities": cities,
            "errors": errors,
            "template_keys": template_keys,
        }
        return jinja_templates.TemplateResponse(request, "templates_edit.html", context, status_code=400)

    updated = await update_template(
        tmpl_id,
        key=key_value,
        text=text_value,
        city_id=payload["city_id"],
    )
    if not updated:
        context = {
            "request": request,
            "tmpl": payload,
            "cities": cities,
            "errors": [
                "Не удалось сохранить шаблон. Проверьте уникальность ключа и попробуйте ещё раз."
            ],
            "template_keys": template_keys,
        }
        return jinja_templates.TemplateResponse(request, "templates_edit.html", context, status_code=400)

    notify_templates_changed()
    return RedirectResponse(url="/templates", status_code=303)


@router.post("/{tmpl_id}/delete")
async def templates_delete(tmpl_id: int):
    await delete_template(tmpl_id)
    notify_templates_changed()
    return RedirectResponse(url="/templates", status_code=303)
