from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui import services

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    counts = await services.dashboard_counts()
    recruiters = await services.list_recruiters()
    cities = await services.list_cities()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "counts": counts, "recruiters": recruiters, "cities": cities},
    )
