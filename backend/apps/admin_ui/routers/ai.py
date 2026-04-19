from __future__ import annotations

from datetime import UTC, datetime, time
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select

from backend.apps.admin_ui.security import (
    Principal,
    get_principal_identifier,
    limiter,
    require_admin,
    require_csrf_token,
    require_principal,
)
from backend.apps.admin_ui.services.dashboard import (
    get_bot_funnel_stats,
    get_pipeline_snapshot,
)
from backend.core.ai.service import (
    AIDisabledError,
    AIRateLimitedError,
    AIService,
    get_ai_service,
)
from backend.core.db import async_session
from backend.domain.models import City, OutboxNotification

router = APIRouter(prefix="/api/ai", tags=["ai"])
principal_dep = Depends(require_principal)
admin_dep = Depends(require_admin)
ai_dep = Depends(get_ai_service)

"""AI endpoints for candidate summaries, chat drafts, dashboard insights, and agent chat."""


def _parse_date_param(value: str | None, *, end: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date_type.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": "Некорректный параметр даты"}) from exc
    dt = datetime.combine(parsed, time.max if end else time.min)
    return dt.replace(tzinfo=UTC)


def _disabled() -> JSONResponse:
    """Return 501 response indicating AI feature is disabled."""
    return JSONResponse({"ok": False, "error": "ai_disabled"}, status_code=501)


def _rate_limited() -> JSONResponse:
    """Return 429 response indicating AI rate limit exceeded."""
    return JSONResponse({"ok": False, "error": "rate_limited"}, status_code=429)


@router.get("/candidates/{candidate_id}/summary")
async def api_ai_candidate_summary(
    candidate_id: int,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    """Get AI-generated candidate summary (cached)."""
    try:
        result = await ai.get_candidate_summary(candidate_id, principal=principal, refresh=False)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, "summary": result.payload})


@router.post("/candidates/{candidate_id}/summary/refresh")
@limiter.limit("5/minute", key_func=get_principal_identifier)
async def api_ai_candidate_summary_refresh(
    candidate_id: int,
    request: Request,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    """Force regenerate candidate summary, bypassing cache."""
    _ = await require_csrf_token(request)
    try:
        result = await ai.get_candidate_summary(candidate_id, principal=principal, refresh=True)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, "summary": result.payload})


@router.get("/candidates/{candidate_id}/coach")
async def api_ai_candidate_coach(
    candidate_id: int,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    try:
        result = await ai.get_candidate_coach(candidate_id, principal=principal, refresh=False)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, "coach": result.payload})


@router.post("/candidates/{candidate_id}/coach/refresh")
async def api_ai_candidate_coach_refresh(
    candidate_id: int,
    request: Request,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    _ = await require_csrf_token(request)
    try:
        result = await ai.get_candidate_coach(candidate_id, principal=principal, refresh=True)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, "coach": result.payload})


@router.post("/candidates/{candidate_id}/coach/drafts")
async def api_ai_candidate_coach_drafts(
    candidate_id: int,
    request: Request,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    _ = await require_csrf_token(request)
    payload = await request.json()
    mode = "neutral"
    if isinstance(payload, dict) and payload.get("mode"):
        mode = str(payload.get("mode"))
    if mode not in {"short", "neutral", "supportive"}:
        raise HTTPException(status_code=400, detail={"message": "Некорректный mode"})
    try:
        result = await ai.get_candidate_coach_drafts(candidate_id, principal=principal, mode=mode)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, **result.payload})


