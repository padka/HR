"""hh.ru sync callback endpoints.

Called by n8n after processing hh.ru API requests.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from backend.core.dependencies import get_async_session
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hh-sync", tags=["hh-sync"])


class SyncCallbackRequest(BaseModel):
    """Callback payload from n8n after hh.ru status sync."""

    candidate_id: int
    success: bool
    hh_status: Optional[str] = None
    error_message: Optional[str] = None
    response_payload: Optional[dict] = None


class ResolveCallbackRequest(BaseModel):
    """Callback payload from n8n after negotiation resolve."""

    candidate_id: int
    negotiation_id: Optional[str] = None
    vacancy_id: Optional[str] = None
    not_found: bool = False
    error_message: Optional[str] = None
    response_payload: Optional[dict] = None


def _verify_webhook_secret(x_webhook_secret: Optional[str] = Header(None)) -> None:
    """Verify the webhook secret header matches the configured value."""
    settings = get_settings()
    expected = settings.hh_webhook_secret
    if not expected:
        # No secret configured — allow all (dev mode)
        return
    if x_webhook_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret",
        )


@router.post("/callback")
async def hh_sync_callback(
    body: SyncCallbackRequest,
    session=Depends(get_async_session),
    _auth: None = Depends(_verify_webhook_secret),
):
    """Handle callback from n8n after hh.ru status sync API call."""
    from backend.domain.hh_sync.worker import handle_sync_callback

    await handle_sync_callback(
        candidate_id=body.candidate_id,
        success=body.success,
        hh_status=body.hh_status,
        error_message=body.error_message,
        response_payload=body.response_payload,
        session=session,
    )
    await session.commit()
    logger.info(
        "hh_sync_callback: candidate=%s success=%s",
        body.candidate_id,
        body.success,
    )
    return {"ok": True}


@router.post("/resolve-callback")
async def hh_resolve_callback(
    body: ResolveCallbackRequest,
    session=Depends(get_async_session),
    _auth: None = Depends(_verify_webhook_secret),
):
    """Handle callback from n8n after negotiation resolve attempt."""
    from backend.domain.hh_sync.worker import handle_resolve_callback

    await handle_resolve_callback(
        candidate_id=body.candidate_id,
        negotiation_id=body.negotiation_id,
        vacancy_id=body.vacancy_id,
        not_found=body.not_found,
        error_message=body.error_message,
        response_payload=body.response_payload,
        session=session,
    )
    await session.commit()
    logger.info(
        "hh_resolve_callback: candidate=%s negotiation=%s not_found=%s",
        body.candidate_id,
        body.negotiation_id,
        body.not_found,
    )
    return {"ok": True}
