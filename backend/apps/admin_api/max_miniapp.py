"""MAX mini-app host shell backed by the built frontend bundle."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.core.settings import get_settings

router = APIRouter(tags=["max-miniapp"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPA_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
SPA_INDEX_FILE = SPA_DIST_DIR / "index.html"


@router.get("/miniapp", include_in_schema=False, response_class=FileResponse)
async def max_miniapp_shell() -> FileResponse:
    settings = get_settings()
    if not getattr(settings, "max_adapter_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MAX mini-app shell is disabled.",
        )
    if not SPA_INDEX_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Frontend bundle is not built for MAX mini-app hosting.",
        )
    return FileResponse(
        SPA_INDEX_FILE,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


__all__ = ["router", "SPA_DIST_DIR", "SPA_INDEX_FILE", "max_miniapp_shell"]
