from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.apps.admin_ui.services.templates import (
    delete_template,
    notify_templates_changed,
    update_templates_for_city,
)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_class=HTMLResponse)
async def templates_list(request: Request):
    return RedirectResponse(url="/app/templates", status_code=302)


@router.get("/new", response_class=HTMLResponse)
async def templates_new(request: Request):
    return RedirectResponse(url="/app/templates/new", status_code=302)


@router.post("/create")
async def templates_create(
    request: Request,
):
    return RedirectResponse(url="/app/templates", status_code=303)


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


@router.get("/{tmpl_id}/edit", response_class=HTMLResponse)
async def templates_edit(request: Request, tmpl_id: int):
    return RedirectResponse(url=f"/app/templates/{tmpl_id}/edit", status_code=302)


@router.post("/{tmpl_id}/update")
async def templates_update(
    request: Request,
    tmpl_id: int,
):
    return RedirectResponse(url=f"/app/templates/{tmpl_id}/edit", status_code=303)


@router.post("/{tmpl_id}/delete")
async def templates_delete(tmpl_id: int):
    await delete_template(tmpl_id)
    notify_templates_changed()
    return RedirectResponse(url="/templates", status_code=303)
