from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.apps.admin_ui.services.cities import list_cities

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    counts = await dashboard_counts()
    recruiters = await list_recruiters()
    cities = await list_cities()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "counts": counts, "recruiters": recruiters, "cities": cities},
    )
