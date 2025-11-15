from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from starlette_wtf import csrf_token

from backend.apps.admin_ui.timezones import tz_display, tz_region_name
from backend.apps.admin_ui.utils import fmt_local, fmt_utc, norm_status, render_or_empty

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _render_csrf_input(request) -> Markup:
    token = csrf_token(request)
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
        csrf_token=csrf_token,
    )
    templates.env.filters.setdefault("render_or_empty", render_or_empty)


__all__ = [
    "templates",
    "register_template_globals",
    "STATIC_DIR",
]
