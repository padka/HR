from pathlib import Path

from fastapi.templating import Jinja2Templates

from backend.apps.admin_ui.timezones import tz_display, tz_region_name
from backend.apps.admin_ui.utils import fmt_local, fmt_utc, norm_status, initials

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def register_template_globals() -> None:
    templates.env.globals.update(
        fmt_local=fmt_local,
        fmt_utc=fmt_utc,
        norm_status=norm_status,
        tz_display=tz_display,
        tz_region_name=tz_region_name,
        initials=initials,
    )


__all__ = [
    "templates",
    "register_template_globals",
    "STATIC_DIR",
]
