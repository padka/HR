import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy import text

from backend.core.db import async_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon_redirect() -> RedirectResponse:
    return RedirectResponse(url="/static/favicon.ico")


@router.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def devtools_probe() -> Response:
    return Response(status_code=204)


@router.get("/__routes", include_in_schema=False)
async def list_routes(request: Request):
    routes = []
    for item in request.app.routes:
        methods = sorted(list(getattr(item, "methods", []))) if hasattr(item, "methods") else []
        routes.append({"path": getattr(item, "path", None), "methods": methods, "name": getattr(item, "name", None)})
    return {"routes": routes}


@router.get("/health", include_in_schema=False)
async def health_check(request: Request) -> JSONResponse:
    checks = {
        "database": "ok",
        "state_manager": "ok" if getattr(request.app.state, "state_manager", None) else "missing",
    }
    bot_service = getattr(request.app.state, "bot_service", None)
    if bot_service is None:
        bot_client_status = "missing"
    else:
        bot_client_status = bot_service.health_status

    checks["bot_client"] = bot_client_status
    if bot_client_status == "ok":
        checks["bot"] = "configured"
    elif bot_client_status == "disabled":
        checks["bot"] = "disabled"
    else:
        checks["bot"] = "unconfigured"
    status_code = 200

    if checks["state_manager"] == "missing":
        status_code = 503

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - depends on runtime DB availability
        logger.exception("Health check database probe failed")
        checks["database"] = "error"
        status_code = 503

    return JSONResponse({"status": "ok" if status_code == 200 else "error", "checks": checks}, status_code=status_code)
