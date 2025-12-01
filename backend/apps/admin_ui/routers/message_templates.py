from typing import List, Optional

from fastapi import APIRouter, Form, Request, Query
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
    get_template_history,
    list_message_templates,
    update_message_template,
)

router = APIRouter(prefix="/message-templates", tags=["message_templates"])


def _parse_city(raw: Optional[str]) -> Optional[int]:
    if raw in {None, "", "default", "none"}:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_flag(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    value = str(raw).strip().lower()
    return value in {"1", "true", "yes", "on", "publish", "active"}


@router.get("", response_class=HTMLResponse)
async def message_templates_list(
    request: Request,
    city: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    payload = await list_message_templates(city=city, key_query=key, channel=channel, status=status)
    context = {
        "request": request,
        "templates": payload["templates"],
        "missing_required": payload["missing_required"],
        "known_hints": payload["known_hints"],
        "cities": payload["cities"],
        "filters": payload["filters"],
        "variables": payload["variables"],
        "mock_context": payload["mock_context"],
        "coverage": payload["coverage"],
        "allowed_channels": ALLOWED_CHANNELS,
    }
    return jinja_templates.TemplateResponse(request, "message_templates_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def message_templates_new(request: Request, copy_from: Optional[int] = Query(None)):
    payload = await list_message_templates()
    base_form = {
        "key": "",
        "locale": DEFAULT_LOCALE,
        "channel": DEFAULT_CHANNEL,
        "city_id": None,
        "body": "",
        "is_active": True,
        "version": 1,
    }
    if copy_from:
        source = await get_message_template(copy_from)
        if source:
            base_form.update(
                {
                    "key": source.key,
                    "locale": source.locale,
                    "channel": source.channel,
                    "city_id": source.city_id,
                    "body": source.body_md,
                    "is_active": False,
                    "version": (source.version or 1) + 1,
                }
            )
    context = {
        "request": request,
        "errors": [],
        "form_data": base_form,
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": False,
        "cities": payload["cities"],
        "variables": payload["variables"],
        "mock_context": payload["mock_context"],
        "history": [],
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context)


@router.post("/create")
async def message_templates_create(
    request: Request,
    key: str = Form(...),
    locale: str = Form(DEFAULT_LOCALE),
    channel: str = Form(DEFAULT_CHANNEL),
    city_id: Optional[str] = Form("default"),
    body: str = Form(...),
    is_active: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
):
    parsed_city = _parse_city(city_id)
    success, errors, _ = await create_message_template(
        key=key,
        locale=locale,
        channel=channel,
        city_id=parsed_city,
        body=body,
        is_active=_parse_flag(is_active),
        version=int(version) if version else None,
    )
    if success:
        return RedirectResponse(url="/message-templates", status_code=303)

    payload = await list_message_templates()
    context = {
        "request": request,
        "errors": errors,
        "form_data": {
            "key": key,
            "locale": locale,
            "channel": channel,
            "city_id": parsed_city,
            "body": body,
            "is_active": _parse_flag(is_active),
            "version": version or 1,
        },
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": False,
        "cities": payload["cities"],
        "variables": payload["variables"],
        "mock_context": payload["mock_context"],
        "history": [],
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context, status_code=400)


@router.get("/{template_id}/edit", response_class=HTMLResponse)
async def message_templates_edit(request: Request, template_id: int):
    template = await get_message_template(template_id)
    if template is None:
        return RedirectResponse(url="/message-templates", status_code=303)

    payload = await list_message_templates()
    history = await get_template_history(template.id)
    context = {
        "request": request,
        "errors": [],
        "template_id": template.id,
        "form_data": {
            "key": template.key,
            "locale": template.locale,
            "channel": template.channel,
            "city_id": template.city_id,
            "body": template.body_md,
            "is_active": template.is_active,
            "version": template.version,
        },
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": True,
        "cities": payload["cities"],
        "variables": payload["variables"],
        "mock_context": payload["mock_context"],
        "history": history,
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context)


@router.post("/{template_id}/update")
async def message_templates_update(
    request: Request,
    template_id: int,
    key: str = Form(...),
    locale: str = Form(DEFAULT_LOCALE),
    channel: str = Form(DEFAULT_CHANNEL),
    city_id: Optional[str] = Form("default"),
    body: str = Form(...),
    is_active: Optional[str] = Form(None),
    bump_version: Optional[str] = Form(None),
):
    parsed_city = _parse_city(city_id)
    success, errors = await update_message_template(
        template_id,
        key=key,
        locale=locale,
        channel=channel,
        city_id=parsed_city,
        body=body,
        is_active=_parse_flag(is_active),
        bump_version=bool(bump_version),
    )
    if success:
        return RedirectResponse(url="/message-templates", status_code=303)

    payload = await list_message_templates()
    history = await get_template_history(template_id)
    context = {
        "request": request,
        "errors": errors,
        "template_id": template_id,
        "form_data": {
            "key": key,
            "locale": locale,
            "channel": channel,
            "city_id": parsed_city,
            "body": body,
            "is_active": _parse_flag(is_active),
        },
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": True,
        "cities": payload["cities"],
        "variables": payload["variables"],
        "mock_context": payload["mock_context"],
        "history": history,
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context, status_code=400)


@router.post("/{template_id}/activate")
async def message_templates_activate(request: Request, template_id: int):
    template = await get_message_template(template_id)
    if template is None:
        return RedirectResponse(url="/message-templates", status_code=303)

    success, errors = await update_message_template(
        template_id,
        key=template.key,
        locale=template.locale,
        channel=template.channel,
        city_id=template.city_id,
        body=template.body_md,
        is_active=True,
        bump_version=False,
    )
    if success:
        return RedirectResponse(url="/message-templates", status_code=303)

    payload = await list_message_templates()
    history = await get_template_history(template_id)
    context = {
        "request": request,
        "errors": errors,
        "template_id": template_id,
        "form_data": {
            "key": template.key,
            "locale": template.locale,
            "channel": template.channel,
            "city_id": template.city_id,
            "body": template.body_md,
            "is_active": template.is_active,
            "version": template.version,
        },
        "allowed_channels": ALLOWED_CHANNELS,
        "known_hints": KNOWN_TEMPLATE_HINTS,
        "is_edit": True,
        "cities": payload["cities"],
        "variables": payload["variables"],
        "mock_context": payload["mock_context"],
        "history": history,
    }
    return jinja_templates.TemplateResponse(request, "message_templates_form.html", context, status_code=400)


@router.post("/{template_id}/delete")
async def message_templates_delete(template_id: int):
    await delete_message_template(template_id)
    return RedirectResponse(url="/message-templates", status_code=303)
