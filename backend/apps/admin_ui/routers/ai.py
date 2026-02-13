from __future__ import annotations

from datetime import date as date_type, datetime, time, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.apps.admin_ui.security import Principal, require_admin, require_csrf_token, require_principal
from backend.core.ai.service import AIService, AIDisabledError, AIRateLimitedError
from backend.core.ai.service import get_ai_service
from backend.core.db import async_session
from backend.domain.models import City, OutboxNotification
from backend.apps.admin_ui.services.dashboard import get_bot_funnel_stats, get_pipeline_snapshot
from sqlalchemy import func, select

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _parse_date_param(value: Optional[str], *, end: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date_type.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": "Некорректный параметр даты"}) from exc
    dt = datetime.combine(parsed, time.max if end else time.min)
    return dt.replace(tzinfo=timezone.utc)


def _disabled() -> JSONResponse:
    return JSONResponse({"ok": False, "error": "ai_disabled"}, status_code=501)


def _rate_limited() -> JSONResponse:
    return JSONResponse({"ok": False, "error": "rate_limited"}, status_code=429)


@router.get("/candidates/{candidate_id}/summary")
async def api_ai_candidate_summary(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
    ai: AIService = Depends(get_ai_service),
) -> JSONResponse:
    try:
        result = await ai.get_candidate_summary(candidate_id, principal=principal, refresh=False)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, "summary": result.payload})


@router.post("/candidates/{candidate_id}/summary/refresh")
async def api_ai_candidate_summary_refresh(
    candidate_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
    ai: AIService = Depends(get_ai_service),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    try:
        result = await ai.get_candidate_summary(candidate_id, principal=principal, refresh=True)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, "summary": result.payload})


@router.post("/candidates/{candidate_id}/chat/drafts")
async def api_ai_chat_drafts(
    candidate_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
    ai: AIService = Depends(get_ai_service),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    payload = await request.json()
    mode = "neutral"
    if isinstance(payload, dict) and payload.get("mode"):
        mode = str(payload.get("mode"))
    if mode not in {"short", "neutral", "supportive"}:
        raise HTTPException(status_code=400, detail={"message": "Некорректный mode"})
    try:
        result = await ai.get_chat_reply_drafts(candidate_id, principal=principal, mode=mode)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, **result.payload})


@router.post("/dashboard/insights")
async def api_ai_dashboard_insights(
    request: Request,
    principal: Principal = Depends(require_admin),
    ai: AIService = Depends(get_ai_service),
) -> JSONResponse:
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Ожидался JSON"})
    date_from = _parse_date_param(data.get("date_from"))
    date_to = _parse_date_param(data.get("date_to"), end=True)
    city_id = data.get("city_id")
    city_name: Optional[str] = None
    scope_id = 0
    if city_id is not None:
        try:
            city_id_value = int(city_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail={"message": "Некорректный city_id"})
        async with async_session() as session:
            city = await session.get(City, city_id_value)
            if city is None:
                raise HTTPException(status_code=404, detail={"message": "Город не найден"})
            city_name = city.name
        scope_id = city_id_value

    # Aggregated context: funnel + snapshot + outbox error rates
    funnel = await get_bot_funnel_stats(date_from=date_from, date_to=date_to, city=city_name)
    snapshot = await get_pipeline_snapshot(city=city_name)

    outbox_failed = 0
    outbox_total = 0
    async with async_session() as session:
        stmt = select(func.count(OutboxNotification.id))
        outbox_total = int(await session.scalar(stmt) or 0)
        outbox_failed = int(
            await session.scalar(
                stmt.where(func.lower(OutboxNotification.status) == "failed")
            )
            or 0
        )

    ctx = {
        "kind": "dashboard_insight_v1",
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "city_id": scope_id or None,
        "funnel": funnel,
        "snapshot": snapshot,
        "notifications": {
            "outbox_total": outbox_total,
            "outbox_failed": outbox_failed,
            "outbox_failed_rate": round((outbox_failed / outbox_total) * 100, 2) if outbox_total else 0.0,
        },
    }

    try:
        result = await ai.get_dashboard_insights(principal=principal, context=ctx, scope_id=scope_id, refresh=False)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, "insight": result.payload})
