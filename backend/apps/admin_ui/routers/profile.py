from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from backend.apps.admin_ui.security import Principal, require_principal

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", include_in_schema=False)
async def profile(request: Request, principal: Principal = Depends(require_principal)) -> RedirectResponse:
    query = request.url.query
    target = "/app/profile"
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(url=target)
