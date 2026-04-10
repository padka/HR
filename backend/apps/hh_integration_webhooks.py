"""Shared HH webhook receiver router for admin surfaces."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from backend.core.dependencies import get_async_session
from backend.domain.hh_integration import get_connection_for_webhook_key
from backend.domain.hh_integration.contracts import HHWebhookDeliveryStatus
from backend.domain.hh_integration.jobs import enqueue_hh_sync_job
from backend.domain.hh_integration.models import HHNegotiation, HHWebhookDelivery

router = APIRouter(prefix="/api/hh-integration", tags=["hh-integration"])
AsyncSessionDep = Depends(get_async_session)
logger = logging.getLogger(__name__)


class HHWebhookEnvelope(BaseModel):
    id: str
    subscription_id: str
    action_type: str
    payload: dict[str, Any]


def _string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _extract_webhook_vacancy_id(payload: dict[str, Any]) -> str | None:
    direct = _string(payload.get("vacancy_id"))
    if direct:
        return direct

    vacancy = payload.get("vacancy")
    if isinstance(vacancy, dict):
        nested = _string(vacancy.get("id"))
        if nested:
            return nested

    topic = payload.get("topic")
    if isinstance(topic, dict):
        topic_vacancy = _string(topic.get("vacancy_id"))
        if topic_vacancy:
            return topic_vacancy
        nested_vacancy = topic.get("vacancy")
        if isinstance(nested_vacancy, dict):
            nested = _string(nested_vacancy.get("id"))
            if nested:
                return nested

    return None


def _extract_webhook_negotiation_id(payload: dict[str, Any]) -> str | None:
    direct = _string(payload.get("negotiation_id"))
    if direct:
        return direct

    negotiation = payload.get("negotiation")
    if isinstance(negotiation, dict):
        nested = _string(negotiation.get("id"))
        if nested:
            return nested

    return None


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

    vacancy_id = _extract_webhook_vacancy_id(payload.payload)
    negotiation_id = _extract_webhook_negotiation_id(payload.payload)
    if vacancy_id or negotiation_id:
        if vacancy_id is None and negotiation_id:
            negotiation = (
                await session.execute(
                    select(HHNegotiation).where(HHNegotiation.external_negotiation_id == negotiation_id).limit(1)
                )
            ).scalar_one_or_none()
            if negotiation is not None:
                vacancy_id = _string(negotiation.external_vacancy_id)
        if vacancy_id:
            await enqueue_hh_sync_job(
                session,
                connection=connection,
                job_type="import_negotiations",
                entity_type="vacancy",
                entity_external_id=vacancy_id,
                payload_json={"fetch_resume_details": False},
            )
        else:
            logger.info(
                "hh.webhook.reimport.skipped_missing_vacancy_id",
                extra={
                    "connection_id": connection.id,
                    "delivery_id": payload.id,
                    "action_type": payload.action_type,
                    "negotiation_id": negotiation_id,
                },
            )
            await enqueue_hh_sync_job(
                session,
                connection=connection,
                job_type="import_negotiations",
                entity_type="employer",
                entity_external_id=connection.employer_id,
                payload_json={"fetch_resume_details": False},
            )

    delivery.status = HHWebhookDeliveryStatus.PROCESSED
    delivery.processed_at = datetime.now(UTC)

    await session.commit()
    return JSONResponse({"ok": True, "duplicate": False}, status_code=status.HTTP_202_ACCEPTED)
