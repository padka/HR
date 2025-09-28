from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from backend.apps.admin_ui.config import templates as jinja_templates
from backend.apps.admin_ui import services

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_class=HTMLResponse)
async def templates_list(request: Request):
    overview = await services.list_templates()
    context = {
        "request": request,
        "overview": overview,
    }
    return jinja_templates.TemplateResponse("templates_list.html", context)


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

    await services.update_templates_for_city(city_id, templates_payload)
    return JSONResponse({"ok": True})
