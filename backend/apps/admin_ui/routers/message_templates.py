from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.apps.admin_ui.services.message_templates import delete_message_template

router = APIRouter(prefix="/message-templates", tags=["message_templates"])


@router.get("", response_class=HTMLResponse)
async def message_templates_list(
    request: Request,
    city: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    redirect_url = "/app/message-templates"
    params = []
    if city:
        params.append(f"city={city}")
    if key:
        params.append(f"key={key}")
    if channel:
        params.append(f"channel={channel}")
    if status:
        params.append(f"status={status}")
    if params:
        redirect_url += "?" + "&".join(params)
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/new", response_class=HTMLResponse)
async def message_templates_new(request: Request, copy_from: Optional[int] = Query(None)):
    return RedirectResponse(url="/app/message-templates", status_code=302)


@router.post("/create")
async def message_templates_create(request: Request):
    return RedirectResponse(url="/app/message-templates", status_code=303)


@router.get("/{template_id}/edit", response_class=HTMLResponse)
async def message_templates_edit(request: Request, template_id: int):
    return RedirectResponse(url="/app/message-templates", status_code=302)


@router.post("/{template_id}/update")
async def message_templates_update(request: Request, template_id: int):
    return RedirectResponse(url="/app/message-templates", status_code=303)


@router.post("/{template_id}/delete")
async def message_templates_delete(template_id: int):
    await delete_message_template(template_id)
    return RedirectResponse(url="/message-templates", status_code=303)
