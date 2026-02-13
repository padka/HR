from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select

from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain import analytics
from backend.domain.ai.models import AIOutput, AIRequestLog
from backend.domain.candidates.models import User
from backend.domain.models import Recruiter

from .context import (
    build_candidate_ai_context,
    build_city_candidate_recommendations_context,
    compute_input_hash,
    get_last_inbound_message_text,
)
from .prompts import (
    candidate_summary_prompts,
    chat_reply_drafts_prompts,
    city_candidate_recommendations_prompts,
    dashboard_insight_prompts,
)
from .providers import AIProvider, AIProviderError, FakeProvider, OpenAIProvider
from .redaction import redact_text
from .schemas import CandidateSummaryV1, ChatReplyDraftsV1, CityCandidateRecommendationsV1, DashboardInsightV1

logger = logging.getLogger(__name__)


class AIDisabledError(RuntimeError):
    pass


class AIRateLimitedError(RuntimeError):
    pass


@dataclass(frozen=True)
class AIResult:
    payload: dict
    cached: bool
    input_hash: str


def _provider_for_settings() -> AIProvider:
    settings = get_settings()
    provider = (settings.ai_provider or "").strip().lower()
    if provider == "fake":
        return FakeProvider()
    return OpenAIProvider(settings)


async def _count_today_requests(principal: Principal) -> int:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    async with async_session() as session:
        total = await session.scalar(
            select(func.count(AIRequestLog.id))
            .where(
                AIRequestLog.principal_type == principal.type,
                AIRequestLog.principal_id == principal.id,
                AIRequestLog.created_at >= start,
            )
        )
        return int(total or 0)


async def _log_request(
    *,
    principal: Principal,
    scope_type: str,
    scope_id: int,
    kind: str,
    provider: str,
    model: str,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
    status_value: str,
    error_code: str = "",
) -> None:
    async with async_session() as session:
        row = AIRequestLog(
            principal_type=principal.type,
            principal_id=principal.id,
            scope_type=scope_type,
            scope_id=scope_id,
            kind=kind,
            provider=provider,
            model=model or "",
            latency_ms=int(latency_ms),
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            status=status_value,
            error_code=error_code or "",
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.commit()


async def _get_cached_output(
    *,
    scope_type: str,
    scope_id: int,
    kind: str,
    input_hash: str,
) -> Optional[AIOutput]:
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        row = await session.scalar(
            select(AIOutput)
            .where(
                AIOutput.scope_type == scope_type,
                AIOutput.scope_id == scope_id,
                AIOutput.kind == kind,
                AIOutput.input_hash == input_hash,
                AIOutput.expires_at > now,
            )
            .order_by(AIOutput.created_at.desc(), AIOutput.id.desc())
            .limit(1)
        )
        return row


async def _store_output(
    *,
    scope_type: str,
    scope_id: int,
    kind: str,
    input_hash: str,
    payload: dict,
    ttl_hours: int = 24,
) -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=ttl_hours)
    async with async_session() as session:
        existing = await session.scalar(
            select(AIOutput).where(
                AIOutput.scope_type == scope_type,
                AIOutput.scope_id == scope_id,
                AIOutput.kind == kind,
                AIOutput.input_hash == input_hash,
            )
        )
        if existing is not None:
            existing.payload_json = payload
            existing.expires_at = expires_at
            existing.created_at = now
        else:
            session.add(
                AIOutput(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    kind=kind,
                    input_hash=input_hash,
                    payload_json=payload,
                    created_at=now,
                    expires_at=expires_at,
                )
            )
        await session.commit()