@router.get("/candidates/{candidate_id}/interview-script")
async def api_ai_candidate_interview_script(
    candidate_id: int,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    try:
        result = await ai.get_candidate_interview_script(candidate_id, principal=principal, refresh=False)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    payload = result.payload if isinstance(result.payload, dict) else {}
    return JSONResponse(
        {
            "ok": True,
            "cached": result.cached,
            "input_hash": result.input_hash,
            "generated_at": payload.get("generated_at"),
            "model": payload.get("model"),
            "prompt_version": payload.get("prompt_version"),
            "script": payload.get("script") if isinstance(payload.get("script"), dict) else payload,
        }
    )


@router.post("/candidates/{candidate_id}/interview-script/refresh")
@limiter.limit("5/minute", key_func=get_principal_identifier)
async def api_ai_candidate_interview_script_refresh(
    candidate_id: int,
    request: Request,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    _ = await require_csrf_token(request)
    try:
        result = await ai.get_candidate_interview_script(candidate_id, principal=principal, refresh=True)
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    payload = result.payload if isinstance(result.payload, dict) else {}
    return JSONResponse(
        {
            "ok": True,
            "cached": result.cached,
            "input_hash": result.input_hash,
            "generated_at": payload.get("generated_at"),
            "model": payload.get("model"),
            "prompt_version": payload.get("prompt_version"),
            "script": payload.get("script") if isinstance(payload.get("script"), dict) else payload,
        }
    )


@router.put("/candidates/{candidate_id}/hh-resume")
async def api_ai_candidate_hh_resume_upsert(
    candidate_id: int,
    request: Request,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    _ = await require_csrf_token(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail={"message": "Ожидался JSON"})
    format_value = str(payload.get("format") or "").strip().lower()
    if format_value not in {"json", "raw_text"}:
        raise HTTPException(status_code=400, detail={"message": "format должен быть json или raw_text"})

    resume_json = payload.get("resume_json")
    resume_text = payload.get("resume_text")
    if format_value == "json":
        if not isinstance(resume_json, dict):
            raise HTTPException(status_code=400, detail={"message": "Для format=json требуется resume_json"})
    else:
        if resume_text is None:
            resume_text = ""
        if not isinstance(resume_text, str):
            raise HTTPException(status_code=400, detail={"message": "Для format=raw_text требуется resume_text"})

    try:
        result = await ai.upsert_candidate_hh_resume(
            candidate_id,
            principal=principal,
            format=format_value,
            resume_json=resume_json if isinstance(resume_json, dict) else None,
            resume_text=str(resume_text) if isinstance(resume_text, str) else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    return JSONResponse({"ok": True, **result})


@router.post("/candidates/{candidate_id}/interview-script/feedback")
@limiter.limit("15/minute", key_func=get_principal_identifier)
async def api_ai_candidate_interview_script_feedback(
    candidate_id: int,
    request: Request,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    _ = await require_csrf_token(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail={"message": "Ожидался JSON"})
    try:
        result = await ai.save_interview_script_feedback(candidate_id, principal=principal, payload=payload)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    return JSONResponse({"ok": True, **result})


@router.post("/candidates/{candidate_id}/chat/drafts")
@limiter.limit("5/minute", key_func=get_principal_identifier)
async def api_ai_chat_drafts(
    candidate_id: int,
    request: Request,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    """Generate AI chat reply drafts for candidate in specified mode."""
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
@limiter.limit("5/minute", key_func=get_principal_identifier)
async def api_ai_dashboard_insights(
    request: Request,
    principal: Principal = admin_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    """Generate AI insights for dashboard based on funnel, pipeline, and notification metrics."""
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Ожидался JSON"})
    date_from = _parse_date_param(data.get("date_from"))
    date_to = _parse_date_param(data.get("date_to"), end=True)
    city_id = data.get("city_id")
    city_name: str | None = None
    scope_id = 0
    if city_id is not None:
        try:
            city_id_value = int(city_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail={"message": "Некорректный city_id"}) from exc
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


@router.get("/cities/{city_id}/candidates/recommendations")
async def api_ai_city_candidate_recommendations(
    city_id: int,
    limit: int = 30,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    """Get AI candidate recommendations for a specific city."""
    limit_value = max(1, min(int(limit or 30), 80))
    try:
        result = await ai.get_city_candidate_recommendations(
            city_id,
            principal=principal,
            limit=limit_value,
            refresh=False,
        )
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, **result.payload})


@router.post("/cities/{city_id}/candidates/recommendations/refresh")
@limiter.limit("5/minute", key_func=get_principal_identifier)
async def api_ai_city_candidate_recommendations_refresh(
    city_id: int,
    request: Request,
    principal: Principal = principal_dep,
    ai: AIService = ai_dep,
) -> JSONResponse:
    """Force regenerate AI candidate recommendations for city, bypassing cache."""
    _ = await require_csrf_token(request)
    limit_value = 30
    try:
        body = await request.json()
        if isinstance(body, dict) and body.get("limit") is not None:
            limit_value = int(body.get("limit"))
    except Exception:
        limit_value = 30
    limit_value = max(1, min(int(limit_value or 30), 80))
    try:
        result = await ai.get_city_candidate_recommendations(
            city_id,
            principal=principal,
            limit=limit_value,
            refresh=True,
        )
    except AIDisabledError:
        return _disabled()
    except AIRateLimitedError:
        return _rate_limited()
    return JSONResponse({"ok": True, "cached": result.cached, "input_hash": result.input_hash, **result.payload})
