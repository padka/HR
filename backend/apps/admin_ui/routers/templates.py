from typing import List, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.apps.admin_ui.config import templates as jinja_templates
from backend.apps.admin_ui.services.cities import list_cities
from backend.apps.admin_ui.services.templates import create_template, list_templates, update_templates_for_city
from backend.apps.admin_ui.utils import parse_optional_int

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_class=HTMLResponse)
async def templates_list(request: Request):
    overview = await list_templates()
    context = {
        "request": request,
        "overview": overview,
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

    await update_templates_for_city(city_id, templates_payload)
    return JSONResponse({"ok": True})
