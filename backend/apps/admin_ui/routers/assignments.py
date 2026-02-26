import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/assignments", tags=["assignments"])
logger = logging.getLogger(__name__)

_DEPRECATION_BODY = {
    "ok": False,
    "deprecated": True,
    "message": (
        "This endpoint is deprecated and will be removed. "
        "Migrate to POST /api/slot-assignments/{id}/confirm "
        "or POST /api/slot-assignments/{id}/request-reschedule "
        "with a valid action token."
    ),
}


@router.post("/{assignment_id}/confirm")
async def confirm_assignment(assignment_id: int):
    """DEPRECATED: Use POST /api/slot-assignments/{id}/confirm with action token."""
    logger.warning(
        "Deprecated /api/v1/assignments/%s/confirm called. "
        "Migrate to token-based /api/slot-assignments/ endpoints.",
        assignment_id,
    )
    return JSONResponse(status_code=410, content=_DEPRECATION_BODY)


@router.post("/{assignment_id}/request-reschedule")
async def request_reschedule(assignment_id: int):
    """DEPRECATED: Use POST /api/slot-assignments/{id}/request-reschedule with action token."""
    logger.warning(
        "Deprecated /api/v1/assignments/%s/request-reschedule called. "
        "Migrate to token-based /api/slot-assignments/ endpoints.",
        assignment_id,
    )
    return JSONResponse(status_code=410, content=_DEPRECATION_BODY)
