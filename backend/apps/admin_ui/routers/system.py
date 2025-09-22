from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

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
