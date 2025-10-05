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
    list_templates,
    notify_templates_changed,
    update_template,
    update_templates_for_city,
)
from backend.apps.admin_ui.utils import parse_optional_int

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_class=HTMLResponse)
async def templates_list(request: Request):
    data = await list_templates()
    context = {
        "request": request,
        **data,
    }
    return jinja_templates.TemplateResponse("templates_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def templates_new(request: Request):
    cities = await list_cities()
    context = {
        "request": request,
        "cities": cities,
        "errors": [],
        "form_data": {},
    }
    return jinja_templates.TemplateResponse("templates_new.html", context)


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
        }
        return jinja_templates.TemplateResponse("templates_new.html", context, status_code=400)

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
    }
    return jinja_templates.TemplateResponse("templates_edit.html", context)


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

    if errors:
        context = {
            "request": request,
            "tmpl": payload,
            "cities": cities,
            "errors": errors,
        }
        return jinja_templates.TemplateResponse("templates_edit.html", context, status_code=400)

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
        }
        return jinja_templates.TemplateResponse("templates_edit.html", context, status_code=400)

    notify_templates_changed()
    return RedirectResponse(url="/templates", status_code=303)


@router.post("/{tmpl_id}/delete")
async def templates_delete(tmpl_id: int):
    await delete_template(tmpl_id)
    notify_templates_changed()
    return RedirectResponse(url="/templates", status_code=303)
