from typing import List, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.apps.admin_ui.config import templates as jinja_templates
from backend.apps.admin_ui.services.message_templates import (
    ALLOWED_CHANNELS,
    DEFAULT_CHANNEL,
    DEFAULT_LOCALE,
    KNOWN_TEMPLATE_HINTS,
    create_message_template,
    delete_message_template,
    get_message_template,
    list_message_templates,
    update_message_template,
)

router = APIRouter(prefix="/message-templates", tags=["message_templates"])


@router.get("", response_class=HTMLResponse)
async def message_templates_list(request: Request):
    payload = await list_message_templates()
    context = {
        "request": request,
        "templates": payload["templates"],
        "missing_required": payload["missing_required"],
        "known_hints": payload["known_hints"],
    }
    return jinja_templates.TemplateResponse(request, "message_templates_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def message_templates_new(request: Request):
    context = {
        "request": request,
        "errors": [],
        "form_data": {
            "key": "",
            "locale": DEFAULT_LOCALE,
            "channel": DEFAULT_CHANNEL,
            "body": "",
            "is_active": True,
            "version": 1,
        },
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": False,
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context)


@router.post("/create")
async def message_templates_create(
    request: Request,
    key: str = Form(...),
    locale: str = Form(DEFAULT_LOCALE),
    channel: str = Form(DEFAULT_CHANNEL),
    body: str = Form(...),
    is_active: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
):
    success, errors, _ = await create_message_template(
        key=key,
        locale=locale,
        channel=channel,
        body=body,
        is_active=bool(is_active),
        version=int(version) if version else None,
    )
    if success:
        return RedirectResponse(url="/message-templates", status_code=303)

    context = {
        "request": request,
        "errors": errors,
        "form_data": {
            "key": key,
            "locale": locale,
            "channel": channel,
            "body": body,
            "is_active": bool(is_active),
            "version": version or 1,
        },
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": False,
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context, status_code=400)


@router.get("/{template_id}/edit", response_class=HTMLResponse)
async def message_templates_edit(request: Request, template_id: int):
    template = await get_message_template(template_id)
    if template is None:
        return RedirectResponse(url="/message-templates", status_code=303)

    context = {
        "request": request,
        "errors": [],
        "template_id": template.id,
        "form_data": {
            "key": template.key,
            "locale": template.locale,
            "channel": template.channel,
            "body": template.body_md,
            "is_active": template.is_active,
            "version": template.version,
        },
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": True,
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context)


@router.post("/{template_id}/update")
async def message_templates_update(
    request: Request,
    template_id: int,
    key: str = Form(...),
    locale: str = Form(DEFAULT_LOCALE),
    channel: str = Form(DEFAULT_CHANNEL),
    body: str = Form(...),
    is_active: Optional[str] = Form(None),
    bump_version: Optional[str] = Form(None),
):
    success, errors = await update_message_template(
        template_id,
        key=key,
        locale=locale,
        channel=channel,
        body=body,
        is_active=bool(is_active),
        bump_version=bool(bump_version),
    )
    if success:
        return RedirectResponse(url="/message-templates", status_code=303)

    context = {
        "request": request,
        "errors": errors,
        "template_id": template_id,
        "form_data": {
            "key": key,
            "locale": locale,
            "channel": channel,
            "body": body,
            "is_active": bool(is_active),
        },
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": True,
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context, status_code=400)


@router.post("/{template_id}/delete")
async def message_templates_delete(template_id: int):
    await delete_message_template(template_id)
    return RedirectResponse(url="/message-templates", status_code=303)