class AIService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._provider = _provider_for_settings()

    def _ensure_enabled(self) -> None:
        if not self._settings.ai_enabled:
            raise AIDisabledError("ai_disabled")

    async def _ensure_quota(self, principal: Principal) -> None:
        limit = int(self._settings.ai_max_requests_per_principal_per_day or 0)
        if limit <= 0:
            return
        used = await _count_today_requests(principal)
        if used >= limit:
            raise AIRateLimitedError("rate_limited")

    async def get_candidate_summary(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        refresh: bool = False,
    ) -> AIResult:
        self._ensure_enabled()
        ctx = await build_candidate_ai_context(candidate_id, principal=principal)
        input_hash = compute_input_hash(ctx)
        kind = "candidate_summary_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                # View metrics: safe, aggregated
                try:
                    await analytics.log_event(
                        "ai_summary_viewed",
                        candidate_id=candidate_id,
                        metadata={"cached": True, "kind": kind},
                    )
                except Exception:  # pragma: no cover - analytics is non-critical
                    pass
                return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

        await self._ensure_quota(principal)

        system_prompt, user_prompt = candidate_summary_prompts(context=ctx)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = CandidateSummaryV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            try:
                await analytics.log_event(
                    "ai_summary_generated",
                    candidate_id=candidate_id,
                    metadata={"kind": kind},
                )
                await analytics.log_event(
                    "ai_summary_viewed",
                    candidate_id=candidate_id,
                    metadata={"cached": False, "kind": kind},
                )
            except Exception:  # pragma: no cover
                pass
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except (AIProviderError, Exception) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.candidate_summary.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            )

    async def get_chat_reply_drafts(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        mode: str,
    ) -> AIResult:
        self._ensure_enabled()
        base_ctx = await build_candidate_ai_context(candidate_id, principal=principal)

        inbound_raw = await get_last_inbound_message_text(candidate_id, principal=principal)
        candidate_fio = None
        recruiter_name = None
        try:
            async with async_session() as session:
                user = await session.get(User, candidate_id)
                if user is not None:
                    candidate_fio = user.fio
                if principal.type == "recruiter":
                    recruiter = await session.get(Recruiter, principal.id)
                    recruiter_name = recruiter.name if recruiter is not None else None
        except Exception:  # pragma: no cover - redaction helper should never break flow
            candidate_fio = None
            recruiter_name = None
        redaction = redact_text(
            inbound_raw or "",
            candidate_fio=candidate_fio,
            recruiter_name=recruiter_name,
        )
        ctx = dict(base_ctx)
        ctx["inbound_message"] = {
            "present": bool(inbound_raw),
            "safe_text_used": bool(inbound_raw) and redaction.safe_to_send,
            "text": redaction.text if inbound_raw and redaction.safe_to_send else None,
        }
        ctx["draft_mode"] = mode

        input_hash = compute_input_hash(ctx)
        kind = "reply_drafts_v1"

        cached = await _get_cached_output(
            scope_type="candidate",
            scope_id=candidate_id,
            kind=kind,
            input_hash=input_hash,
        )
        if cached is not None:
            return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

        await self._ensure_quota(principal)

        system_prompt, user_prompt = chat_reply_drafts_prompts(context=ctx, mode=mode)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = ChatReplyDraftsV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            try:
                await analytics.log_event(
                    "ai_drafts_generated",
                    candidate_id=candidate_id,
                    metadata={"kind": kind, "mode": mode},
                )
            except Exception:  # pragma: no cover
                pass
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.chat_drafts.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            )

    async def get_dashboard_insights(
        self,
        *,
        principal: Principal,
        context: dict[str, Any],
        scope_id: int = 0,
        refresh: bool = False,
    ) -> AIResult:
        self._ensure_enabled()
        input_hash = compute_input_hash(context)
        kind = "dashboard_insight_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="dashboard",
                scope_id=scope_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

        await self._ensure_quota(principal)
        system_prompt, user_prompt = dashboard_insight_prompts(context=context)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = DashboardInsightV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="dashboard",
                scope_id=scope_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="dashboard",
                scope_id=scope_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="dashboard",
                scope_id=scope_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            )

    async def get_city_candidate_recommendations(
        self,
        city_id: int,
        *,
        principal: Principal,
        limit: int = 30,
        refresh: bool = False,
    ) -> AIResult:
        self._ensure_enabled()
        ctx = await build_city_candidate_recommendations_context(city_id, principal=principal, limit=limit)
        input_hash = compute_input_hash(ctx)
        kind = "city_candidate_recommendations_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="city",
                scope_id=city_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

        await self._ensure_quota(principal)

        system_prompt, user_prompt = city_candidate_recommendations_prompts(context=ctx)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = CityCandidateRecommendationsV1.model_validate(payload).model_dump()
            try:
                allowed_ids = {
                    int(item.get("id"))
                    for item in ((ctx.get("candidates") or {}).get("items") or [])
                    if isinstance(item, dict) and isinstance(item.get("id"), int)
                }
                recs = validated.get("recommended") or []
                filtered = []
                for rec in recs:
                    if not isinstance(rec, dict):
                        continue
                    cid = rec.get("candidate_id")
                    if isinstance(cid, int) and cid in allowed_ids:
                        filtered.append(rec)
                validated["recommended"] = filtered[:10]
                validated["criteria_used"] = bool((ctx.get("city") or {}).get("criteria_present"))
            except Exception:  # pragma: no cover - best-effort guardrail
                pass
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="city",
                scope_id=city_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="city",
                scope_id=city_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="city",
                scope_id=city_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.city_recommendations.failed", extra={"city_id": city_id}, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            )


def get_ai_service() -> AIService:
    return AIService()
