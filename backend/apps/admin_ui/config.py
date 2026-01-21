from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from starlette_wtf import csrf_token

from backend.apps.admin_ui.timezones import tz_display, tz_region_name
from backend.apps.admin_ui.utils import fmt_local, fmt_utc, norm_status, render_or_empty

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _safe_csrf_token(request) -> str:
    try:
        return csrf_token(request)
    except Exception:
        return ""


def _render_csrf_input(request) -> Markup:
    token = _safe_csrf_token(request)
    if not token:
        return Markup("")
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')


def register_template_globals() -> None:
    templates.env.globals.update(
        fmt_local=fmt_local,
        fmt_utc=fmt_utc,
        norm_status=norm_status,
        tz_display=tz_display,
        tz_region_name=tz_region_name,
        render_or_empty=render_or_empty,
        csrf_input=_render_csrf_input,
        csrf_token=_safe_csrf_token,
    )
    templates.env.filters.setdefault("render_or_empty", render_or_empty)


def safe_template_response(
    template_name: str,
    request: Request,
    context: Mapping[str, Any] | None = None,
    *,
    encode_json_keys: Iterable[str] = (),
    **response_kwargs: Any,
):
    payload: dict[str, Any] = {"request": request}
    if context:
        payload.update(context)
    for key in encode_json_keys:
        if key in payload:
            payload[key] = jsonable_encoder(payload[key])
    return templates.TemplateResponse(request, template_name, payload, **response_kwargs)


__all__ = [
    "templates",
    "register_template_globals",
    "safe_template_response",
    "STATIC_DIR",
]
