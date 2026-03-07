"""Shared HH webhook receiver router for admin surfaces."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from backend.core.dependencies import get_async_session
from backend.domain.hh_integration import get_connection_for_webhook_key
from backend.domain.hh_integration.models import HHWebhookDelivery

router = APIRouter(prefix="/api/hh-integration", tags=["hh-integration"])
AsyncSessionDep = Depends(get_async_session)


class HHWebhookEnvelope(BaseModel):
    id: str
    subscription_id: str
    action_type: str
    payload: dict[str, Any]


@router.post("/webhooks/{webhook_key}")
async def receive_hh_webhook(
    webhook_key: str,
    request: Request,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_webhook_key(session, webhook_key)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown webhook key")

    try:
        raw_payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    try:
        payload = HHWebhookEnvelope.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.errors()) from exc

    existing = await session.scalar(
        select(HHWebhookDelivery.id).where(
            HHWebhookDelivery.connection_id == connection.id,
            HHWebhookDelivery.delivery_id == payload.id,
        )
    )
    if existing is not None:
        return JSONResponse({"ok": True, "duplicate": True}, status_code=status.HTTP_409_CONFLICT)

    delivery = HHWebhookDelivery(
        connection_id=connection.id,
        delivery_id=payload.id,
        subscription_id=payload.subscription_id,
        action_type=payload.action_type,
        payload_json=raw_payload,
        headers_json={k: v for k, v in request.headers.items()},
    )
    session.add(delivery)
    await session.commit()
    return JSONResponse({"ok": True, "duplicate": False}, status_code=status.HTTP_202_ACCEPTED)
