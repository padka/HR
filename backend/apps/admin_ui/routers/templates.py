from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.apps.admin_ui.config import templates as jinja_templates
from backend.apps.admin_ui import services
from backend.apps.admin_ui.utils import parse_optional_int

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_class=HTMLResponse)
async def templates_list(request: Request):
    data = await services.list_templates()
    context = {
        "request": request,
        "items": data["templates"],
        "cities": data["cities"],
    }
    return jinja_templates.TemplateResponse("templates_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def templates_new(request: Request):
    cities = await services.list_cities()
    return jinja_templates.TemplateResponse("templates_new.html", {"request": request, "cities": cities})


@router.post("/create")
async def templates_create(
    key: str = Form(...),
    text: str = Form(...),
    city_id: Optional[str] = Form(None),
    is_global: Optional[str] = Form(None),
):
    city_id_val = None if is_global else parse_optional_int(city_id)
    if not is_global and city_id_val is None:
        return RedirectResponse(url="/templates/new?err=city_required", status_code=303)
    await services.create_template(key, text, city_id_val)
    return RedirectResponse(url="/templates", status_code=303)


@router.get("/{tmpl_id}/edit", response_class=HTMLResponse)
async def templates_edit(request: Request, tmpl_id: int):
    tmpl = await services.get_template(tmpl_id)
    if not tmpl:
        return RedirectResponse(url="/templates", status_code=303)
    cities = await services.list_cities()
    context = {
        "request": request,
        "tmpl": tmpl,
        "cities": cities,
    }
    return jinja_templates.TemplateResponse("templates_edit.html", context)


@router.post("/{tmpl_id}/update")
async def templates_update(
    tmpl_id: int,
    key: str = Form(...),
    text: str = Form(...),
    city_id: Optional[str] = Form(None),
    is_global: Optional[str] = Form(None),
):
    city_id_val = None if is_global else parse_optional_int(city_id)
    if not is_global and city_id_val is None:
        return RedirectResponse(url=f"/templates/{tmpl_id}/edit?err=city_required", status_code=303)
    await services.update_template(tmpl_id, key=key, text=text, city_id=city_id_val)
    return RedirectResponse(url="/templates", status_code=303)


@router.post("/{tmpl_id}/delete")
async def templates_delete(tmpl_id: int):
    await services.delete_template(tmpl_id)
    return RedirectResponse(url="/templates", status_code=303)
