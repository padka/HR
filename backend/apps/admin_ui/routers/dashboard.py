from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.dashboard import (
    dashboard_calendar_snapshot,
    dashboard_counts,
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    counts = await dashboard_counts()
    calendar = await dashboard_calendar_snapshot()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "counts": counts,
            "calendar": calendar,
        },
    )
