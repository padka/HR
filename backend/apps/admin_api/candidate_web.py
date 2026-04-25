"""Bounded browser candidate pilot surface."""

from __future__ import annotations

import hashlib
import os
import re
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_api.candidate_access.auth import (
    CANDIDATE_ACCESS_SESSION_HEADER,
    CandidateAccessPrincipal,
    get_web_candidate_access_principal,
    is_candidate_social_verified,
)
from backend.apps.admin_api.candidate_access.router import (
    BookingInfo,
    CancelBookingRequest,
    CandidateBookingCityInfo,
    CandidateBookingContextInfo,
    CandidateBookingContextRequest,
    CandidateBookingRecruiterInfo,
    CandidateInfo,
    CandidateIntroDayResponse,
    CandidateJourneyResponse,
    CandidateManualAvailabilityRequest,
    CandidateManualAvailabilityResponse,
    CandidateTest1AnswersRequest,
    CandidateTest1Response,
    CandidateTest2AnswerRequest,
    CandidateTest2Response,
    CreateBookingRequest,
    RescheduleBookingRequest,
    SlotInfo,
)
from backend.apps.admin_api.candidate_access.router import (
    cancel_candidate_access_booking as _shared_cancel_booking,
)
from backend.apps.admin_api.candidate_access.router import (
    complete_candidate_access_test1 as _shared_complete_test1,
)
from backend.apps.admin_api.candidate_access.router import (
    confirm_candidate_access_booking as _shared_confirm_booking,
)
from backend.apps.admin_api.candidate_access.router import (
    confirm_candidate_access_intro_day as _shared_confirm_intro_day,
)
from backend.apps.admin_api.candidate_access.router import (
    create_candidate_access_booking as _shared_create_booking,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_booking_context as _shared_get_booking_context,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_cities as _shared_get_cities,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_intro_day as _shared_get_intro_day,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_journey as _shared_get_journey,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_me as _shared_get_me,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_recruiters as _shared_get_recruiters,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_slots as _shared_get_slots,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_test1 as _shared_get_test1,
)
from backend.apps.admin_api.candidate_access.router import (
    get_candidate_access_test2 as _shared_get_test2,
)
from backend.apps.admin_api.candidate_access.router import (
    reschedule_candidate_access_booking as _shared_reschedule_booking,
)
from backend.apps.admin_api.candidate_access.router import (
    save_candidate_access_booking_context as _shared_save_booking_context,
)
from backend.apps.admin_api.candidate_access.router import (
    save_candidate_access_manual_availability as _shared_save_manual_availability,
)
from backend.apps.admin_api.candidate_access.router import (
    save_candidate_access_test1_answers as _shared_save_test1_answers,
)
from backend.apps.admin_api.candidate_access.router import (
    submit_candidate_access_test2_answer as _shared_submit_test2_answer,
)
from backend.apps.admin_api.max_launch import _sqlite_next_pk
from backend.core.dependencies import get_async_session
from backend.core.settings import Settings, get_settings
from backend.domain.candidates.journey import append_journey_event
from backend.domain.candidates.max_launch_invites import (
    MaxLaunchInviteError,
    create_max_launch_invite,
)
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessSessionStatus,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneyEvent,
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    CandidateWebCampaign,
    CandidateWebPublicIntake,
    User,
)
from backend.domain.candidates.public_intake import (
    INTAKE_STATUS_CONFLICT,
    INTAKE_STATUS_EXPIRED,
    INTAKE_STATUS_FAILED,
    INTAKE_STATUS_SESSION_ISSUED,
    INTAKE_STATUS_VERIFIED,
    PUBLIC_PROVIDER_HH,
    PUBLIC_PROVIDER_MAX,
    PUBLIC_PROVIDER_TELEGRAM,
    campaign_is_available,
    create_public_intake,
    find_or_create_public_candidate,
    generate_public_token,
    get_public_campaign_by_slug,
    hash_public_token,
    normalize_campaign_slug,
    normalize_public_provider,
    sanitize_allowed_public_providers,
)
from backend.domain.candidates.services import (
    bind_max_to_candidate,
    bind_telegram_to_candidate,
    ensure_candidate_invite_token,
)
from backend.domain.hh_integration.candidate_import import (
    CandidateHHIdentityConflict,
    candidate_has_hh_contact,
    is_candidate_hh_verified,
    upsert_candidate_hh_identity,
)
from backend.domain.hh_integration.client import HHApiClient, HHApiError
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    HHResumeSnapshot,
)
from backend.domain.hh_integration.oauth import (
    build_hh_candidate_authorize_url,
    build_hh_public_candidate_authorize_url,
    parse_hh_candidate_oauth_state,
    parse_hh_public_candidate_oauth_state,
)
from backend.domain.models import City

api_router = APIRouter(tags=["candidate-web"])
shell_router = APIRouter(tags=["candidate-web-shell"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPA_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
SPA_INDEX_FILE = SPA_DIST_DIR / "index.html"

WEB_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~=-]{16,512}$")
WEB_ACCESS_SESSION_IDLE_TTL = timedelta(hours=8)
BOOTSTRAP_RATE_LIMIT_WINDOW_SECONDS = 60
BOOTSTRAP_RATE_LIMIT_MAX_ATTEMPTS = 20
MUTATION_RATE_LIMIT_WINDOW_SECONDS = 60
MUTATION_RATE_LIMIT_MAX_ATTEMPTS = 30
_bootstrap_attempts: dict[str, deque[float]] = defaultdict(deque)
_mutation_attempts: dict[str, deque[float]] = defaultdict(deque)


class CandidateWebBootstrapRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=512)
    source: str | None = Field(default=None, max_length=64)
    utm: dict[str, str] = Field(default_factory=dict, max_length=12)


class CandidateWebCandidateSummary(BaseModel):
    id: int
    candidate_id: str
    application_id: int | None = None


class CandidateWebSessionSummary(BaseModel):
    session_id: str
    journey_session_id: int
    status: str
    surface: str
    auth_method: str
    launch_channel: str
    expires_at: datetime
    reused: bool


class CandidateWebBootstrapResponse(BaseModel):
    ok: bool = True
    surface: str = CandidateJourneySurface.STANDALONE_WEB.value
    auth_method: str = CandidateAccessAuthMethod.SIGNED_LINK.value
    candidate: CandidateWebCandidateSummary
    session: CandidateWebSessionSummary


class CandidateVerificationChannelInfo(BaseModel):
    available: bool
    verified: bool = False
    status: str
    label: str
    url: str | None = None
    start_param: str | None = None
    expires_at: datetime | None = None
    reason: str | None = None
    local_confirm_available: bool = False


class CandidateHHResumeInfo(BaseModel):
    resume_id: str | None = None
    url: str | None = None
    title: str | None = None
    city: str | None = None
    synced_at: datetime | None = None
    import_status: str | None = None
    contact_available: bool = False


class CandidateVerificationResponse(BaseModel):
    verified: bool
    booking_ready: bool = False
    required_before: list[str] = Field(
        default_factory=lambda: ["test1", "booking", "manual_availability"]
    )
    available_channels: list[str] = Field(default_factory=list)
    telegram: CandidateVerificationChannelInfo
    max: CandidateVerificationChannelInfo
    hh: CandidateVerificationChannelInfo
    hh_resume: CandidateHHResumeInfo | None = None


class PublicCampaignResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    title: str
    status: str
    available: bool
    allowed_providers: list[str]
    city_label: str | None = None
    source_label: str | None = None
    copy_text: dict[str, str] = Field(default_factory=dict, alias="copy")
    availability_flags: dict[str, bool] = Field(default_factory=dict)


class PublicVerificationStartRequest(BaseModel):
    utm: dict[str, str] = Field(default_factory=dict, max_length=12)


class PublicVerificationStartResponse(BaseModel):
    provider: str
    available: bool
    url: str | None = None
    poll_token: str | None = None
    start_param: str | None = None
    expires_at: datetime | None = None
    reason: str | None = None
    local_confirm_available: bool = False


class PublicVerificationStatusResponse(BaseModel):
    status: str
    provider: str | None = None
    verified: bool = False
    handoff_available: bool = False
    handoff_code: str | None = None
    reason: str | None = None
    expires_at: datetime | None = None


class PublicSessionExchangeRequest(BaseModel):
    handoff_code: str = Field(..., min_length=16, max_length=256)
    source: str | None = Field(default="web", max_length=64)
    utm: dict[str, str] = Field(default_factory=dict, max_length=12)


class PublicLocalConfirmRequest(BaseModel):
    poll_token: str = Field(..., min_length=16, max_length=256)
    provider: str = Field(default=PUBLIC_PROVIDER_TELEGRAM, max_length=24)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _raise_candidate_web_http_error(
    *,
    status_code: int,
    code: str,
    message: str,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _normalize_web_token(raw_token: str) -> str:
    token = str(raw_token or "").strip()
    if not WEB_TOKEN_RE.fullmatch(token):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_link",
            message="Candidate link is invalid.",
        )
    return token


def _hash_web_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _sanitize_tracking(request: CandidateWebBootstrapRequest) -> dict[str, Any]:
    source = str(request.source or "web").strip().lower() or "web"
    if source not in {"web", "browser", "candidate_web", "standalone_web"}:
        source = "web"
    utm: dict[str, str] = {}
    allowed_keys = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "ref",
    }
    for key, value in dict(request.utm or {}).items():
        clean_key = str(key or "").strip().lower()
        clean_value = str(value or "").strip()
        if clean_key in allowed_keys and clean_value:
            utm[clean_key] = clean_value[:160]
    return {"source": source, "utm": utm}


def _bootstrap_rate_limit_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _mutation_rate_limit_key(request: Request) -> str:
    ip_key = _bootstrap_rate_limit_key(request)
    session_token = str(request.headers.get(CANDIDATE_ACCESS_SESSION_HEADER, "") or "").strip()
    session_key = hashlib.sha256(session_token.encode("utf-8")).hexdigest()[:16] if session_token else "missing"
    return f"{ip_key}:{session_key}"


def _enforce_rate_limit_bucket(
    *,
    attempts: dict[str, deque[float]],
    key: str,
    max_attempts: int,
    window_seconds: int,
    code: str,
    message: str,
) -> None:
    now = time.monotonic()
    bucket = attempts[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= max_attempts:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code=code,
            message=message,
        )
    bucket.append(now)


def _enforce_bootstrap_rate_limit(request: Request, settings: Settings) -> None:
    if not getattr(settings, "rate_limit_enabled", False):
        return
    _enforce_rate_limit_bucket(
        attempts=_bootstrap_attempts,
        key=_bootstrap_rate_limit_key(request),
        max_attempts=BOOTSTRAP_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=BOOTSTRAP_RATE_LIMIT_WINDOW_SECONDS,
        code="rate_limited",
        message="Too many candidate link attempts. Try again later.",
    )


def _enforce_mutation_rate_limit(request: Request, settings: Settings) -> None:
    if not getattr(settings, "rate_limit_enabled", False):
        return
    _enforce_rate_limit_bucket(
        attempts=_mutation_attempts,
        key=_mutation_rate_limit_key(request),
        max_attempts=MUTATION_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=MUTATION_RATE_LIMIT_WINDOW_SECONDS,
        code="rate_limited",
        message="Too many candidate actions. Try again later.",
    )


def _build_telegram_deep_link(token: str) -> str | None:
    bot_name = (
        os.getenv("TELEGRAM_PUBLIC_BOT_NAME")
        or os.getenv("TELEGRAM_BOT_USERNAME")
        or os.getenv("BOT_USERNAME")
        or ""
    ).strip()
    if not bot_name:
        return None
    return f"https://t.me/{bot_name.lstrip('@')}?start={token}"


def _local_verification_available(settings: Settings) -> bool:
    explicit_flag = os.getenv("CANDIDATE_WEB_LOCAL_VERIFICATION_ENABLED")
    if explicit_flag is not None:
        return explicit_flag.strip().lower() in {"1", "true", "yes", "on"}
    return str(getattr(settings, "environment", "") or "").strip().lower() in {
        "development",
        "test",
    }


def _max_verification_available(settings: Settings) -> bool:
    return bool(
        getattr(settings, "max_adapter_enabled", False)
        and str(getattr(settings, "max_bot_token", "") or "").strip()
        and (
            str(getattr(settings, "max_public_bot_name", "") or "").strip()
            or str(getattr(settings, "max_miniapp_url", "") or "").strip()
        )
    )


def _hh_candidate_oauth_available(settings: Settings) -> bool:
    return bool(
        getattr(settings, "hh_candidate_oauth_enabled", False)
        and str(getattr(settings, "hh_candidate_client_id", "") or "").strip()
        and str(getattr(settings, "hh_candidate_client_secret", "") or "").strip()
        and str(getattr(settings, "hh_candidate_redirect_uri", "") or "").strip()
    )


def _hh_unavailable_reason(settings: Settings) -> str | None:
    if not getattr(settings, "hh_candidate_oauth_enabled", False):
        return "hh_oauth_disabled"
    if not str(getattr(settings, "hh_candidate_client_id", "") or "").strip():
        return "hh_candidate_client_id_missing"
    if not str(getattr(settings, "hh_candidate_client_secret", "") or "").strip():
        return "hh_candidate_client_secret_missing"
    if not str(getattr(settings, "hh_candidate_redirect_uri", "") or "").strip():
        return "hh_candidate_redirect_uri_missing"
    return None


async def _build_hh_resume_info(
    session: AsyncSession,
    candidate: User,
) -> CandidateHHResumeInfo | None:
    identity = await session.scalar(
        select(CandidateExternalIdentity).where(
            CandidateExternalIdentity.candidate_id == int(candidate.id),
            CandidateExternalIdentity.source == "hh",
        )
    )
    if identity is None and not str(candidate.hh_resume_id or "").strip():
        return None

    resume_id = (
        str(identity.external_resume_id or "").strip()
        if identity is not None
        else str(candidate.hh_resume_id or "").strip()
    ) or None
    resume_url = str(identity.external_resume_url or "").strip() if identity is not None else ""
    resume_title = None
    resume_city = None
    synced_at = candidate.hh_synced_at or (identity.last_hh_sync_at if identity is not None else None)

    if resume_id:
        snapshot = await session.scalar(
            select(HHResumeSnapshot)
            .where(HHResumeSnapshot.external_resume_id == resume_id)
            .order_by(desc(HHResumeSnapshot.fetched_at), desc(HHResumeSnapshot.id))
            .limit(1)
        )
        payload = snapshot.payload_json if snapshot and isinstance(snapshot.payload_json, dict) else {}
        resume_url = resume_url or str(payload.get("alternate_url") or payload.get("url") or "").strip()
        for key in ("title", "position", "desired_position", "headline"):
            value = str(payload.get(key) or "").strip()
            if value:
                resume_title = value
                break
        area = payload.get("area")
        if isinstance(area, dict):
            resume_city = str(area.get("name") or "").strip() or None
        if synced_at is None and snapshot is not None:
            synced_at = snapshot.fetched_at

    return CandidateHHResumeInfo(
        resume_id=resume_id,
        url=resume_url or (f"https://hh.ru/resume/{resume_id}" if resume_id else None),
        title=resume_title or candidate.desired_position,
        city=resume_city or candidate.city,
        synced_at=_as_utc(synced_at),
        import_status=candidate.hh_sync_status or (identity.sync_status if identity is not None else None),
        contact_available=candidate_has_hh_contact(candidate),
    )


async def _build_verification_response(
    candidate: User,
    *,
    session: AsyncSession,
    settings: Settings,
    telegram_start_param: str | None = None,
    telegram_url: str | None = None,
    telegram_expires_at: datetime | None = None,
    max_start_param: str | None = None,
    max_url: str | None = None,
    max_expires_at: datetime | None = None,
    hh_url: str | None = None,
) -> CandidateVerificationResponse:
    telegram_verified = bool(candidate.telegram_id or candidate.telegram_user_id)
    max_verified = bool(str(candidate.max_user_id or "").strip())
    hh_verified = await is_candidate_hh_verified(session, int(candidate.id))
    max_available = _max_verification_available(settings)
    hh_available = _hh_candidate_oauth_available(settings)
    available_channels = ["telegram"]
    if max_available:
        available_channels.append("max")
    if hh_available:
        available_channels.append("hh")

    telegram_reason = None if telegram_url else "telegram_bot_username_missing"
    max_reason = None if max_available else "max_unavailable_in_local_environment"
    hh_reason = None if hh_available else _hh_unavailable_reason(settings)
    local_confirm_available = _local_verification_available(settings)
    booking_ready = bool(telegram_verified or max_verified or (hh_verified and candidate_has_hh_contact(candidate)))
    return CandidateVerificationResponse(
        verified=telegram_verified or max_verified or hh_verified,
        booking_ready=booking_ready,
        available_channels=available_channels,
        telegram=CandidateVerificationChannelInfo(
            available=True,
            verified=telegram_verified,
            status="verified" if telegram_verified else "available",
            label="Telegram",
            url=telegram_url,
            start_param=telegram_start_param,
            expires_at=telegram_expires_at,
            reason=telegram_reason,
            local_confirm_available=local_confirm_available,
        ),
        max=CandidateVerificationChannelInfo(
            available=max_available,
            verified=max_verified,
            status="verified"
            if max_verified
            else ("available" if max_available else "unavailable"),
            label="MAX",
            url=max_url,
            start_param=max_start_param,
            expires_at=max_expires_at,
            reason=max_reason,
            local_confirm_available=local_confirm_available,
        ),
        hh=CandidateVerificationChannelInfo(
            available=hh_available,
            verified=hh_verified,
            status="verified"
            if hh_verified
            else ("available" if hh_available else "unavailable"),
            label="hh.ru",
            url=hh_url,
            reason=hh_reason,
            local_confirm_available=local_confirm_available,
        ),
        hh_resume=await _build_hh_resume_info(session, candidate),
    )


async def _candidate_has_identity_verification(
    session: AsyncSession,
    candidate: User,
) -> bool:
    if is_candidate_social_verified(candidate):
        return True
    return await is_candidate_hh_verified(session, int(candidate.id))


async def _ensure_candidate_web_booking_ready(
    principal: CandidateAccessPrincipal,
    session: AsyncSession,
) -> User:
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    social_verified = is_candidate_social_verified(candidate)
    hh_verified = await is_candidate_hh_verified(session, int(candidate.id))
    if not social_verified and not (hh_verified and candidate_has_hh_contact(candidate)):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="social_verification_required",
            message="Подтвердите Telegram или MAX либо импортируйте контакт из hh.ru, чтобы выбрать время.",
        )
    await session.rollback()
    return candidate


async def _ensure_candidate_web_test_access(
    principal: CandidateAccessPrincipal,
    session: AsyncSession,
) -> User:
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    if not await _candidate_has_identity_verification(session, candidate):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="social_verification_required",
            message="Подтвердите Telegram, MAX или hh.ru, чтобы открыть анкету.",
        )
    await session.rollback()
    return candidate


async def _load_browser_token(
    session: AsyncSession,
    *,
    token_hash: str,
    now: datetime,
) -> CandidateAccessToken:
    result = await session.execute(
        select(CandidateAccessToken)
        .where(CandidateAccessToken.token_hash == token_hash)
        .order_by(CandidateAccessToken.created_at.desc(), CandidateAccessToken.id.desc())
        .limit(1)
        .with_for_update()
    )
    token = result.scalar_one_or_none()
    if token is None:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="candidate_link_not_found",
            message="Candidate link was not found.",
        )
    if token.token_kind not in {
        CandidateAccessTokenKind.INVITE.value,
        CandidateAccessTokenKind.LAUNCH.value,
        CandidateAccessTokenKind.RESUME.value,
    }:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="candidate_link_invalid",
            message="Candidate link is not valid for browser access.",
        )
    if token.journey_surface != CandidateJourneySurface.STANDALONE_WEB.value:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_link_surface_mismatch",
            message="Candidate link is not valid for browser access.",
        )
    if token.auth_method != CandidateAccessAuthMethod.SIGNED_LINK.value:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_link_auth_method_mismatch",
            message="Candidate link is not valid for signed-link browser access.",
        )
    if token.launch_channel != CandidateLaunchChannel.WEB.value:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_link_channel_mismatch",
            message="Candidate link is not valid for browser channel access.",
        )
    if token.revoked_at is not None:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_410_GONE,
            code="candidate_link_revoked",
            message="Candidate link has been revoked.",
        )
    token_expires_at = _as_utc(token.expires_at)
    if token_expires_at is None or token_expires_at <= now:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_410_GONE,
            code="candidate_link_expired",
            message="Candidate link has expired.",
        )
    return token


async def _load_candidate_or_raise(session: AsyncSession, candidate_id: int) -> User:
    candidate = await session.get(User, candidate_id)
    if candidate is None or not candidate.is_active:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="candidate_unavailable",
            message="Candidate is no longer available.",
        )
    return candidate


async def _ensure_web_journey_session(
    session: AsyncSession,
    *,
    token: CandidateAccessToken,
    now: datetime,
    tracking: dict[str, Any],
) -> CandidateJourneySession:
    journey_session: CandidateJourneySession | None = None
    if token.journey_session_id is not None:
        journey_session = await session.get(CandidateJourneySession, token.journey_session_id)
        if journey_session is not None and journey_session.candidate_id != token.candidate_id:
            journey_session = None

    if journey_session is None:
        journey_session = CandidateJourneySession(
            candidate_id=token.candidate_id,
            application_id=token.application_id,
            journey_key="candidate_portal",
            journey_version="v1",
            entry_channel=CandidateLaunchChannel.WEB.value,
            current_step_key="test1",
            last_surface=CandidateJourneySurface.STANDALONE_WEB.value,
            last_auth_method=CandidateAccessAuthMethod.SIGNED_LINK.value,
            status=CandidateJourneySessionStatus.ACTIVE.value,
            payload_json={"candidate_web": tracking},
            last_activity_at=now,
        )
        session.add(journey_session)
        await session.flush()
        token.journey_session_id = journey_session.id
    else:
        if journey_session.application_id is None and token.application_id is not None:
            journey_session.application_id = token.application_id
        if str(journey_session.current_step_key or "").strip().lower() in {"", "profile"}:
            journey_session.current_step_key = "test1"
        journey_session.entry_channel = journey_session.entry_channel or CandidateLaunchChannel.WEB.value
        journey_session.last_surface = CandidateJourneySurface.STANDALONE_WEB.value
        journey_session.last_auth_method = CandidateAccessAuthMethod.SIGNED_LINK.value
        journey_session.last_activity_at = now
        if journey_session.status != CandidateJourneySessionStatus.ACTIVE.value:
            journey_session.status = CandidateJourneySessionStatus.ACTIVE.value
        payload = dict(journey_session.payload_json or {})
        payload["candidate_web"] = {**dict(payload.get("candidate_web") or {}), **tracking}
        journey_session.payload_json = payload

    return journey_session


async def _load_existing_web_access_session(
    session: AsyncSession,
    *,
    token: CandidateAccessToken,
    now: datetime,
) -> CandidateAccessSession | None:
    return await session.scalar(
        select(CandidateAccessSession)
        .where(
            CandidateAccessSession.origin_token_id == int(token.id),
            CandidateAccessSession.candidate_id == int(token.candidate_id),
            CandidateAccessSession.journey_surface == CandidateJourneySurface.STANDALONE_WEB.value,
            CandidateAccessSession.auth_method == CandidateAccessAuthMethod.SIGNED_LINK.value,
            CandidateAccessSession.launch_channel == CandidateLaunchChannel.WEB.value,
            CandidateAccessSession.status == CandidateAccessSessionStatus.ACTIVE.value,
            CandidateAccessSession.expires_at > now,
        )
        .order_by(CandidateAccessSession.issued_at.desc(), CandidateAccessSession.id.desc())
        .limit(1)
        .with_for_update()
    )


def _mark_candidate_web_visible(candidate: User, *, now: datetime) -> None:
    source_value = str(getattr(candidate, "source", "") or "").strip().lower()
    if source_value in {"", "bot", "candidate_access", "manual", "manual_silent"}:
        candidate.source = CandidateLaunchChannel.WEB.value
    has_telegram = bool(candidate.telegram_id or candidate.telegram_user_id or candidate.telegram_username)
    has_max = bool(str(getattr(candidate, "max_user_id", "") or "").strip())
    if not has_telegram and not has_max:
        candidate.messenger_platform = CandidateLaunchChannel.WEB.value
    candidate.last_activity = now


async def _bootstrap_browser_candidate(
    session: AsyncSession,
    *,
    request: CandidateWebBootstrapRequest,
) -> tuple[User, CandidateAccessToken, CandidateJourneySession, CandidateAccessSession, bool]:
    now = _utcnow()
    normalized_token = _normalize_web_token(request.token)
    token = await _load_browser_token(
        session,
        token_hash=_hash_web_token(normalized_token),
        now=now,
    )
    candidate = await _load_candidate_or_raise(session, int(token.candidate_id))
    tracking = _sanitize_tracking(request)
    journey_session = await _ensure_web_journey_session(
        session,
        token=token,
        now=now,
        tracking=tracking,
    )
    access_session = await _load_existing_web_access_session(session, token=token, now=now)

    reused = access_session is not None
    expires_at = now + WEB_ACCESS_SESSION_IDLE_TTL
    if access_session is None:
        access_session_id = await _sqlite_next_pk(session, CandidateAccessSession)
        access_session = CandidateAccessSession(
            id=access_session_id,
            candidate_id=int(candidate.id),
            application_id=token.application_id,
            journey_session_id=int(journey_session.id),
            origin_token_id=int(token.id),
            journey_surface=CandidateJourneySurface.STANDALONE_WEB.value,
            auth_method=CandidateAccessAuthMethod.SIGNED_LINK.value,
            launch_channel=CandidateLaunchChannel.WEB.value,
            provider_session_id=None,
            provider_user_id=str(candidate.id),
            session_version_snapshot=max(1, int(journey_session.session_version or 1)),
            phone_verification_state=token.phone_verification_state,
            phone_delivery_channel=token.phone_delivery_channel,
            status=CandidateAccessSessionStatus.ACTIVE.value,
            issued_at=now,
            last_seen_at=now,
            refreshed_at=now,
            expires_at=expires_at,
            correlation_id=token.correlation_id or str(uuid.uuid4()),
            metadata_json={"candidate_web": tracking},
        )
        session.add(access_session)
        await session.flush()
    else:
        access_session.last_seen_at = now
        access_session.refreshed_at = now
        access_session.expires_at = expires_at
        metadata = dict(access_session.metadata_json or {})
        metadata["candidate_web"] = {**dict(metadata.get("candidate_web") or {}), **tracking}
        access_session.metadata_json = metadata

    token.last_seen_at = now
    if token.consumed_at is None:
        token.consumed_at = now
    if token.session_version_snapshot is None:
        token.session_version_snapshot = max(1, int(journey_session.session_version or 1))

    journey_session.last_access_session_id = int(access_session.id)
    journey_session.last_surface = CandidateJourneySurface.STANDALONE_WEB.value
    journey_session.last_auth_method = CandidateAccessAuthMethod.SIGNED_LINK.value
    journey_session.last_activity_at = now
    _mark_candidate_web_visible(candidate, now=now)

    return candidate, token, journey_session, access_session, reused


def _feature_enabled(settings: Settings) -> bool:
    return bool(getattr(settings, "candidate_web_pilot_enabled", False))


def _public_intake_enabled(settings: Settings) -> bool:
    return bool(_feature_enabled(settings) and getattr(settings, "candidate_web_public_intake_enabled", False))


def _public_intake_ttl(settings: Settings) -> int:
    return max(60, int(getattr(settings, "candidate_web_public_intake_token_ttl_seconds", 900)))


def _public_handoff_ttl(settings: Settings) -> int:
    return max(60, int(getattr(settings, "candidate_web_public_handoff_ttl_seconds", 300)))


def _sanitize_public_utm(values: dict[str, str] | None) -> dict[str, str]:
    request = CandidateWebBootstrapRequest(
        token="placeholder-public-token-0001",
        source="web",
        utm=dict(values or {}),
    )
    return dict(_sanitize_tracking(request)["utm"])


def _public_allowed_providers(
    campaign: CandidateWebCampaign,
    settings: Settings,
) -> list[str]:
    return sanitize_allowed_public_providers(
        campaign.allowed_providers_json,
        defaults=tuple(getattr(settings, "candidate_web_public_intake_allowed_providers", ()) or ()),
    )


async def _load_public_campaign_or_raise(
    session: AsyncSession,
    *,
    slug: str,
    settings: Settings,
) -> CandidateWebCampaign:
    if not _public_intake_enabled(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="public_intake_disabled",
            message="Public candidate intake is disabled.",
        )
    campaign = await get_public_campaign_by_slug(session, slug)
    if campaign is None:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="campaign_not_found",
            message="Candidate campaign was not found.",
        )
    return campaign


async def _build_public_campaign_response(
    session: AsyncSession,
    *,
    campaign: CandidateWebCampaign,
    settings: Settings,
) -> PublicCampaignResponse:
    now = _utcnow()
    city_label = None
    if campaign.city_id is not None:
        city = await session.get(City, int(campaign.city_id))
        if city is not None:
            city_label = str(city.name or "").strip() or None
    allowed = _public_allowed_providers(campaign, settings)
    available = bool(_public_intake_enabled(settings) and campaign_is_available(campaign, now=now))
    return PublicCampaignResponse(
        slug=campaign.slug,
        title=campaign.title,
        status=campaign.status,
        available=available,
        allowed_providers=allowed,
        city_label=city_label,
        source_label=campaign.source_label,
        copy_text={
            "title": campaign.title,
            "subtitle": "Подтвердите профиль и заполните анкету кандидата.",
        },
        availability_flags={
            "telegram": PUBLIC_PROVIDER_TELEGRAM in allowed,
            "max": PUBLIC_PROVIDER_MAX in allowed and _max_verification_available(settings),
            "hh": PUBLIC_PROVIDER_HH in allowed and _hh_candidate_oauth_available(settings),
            "local_confirm": _local_verification_available(settings),
        },
    )


async def _ensure_public_campaign_available(
    session: AsyncSession,
    *,
    slug: str,
    provider: str,
    settings: Settings,
) -> CandidateWebCampaign:
    campaign = await _load_public_campaign_or_raise(session, slug=slug, settings=settings)
    now = _utcnow()
    if not campaign_is_available(campaign, now=now):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="campaign_unavailable",
            message="Candidate campaign is not available.",
        )
    allowed = _public_allowed_providers(campaign, settings)
    provider_value = normalize_public_provider(provider)
    if provider_value not in allowed:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="provider_not_allowed",
            message="This verification provider is not available for the campaign.",
        )
    return campaign


def _candidate_flow_redirect(marker: str) -> RedirectResponse:
    safe_marker = re.sub(r"[^a-z0-9_-]", "", str(marker or "error").lower()) or "error"
    return RedirectResponse(
        url=f"/candidate-flow?hh={safe_marker}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _candidate_public_flow_redirect(return_to: str | None, marker: str) -> RedirectResponse:
    safe_marker = re.sub(r"[^a-z0-9_-]", "", str(marker or "error").lower()) or "error"
    target = str(return_to or "/candidate-flow/start").strip()
    if not target.startswith(("/candidate-flow/start", "/apply/")):
        target = "/candidate-flow/start"
    separator = "&" if "?" in target else "?"
    return RedirectResponse(
        url=f"{target}{separator}hh={safe_marker}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _is_applicant_me_payload(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    if payload.get("is_applicant") is False:
        return False
    role_values = {
        str(payload.get("role") or "").strip().lower(),
        str(payload.get("user_type") or "").strip().lower(),
        str(payload.get("auth_type") or "").strip().lower(),
    }
    if "employer" in role_values:
        return False
    return True


def _resume_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _resume_ref(item: dict[str, Any]) -> tuple[str | None, str | None]:
    resume_id = str(item.get("id") or "").strip() or None
    resume_url = str(item.get("url") or "").strip() or None
    return resume_id, resume_url


def _local_hh_resume_fixture(candidate: User) -> dict[str, Any]:
    candidate_id = int(candidate.id)
    phone = str(candidate.phone or "").strip()
    return {
        "id": f"local-hh-resume-{candidate_id}",
        "alternate_url": f"https://hh.ru/resume/local-hh-resume-{candidate_id}",
        "title": candidate.desired_position or "Специалист контактного центра",
        "first_name": "Local",
        "last_name": "Candidate",
        "middle_name": str(candidate_id),
        "full_name": candidate.fio if not str(candidate.fio or "").startswith("Browser Candidate") else None,
        "area": {"name": candidate.city or "Москва"},
        "phones": [
            {
                "formatted": phone or f"+7 999 000 {candidate_id % 10000:04d}",
            }
        ],
        "skills": ["Коммуникация", "Работа с клиентами", "Дисциплина"],
        "updated_at": _utcnow().isoformat(),
        "created_at": _utcnow().isoformat(),
    }


async def _append_hh_verified_event(
    session: AsyncSession,
    candidate: User,
    *,
    has_resume: bool,
    sync_status: str,
) -> None:
    existing_event_id = await session.scalar(
        select(CandidateJourneyEvent.id)
        .where(
            CandidateJourneyEvent.candidate_id == int(candidate.id),
            CandidateJourneyEvent.event_key == "candidate_web_hh_verified",
        )
        .limit(1)
    )
    if existing_event_id is not None:
        return
    append_journey_event(
        candidate,
        event_key="candidate_web_hh_verified",
        stage="identity",
        actor_type="candidate",
        summary="Кандидат подтвердил профиль через hh.ru",
        payload={"channel": "hh", "has_resume": has_resume, "sync_status": sync_status},
        created_at=_utcnow(),
    )


async def _complete_public_hh_verification_callback(
    *,
    session: AsyncSession,
    settings: Settings,
    code: str,
    intake_id: int,
    return_to: str | None,
) -> RedirectResponse:
    if not _public_intake_enabled(settings) or not _hh_candidate_oauth_available(settings):
        return _candidate_public_flow_redirect(return_to, "disabled")

    client = HHApiClient(
        client_id=settings.hh_candidate_client_id,
        client_secret=settings.hh_candidate_client_secret,
        redirect_uri=settings.hh_candidate_redirect_uri,
        user_agent=settings.hh_candidate_user_agent,
    )
    try:
        intake = await session.get(CandidateWebPublicIntake, int(intake_id))
        if intake is None or intake.provider != PUBLIC_PROVIDER_HH:
            await session.rollback()
            return _candidate_public_flow_redirect(return_to, "error")
        now = _utcnow()
        if _as_utc(intake.expires_at) is None or _as_utc(intake.expires_at) <= now:
            intake.status = INTAKE_STATUS_EXPIRED
            await session.commit()
            return _candidate_public_flow_redirect(return_to, "expired")
        await session.rollback()

        tokens = await client.exchange_authorization_code(code)
        me_payload = await client.get_me(tokens.access_token)
        if not _is_applicant_me_payload(me_payload):
            async with session.begin():
                intake = await session.get(CandidateWebPublicIntake, int(intake_id))
                if intake is not None:
                    intake.status = INTAKE_STATUS_FAILED
                    intake.metadata_json = {
                        **dict(intake.metadata_json or {}),
                        "failure_code": "hh_not_applicant",
                    }
            return _candidate_public_flow_redirect(return_to, "error")

        resumes_payload = await client.list_my_resumes(tokens.access_token)
        resume_items = _resume_items(resumes_payload)
        resume_payload = None
        resume_id = None
        if resume_items:
            resume_id, resume_url = _resume_ref(resume_items[0])
            api_resume_prefix = settings.hh_api_base_url.rstrip("/") + "/resumes/"
            safe_resume_url = resume_url if resume_url and resume_url.startswith(api_resume_prefix) else None
            resume_payload = await client.get_applicant_resume(
                tokens.access_token,
                resume_id=resume_id,
                resume_url=safe_resume_url,
            )
            resume_id = str((resume_payload or {}).get("id") or resume_id or "").strip() or None

        provider_user_id = str(me_payload.get("id") or me_payload.get("account_id") or "").strip()
        if not provider_user_id:
            provider_user_id = f"hh-public-intake-{intake_id}"

        async with session.begin():
            intake = await session.scalar(
                select(CandidateWebPublicIntake)
                .where(CandidateWebPublicIntake.id == int(intake_id))
                .with_for_update()
            )
            if intake is None or intake.provider != PUBLIC_PROVIDER_HH:
                return _candidate_public_flow_redirect(return_to, "error")
            now = _utcnow()
            if _as_utc(intake.expires_at) is None or _as_utc(intake.expires_at) <= now:
                intake.status = INTAKE_STATUS_EXPIRED
                return _candidate_public_flow_redirect(return_to, "expired")
            candidate, result_code = await find_or_create_public_candidate(
                session,
                intake=intake,
                provider_user_id=provider_user_id,
                hh_resume_id=resume_id,
            )
            if candidate is None:
                return _candidate_public_flow_redirect(return_to, "conflict" if "conflict" in result_code else "error")
            result = await upsert_candidate_hh_identity(
                session,
                candidate=candidate,
                me_payload=me_payload,
                resume_payload=resume_payload,
            )
            await _append_hh_verified_event(
                session,
                candidate,
                has_resume=result.resume_imported,
                sync_status=result.sync_status,
            )
            return _candidate_public_flow_redirect(
                return_to,
                "connected" if result.resume_imported else "no_resume",
            )
    except CandidateHHIdentityConflict:
        await session.rollback()
        async with session.begin():
            intake = await session.get(CandidateWebPublicIntake, int(intake_id))
            if intake is not None:
                intake.status = INTAKE_STATUS_CONFLICT
                intake.metadata_json = {
                    **dict(intake.metadata_json or {}),
                    "conflict_code": "hh_identity_conflict",
                }
        return _candidate_public_flow_redirect(return_to, "conflict")
    except (HHApiError, ValueError):
        await session.rollback()
        return _candidate_public_flow_redirect(return_to, "error")


@shell_router.get("/candidate-flow", include_in_schema=False, response_class=FileResponse)
@shell_router.get("/candidate-flow/{path:path}", include_in_schema=False, response_class=FileResponse)
async def candidate_web_shell(path: str = "") -> FileResponse:
    del path
    settings = get_settings()
    if not _feature_enabled(settings):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Browser candidate pilot is disabled.",
        )
    if not SPA_INDEX_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Frontend bundle is not built for browser candidate hosting.",
        )
    return FileResponse(
        SPA_INDEX_FILE,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@shell_router.get("/apply/{slug}", include_in_schema=False)
async def candidate_web_apply_alias(slug: str) -> RedirectResponse:
    settings = get_settings()
    if not _feature_enabled(settings):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Browser candidate pilot is disabled.",
        )
    safe_slug = normalize_campaign_slug(slug)
    if not safe_slug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return RedirectResponse(
        url=f"/candidate-flow/start?campaign={safe_slug}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


def _build_max_public_deep_link(settings: Settings, start_param: str) -> str | None:
    public_bot_name = str(getattr(settings, "max_public_bot_name", "") or "").strip().lstrip("@")
    if public_bot_name:
        return f"https://max.ru/{public_bot_name}?start={start_param}"
    return None


@api_router.get("/public/campaigns/{slug}", response_model=PublicCampaignResponse)
async def get_public_candidate_campaign(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicCampaignResponse:
    campaign = await _load_public_campaign_or_raise(session, slug=slug, settings=settings)
    return await _build_public_campaign_response(session, campaign=campaign, settings=settings)


async def _start_public_provider_verification(
    *,
    slug: str,
    provider: str,
    request: PublicVerificationStartRequest,
    http_request: Request,
    session: AsyncSession,
    settings: Settings,
) -> tuple[CandidateWebCampaign, Any]:
    _enforce_bootstrap_rate_limit(http_request, settings)
    provider_value = normalize_public_provider(provider)
    async with session.begin():
        campaign = await _ensure_public_campaign_available(
            session,
            slug=slug,
            provider=provider_value,
            settings=settings,
        )
        started = await create_public_intake(
            session,
            campaign=campaign,
            provider=provider_value,
            utm=_sanitize_public_utm(request.utm),
            token_ttl_seconds=_public_intake_ttl(settings),
        )
    return campaign, started


@api_router.post(
    "/public/campaigns/{slug}/verification/telegram/start",
    response_model=PublicVerificationStartResponse,
)
async def start_public_candidate_telegram_verification(
    slug: str,
    request: PublicVerificationStartRequest,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicVerificationStartResponse:
    _campaign, started = await _start_public_provider_verification(
        slug=slug,
        provider=PUBLIC_PROVIDER_TELEGRAM,
        request=request,
        http_request=http_request,
        session=session,
        settings=settings,
    )
    telegram_url = _build_telegram_deep_link(started.provider_token)
    return PublicVerificationStartResponse(
        provider=PUBLIC_PROVIDER_TELEGRAM,
        available=bool(telegram_url),
        url=telegram_url,
        poll_token=started.poll_token,
        start_param=started.provider_token,
        expires_at=_as_utc(started.intake.expires_at),
        reason=None if telegram_url else "telegram_bot_username_missing",
        local_confirm_available=_local_verification_available(settings),
    )


@api_router.post(
    "/public/campaigns/{slug}/verification/max/start",
    response_model=PublicVerificationStartResponse,
)
async def start_public_candidate_max_verification(
    slug: str,
    request: PublicVerificationStartRequest,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicVerificationStartResponse:
    _campaign, started = await _start_public_provider_verification(
        slug=slug,
        provider=PUBLIC_PROVIDER_MAX,
        request=request,
        http_request=http_request,
        session=session,
        settings=settings,
    )
    max_url = _build_max_public_deep_link(settings, started.provider_token)
    available = bool(max_url and _max_verification_available(settings))
    return PublicVerificationStartResponse(
        provider=PUBLIC_PROVIDER_MAX,
        available=available,
        url=max_url,
        poll_token=started.poll_token,
        start_param=started.provider_token,
        expires_at=_as_utc(started.intake.expires_at),
        reason=None if available else "max_unavailable_in_local_environment",
        local_confirm_available=_local_verification_available(settings),
    )


@api_router.post(
    "/public/campaigns/{slug}/verification/hh/start",
    response_model=PublicVerificationStartResponse,
)
async def start_public_candidate_hh_verification(
    slug: str,
    request: PublicVerificationStartRequest,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicVerificationStartResponse:
    _campaign, started = await _start_public_provider_verification(
        slug=slug,
        provider=PUBLIC_PROVIDER_HH,
        request=request,
        http_request=http_request,
        session=session,
        settings=settings,
    )
    authorize_url = None
    reason = _hh_unavailable_reason(settings)
    if _hh_candidate_oauth_available(settings):
        try:
            authorize_url, _state = build_hh_public_candidate_authorize_url(
                intake_id=int(started.intake.id),
                return_to=f"/candidate-flow/start?campaign={normalize_campaign_slug(slug)}",
            )
            reason = None
        except ValueError:
            authorize_url = None
            reason = "hh_oauth_disabled"
    return PublicVerificationStartResponse(
        provider=PUBLIC_PROVIDER_HH,
        available=bool(authorize_url),
        url=authorize_url,
        poll_token=started.poll_token,
        start_param=None,
        expires_at=_as_utc(started.intake.expires_at),
        reason=reason,
        local_confirm_available=_local_verification_available(settings),
    )


@api_router.get("/public/verification/status", response_model=PublicVerificationStatusResponse)
async def get_public_candidate_verification_status(
    poll_token: str,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicVerificationStatusResponse:
    if not _public_intake_enabled(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="public_intake_disabled",
            message="Public candidate intake is disabled.",
        )
    _enforce_bootstrap_rate_limit(http_request, settings)
    poll_hash = hash_public_token(str(poll_token or "").strip())
    async with session.begin():
        intake = await session.scalar(
            select(CandidateWebPublicIntake)
            .where(CandidateWebPublicIntake.poll_token_hash == poll_hash)
            .with_for_update()
        )
        if intake is None:
            _raise_candidate_web_http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="poll_not_found",
                message="Verification status was not found.",
            )
        now = _utcnow()
        intake_expires_at = _as_utc(intake.expires_at)
        if intake_expires_at is not None and intake_expires_at <= now:
            if intake.status not in {INTAKE_STATUS_VERIFIED, INTAKE_STATUS_SESSION_ISSUED}:
                intake.status = INTAKE_STATUS_EXPIRED
            return PublicVerificationStatusResponse(
                status=intake.status,
                provider=intake.provider,
                verified=False,
                handoff_available=False,
                reason="expired",
                expires_at=intake_expires_at,
            )
        if intake.status == INTAKE_STATUS_VERIFIED and intake.candidate_id is not None:
            handoff_code = generate_public_token("handoff")
            intake.handoff_code_hash = hash_public_token(handoff_code)
            intake.expires_at = now + timedelta(seconds=_public_handoff_ttl(settings))
            return PublicVerificationStatusResponse(
                status=intake.status,
                provider=intake.provider,
                verified=True,
                handoff_available=True,
                handoff_code=handoff_code,
                expires_at=_as_utc(intake.expires_at),
            )
        return PublicVerificationStatusResponse(
            status=intake.status,
            provider=intake.provider,
            verified=intake.status == INTAKE_STATUS_SESSION_ISSUED,
            handoff_available=False,
            reason=dict(intake.metadata_json or {}).get("conflict_code")
            if intake.status == INTAKE_STATUS_CONFLICT
            else None,
            expires_at=intake_expires_at,
        )


@api_router.post("/public/verification/local-confirm", response_model=PublicVerificationStatusResponse)
async def locally_confirm_public_candidate_verification(
    request: PublicLocalConfirmRequest,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicVerificationStatusResponse:
    if not _local_verification_available(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="local_verification_disabled",
            message="Local verification is disabled.",
        )
    if not _public_intake_enabled(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="public_intake_disabled",
            message="Public candidate intake is disabled.",
        )
    _enforce_bootstrap_rate_limit(http_request, settings)
    provider = normalize_public_provider(request.provider)
    if provider not in {PUBLIC_PROVIDER_TELEGRAM, PUBLIC_PROVIDER_MAX, PUBLIC_PROVIDER_HH}:
        _raise_candidate_web_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="provider_not_allowed",
            message="This verification provider is not available.",
        )
    poll_hash = hash_public_token(str(request.poll_token or "").strip())
    async with session.begin():
        intake = await session.scalar(
            select(CandidateWebPublicIntake)
            .where(CandidateWebPublicIntake.poll_token_hash == poll_hash)
            .with_for_update()
        )
        if intake is None:
            _raise_candidate_web_http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="poll_not_found",
                message="Verification status was not found.",
            )
        if normalize_public_provider(intake.provider) != provider:
            _raise_candidate_web_http_error(
                status_code=status.HTTP_409_CONFLICT,
                code="provider_mismatch",
                message="Verification provider does not match this intake.",
            )
        now = _utcnow()
        intake_expires_at = _as_utc(intake.expires_at)
        if intake_expires_at is not None and intake_expires_at <= now:
            intake.status = INTAKE_STATUS_EXPIRED
            return PublicVerificationStatusResponse(
                status=intake.status,
                provider=intake.provider,
                reason="expired",
                expires_at=intake_expires_at,
            )
        if provider == PUBLIC_PROVIDER_TELEGRAM:
            provider_user_id = str(9_100_000_000 + int(intake.id))
            username = f"public_web_{intake.id}"
            display_name = f"WEB кандидат TG {intake.id}"
            hh_resume_id = None
        elif provider == PUBLIC_PROVIDER_MAX:
            provider_user_id = f"local-public-max-{intake.id}"
            username = f"public_web_{intake.id}"
            display_name = f"WEB кандидат MAX {intake.id}"
            hh_resume_id = None
        else:
            provider_user_id = f"local-hh-applicant-{intake.id}"
            username = None
            display_name = f"WEB кандидат HH {intake.id}"
            hh_resume_id = f"local-public-hh-resume-{intake.id}"
        candidate, code = await find_or_create_public_candidate(
            session,
            intake=intake,
            provider_user_id=provider_user_id,
            username=username,
            display_name=display_name,
            hh_resume_id=hh_resume_id,
        )
        if candidate is not None and provider == PUBLIC_PROVIDER_HH:
            try:
                result = await upsert_candidate_hh_identity(
                    session,
                    candidate=candidate,
                    me_payload={"id": provider_user_id},
                    resume_payload={
                        "id": hh_resume_id,
                        "alternate_url": f"https://hh.ru/resume/{hh_resume_id}",
                        "title": candidate.desired_position or "Специалист контактного центра",
                        "full_name": candidate.fio,
                        "area": {"name": candidate.city or "Москва"},
                        "phones": [{"formatted": candidate.phone or "+7 999 000 0000"}],
                        "updated_at": now.isoformat(),
                    },
                )
                await _append_hh_verified_event(
                    session,
                    candidate,
                    has_resume=result.resume_imported,
                    sync_status=result.sync_status,
                )
            except CandidateHHIdentityConflict:
                intake.status = INTAKE_STATUS_CONFLICT
                intake.metadata_json = {
                    **dict(intake.metadata_json or {}),
                    "conflict_code": "hh_identity_conflict",
                }
                return PublicVerificationStatusResponse(
                    status=intake.status,
                    provider=intake.provider,
                    reason="hh_identity_conflict",
                    expires_at=_as_utc(intake.expires_at),
                )
        if intake.status == INTAKE_STATUS_VERIFIED:
            handoff_code = generate_public_token("handoff")
            intake.handoff_code_hash = hash_public_token(handoff_code)
            intake.expires_at = now + timedelta(seconds=_public_handoff_ttl(settings))
            return PublicVerificationStatusResponse(
                status=intake.status,
                provider=intake.provider,
                verified=True,
                handoff_available=True,
                handoff_code=handoff_code,
                expires_at=_as_utc(intake.expires_at),
            )
        return PublicVerificationStatusResponse(
            status=intake.status,
            provider=intake.provider,
            verified=False,
            reason=code,
            expires_at=_as_utc(intake.expires_at),
        )


@api_router.post("/public/session/exchange", response_model=CandidateWebBootstrapResponse)
async def exchange_public_candidate_session(
    request: PublicSessionExchangeRequest,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateWebBootstrapResponse:
    if not _public_intake_enabled(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="public_intake_disabled",
            message="Public candidate intake is disabled.",
        )
    _enforce_bootstrap_rate_limit(http_request, settings)
    handoff_hash = hash_public_token(str(request.handoff_code or "").strip())
    async with session.begin():
        intake = await session.scalar(
            select(CandidateWebPublicIntake)
            .where(CandidateWebPublicIntake.handoff_code_hash == handoff_hash)
            .with_for_update()
        )
        if intake is None:
            _raise_candidate_web_http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="handoff_not_found",
                message="Verification handoff was not found.",
            )
        if intake.status != INTAKE_STATUS_VERIFIED or intake.candidate_id is None:
            _raise_candidate_web_http_error(
                status_code=status.HTTP_409_CONFLICT,
                code="handoff_not_ready",
                message="Verification handoff is not ready.",
            )
        now = _utcnow()
        intake_expires_at = _as_utc(intake.expires_at)
        if intake_expires_at is None or intake_expires_at <= now:
            intake.status = INTAKE_STATUS_EXPIRED
            _raise_candidate_web_http_error(
                status_code=status.HTTP_410_GONE,
                code="handoff_expired",
                message="Verification handoff has expired.",
            )
        candidate = await _load_candidate_or_raise(session, int(intake.candidate_id))
        raw_resume_token = generate_public_token("web")
        token_id = await _sqlite_next_pk(session, CandidateAccessToken)
        access_token = CandidateAccessToken(
            id=token_id,
            token_hash=_hash_web_token(raw_resume_token),
            candidate_id=int(candidate.id),
            token_kind=CandidateAccessTokenKind.RESUME.value,
            journey_surface=CandidateJourneySurface.STANDALONE_WEB.value,
            auth_method=CandidateAccessAuthMethod.SIGNED_LINK.value,
            launch_channel=CandidateLaunchChannel.WEB.value,
            expires_at=now + timedelta(hours=max(1, int(settings.access_token_ttl_hours))),
            metadata_json={
                "candidate_web_public_intake": {
                    "campaign_id": int(intake.campaign_id),
                    "provider": intake.provider,
                }
            },
            correlation_id=str(uuid.uuid4()),
            issued_by_type="candidate_web_public_intake",
            issued_by_id=str(intake.id),
        )
        session.add(access_token)
        await session.flush()
        tracking_utm = {**dict(intake.utm_json or {}), **_sanitize_public_utm(request.utm)}
        bootstrap_request = CandidateWebBootstrapRequest(
            token=raw_resume_token,
            source=request.source or "web",
            utm=tracking_utm,
        )
        candidate, token, journey_session, access_session, reused = await _bootstrap_browser_candidate(
            session,
            request=bootstrap_request,
        )
        intake.access_session_id = int(access_session.id)
        intake.status = INTAKE_STATUS_SESSION_ISSUED
        intake.consumed_at = now
        intake.handoff_code_hash = None
    return CandidateWebBootstrapResponse(
        candidate=CandidateWebCandidateSummary(
            id=int(candidate.id),
            candidate_id=candidate.candidate_id,
            application_id=token.application_id,
        ),
        session=CandidateWebSessionSummary(
            session_id=access_session.session_id,
            journey_session_id=int(journey_session.id),
            status=access_session.status,
            surface=access_session.journey_surface,
            auth_method=access_session.auth_method,
            launch_channel=access_session.launch_channel,
            expires_at=access_session.expires_at,
            reused=reused,
        ),
    )


@api_router.post("/bootstrap", response_model=CandidateWebBootstrapResponse)
async def bootstrap_candidate_web(
    request: CandidateWebBootstrapRequest,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateWebBootstrapResponse:
    if not _feature_enabled(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="candidate_web_disabled",
            message="Browser candidate pilot is disabled.",
        )
    _enforce_bootstrap_rate_limit(http_request, settings)
    async with session.begin():
        candidate, token, journey_session, access_session, reused = await _bootstrap_browser_candidate(
            session,
            request=request,
        )
    return CandidateWebBootstrapResponse(
        candidate=CandidateWebCandidateSummary(
            id=int(candidate.id),
            candidate_id=candidate.candidate_id,
            application_id=token.application_id,
        ),
        session=CandidateWebSessionSummary(
            session_id=access_session.session_id,
            journey_session_id=int(journey_session.id),
            status=access_session.status,
            surface=access_session.journey_surface,
            auth_method=access_session.auth_method,
            launch_channel=access_session.launch_channel,
            expires_at=access_session.expires_at,
            reused=reused,
        ),
    )


@api_router.get("/me", response_model=CandidateInfo)
async def get_candidate_web_me(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await _shared_get_me(principal, session)


@api_router.get("/journey", response_model=CandidateJourneyResponse)
async def get_candidate_web_journey(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateJourneyResponse:
    return await _shared_get_journey(principal, session)


@api_router.get("/verification", response_model=CandidateVerificationResponse)
async def get_candidate_web_verification(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateVerificationResponse:
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    return await _build_verification_response(candidate, session=session, settings=settings)


@api_router.post("/verification/telegram/start", response_model=CandidateVerificationResponse)
async def start_candidate_web_telegram_verification(
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateVerificationResponse:
    _enforce_mutation_rate_limit(http_request, settings)
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    if is_candidate_social_verified(candidate):
        return await _build_verification_response(candidate, session=session, settings=settings)

    invite = await ensure_candidate_invite_token(
        session,
        str(candidate.candidate_id),
        channel="telegram",
    )
    telegram_start_param = invite.token
    await session.commit()
    return await _build_verification_response(
        candidate,
        session=session,
        settings=settings,
        telegram_start_param=telegram_start_param,
        telegram_url=_build_telegram_deep_link(telegram_start_param),
    )


@api_router.post("/verification/max/start", response_model=CandidateVerificationResponse)
async def start_candidate_web_max_verification(
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateVerificationResponse:
    _enforce_mutation_rate_limit(http_request, settings)
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    if is_candidate_social_verified(candidate):
        return await _build_verification_response(candidate, session=session, settings=settings)

    try:
        preview = await create_max_launch_invite(
            int(candidate.id),
            principal.application_id,
            session=session,
            issued_by_type="candidate_web_self_serve",
            issued_by_id=str(principal.access_session_id),
            settings=settings,
        )
    except MaxLaunchInviteError:
        return await _build_verification_response(candidate, session=session, settings=settings)
    await session.commit()
    return await _build_verification_response(
        candidate,
        session=session,
        settings=settings,
        max_start_param=preview.start_param,
        max_url=preview.max_chat_url or preview.max_launch_url,
        max_expires_at=_as_utc(preview.expires_at),
    )


@api_router.post("/verification/hh/start", response_model=CandidateVerificationResponse)
async def start_candidate_web_hh_verification(
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateVerificationResponse:
    _enforce_mutation_rate_limit(http_request, settings)
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    if await is_candidate_hh_verified(session, int(candidate.id)):
        return await _build_verification_response(candidate, session=session, settings=settings)
    if not _hh_candidate_oauth_available(settings):
        return await _build_verification_response(candidate, session=session, settings=settings)

    try:
        authorize_url, _state = build_hh_candidate_authorize_url(
            candidate_id=int(candidate.id),
            access_session_id=int(principal.access_session_id),
            journey_session_id=int(principal.journey_session_id),
            return_to="/candidate-flow",
        )
    except ValueError:
        return await _build_verification_response(candidate, session=session, settings=settings)
    return await _build_verification_response(
        candidate,
        session=session,
        settings=settings,
        hh_url=authorize_url,
    )


@api_router.get("/verification/hh/callback")
async def complete_candidate_web_hh_verification_callback(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        return _candidate_flow_redirect("error")
    if not _feature_enabled(settings) or not _hh_candidate_oauth_available(settings):
        return _candidate_flow_redirect("disabled")
    if not code or not state:
        return _candidate_flow_redirect("error")

    try:
        parsed_state = parse_hh_candidate_oauth_state(state)
    except ValueError:
        try:
            public_state = parse_hh_public_candidate_oauth_state(state)
        except ValueError:
            return _candidate_flow_redirect("error")
        return await _complete_public_hh_verification_callback(
            session=session,
            settings=settings,
            code=code,
            intake_id=int(public_state.intake_id),
            return_to=public_state.return_to,
        )

    now = _utcnow()
    access_session = await session.get(CandidateAccessSession, int(parsed_state.access_session_id))
    if (
        access_session is None
        or access_session.status != CandidateAccessSessionStatus.ACTIVE.value
        or access_session.candidate_id != int(parsed_state.candidate_id)
        or access_session.journey_session_id != int(parsed_state.journey_session_id)
        or access_session.journey_surface != CandidateJourneySurface.STANDALONE_WEB.value
        or access_session.auth_method != CandidateAccessAuthMethod.SIGNED_LINK.value
        or _as_utc(access_session.expires_at) is None
        or _as_utc(access_session.expires_at) <= now
    ):
        await session.rollback()
        return _candidate_flow_redirect("error")

    candidate = await _load_candidate_or_raise(session, int(parsed_state.candidate_id))
    client = HHApiClient(
        client_id=settings.hh_candidate_client_id,
        client_secret=settings.hh_candidate_client_secret,
        redirect_uri=settings.hh_candidate_redirect_uri,
        user_agent=settings.hh_candidate_user_agent,
    )
    try:
        tokens = await client.exchange_authorization_code(code)
        me_payload = await client.get_me(tokens.access_token)
        if not _is_applicant_me_payload(me_payload):
            await session.rollback()
            return _candidate_flow_redirect("error")

        resumes_payload = await client.list_my_resumes(tokens.access_token)
        resume_items = _resume_items(resumes_payload)
        if not resume_items:
            result = await upsert_candidate_hh_identity(
                session,
                candidate=candidate,
                me_payload=me_payload,
                resume_payload=None,
            )
            await _append_hh_verified_event(
                session,
                candidate,
                has_resume=False,
                sync_status=result.sync_status,
            )
            await session.commit()
            return _candidate_flow_redirect("no_resume")

        resume_id, resume_url = _resume_ref(resume_items[0])
        api_resume_prefix = settings.hh_api_base_url.rstrip("/") + "/resumes/"
        safe_resume_url = resume_url if resume_url and resume_url.startswith(api_resume_prefix) else None
        resume_payload = await client.get_applicant_resume(
            tokens.access_token,
            resume_id=resume_id,
            resume_url=safe_resume_url,
        )
        result = await upsert_candidate_hh_identity(
            session,
            candidate=candidate,
            me_payload=me_payload,
            resume_payload=resume_payload,
        )
        await _append_hh_verified_event(
            session,
            candidate,
            has_resume=result.resume_imported,
            sync_status=result.sync_status,
        )
        await session.commit()
        return _candidate_flow_redirect("connected" if result.resume_imported else "no_resume")
    except CandidateHHIdentityConflict:
        await session.rollback()
        candidate = await _load_candidate_or_raise(session, int(parsed_state.candidate_id))
        candidate.hh_sync_status = "conflicted"
        candidate.hh_sync_error = "hh_identity_conflict"
        append_journey_event(
            candidate,
            event_key="candidate_web_hh_conflict",
            stage="identity",
            actor_type="candidate",
            summary="HH резюме уже связано с другим кандидатом",
            payload={"channel": "hh", "reason": "identity_conflict"},
            created_at=_utcnow(),
        )
        await session.commit()
        return _candidate_flow_redirect("conflict")
    except (HHApiError, ValueError):
        await session.rollback()
        return _candidate_flow_redirect("error")


@api_router.post("/verification/telegram/local-confirm", response_model=CandidateVerificationResponse)
async def locally_confirm_candidate_web_telegram_verification(
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateVerificationResponse:
    if not _local_verification_available(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="local_verification_disabled",
            message="Local verification is disabled.",
        )
    _enforce_mutation_rate_limit(http_request, settings)
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    if not is_candidate_social_verified(candidate):
        invite = await ensure_candidate_invite_token(
            session,
            str(candidate.candidate_id),
            channel="telegram",
        )
        await session.commit()
        bound = await bind_telegram_to_candidate(
            token=invite.token,
            telegram_id=9_000_000_000 + int(candidate.id),
            username=f"local_web_{int(candidate.id)}",
        )
        if bound is not None:
            candidate = bound
        else:
            candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    return await _build_verification_response(candidate, session=session, settings=settings)


@api_router.post("/verification/max/local-confirm", response_model=CandidateVerificationResponse)
async def locally_confirm_candidate_web_max_verification(
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateVerificationResponse:
    if not _local_verification_available(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="local_verification_disabled",
            message="Local verification is disabled.",
        )
    _enforce_mutation_rate_limit(http_request, settings)
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    if not is_candidate_social_verified(candidate):
        try:
            preview = await create_max_launch_invite(
                int(candidate.id),
                principal.application_id,
                session=session,
                issued_by_type="candidate_web_local_verify",
                issued_by_id=str(principal.access_session_id),
                settings=settings,
            )
        except MaxLaunchInviteError:
            preview = None
        await session.commit()
        if preview and preview.start_param:
            bound = await bind_max_to_candidate(
                start_param=preview.start_param,
                max_user_id=f"local-max-web-{int(candidate.id)}",
                username=f"local_web_{int(candidate.id)}",
                display_name=candidate.fio,
            )
            if bound is not None:
                candidate = bound
            else:
                candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    return await _build_verification_response(candidate, session=session, settings=settings)


@api_router.post("/verification/hh/local-confirm", response_model=CandidateVerificationResponse)
async def locally_confirm_candidate_web_hh_verification(
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateVerificationResponse:
    if not _local_verification_available(settings):
        _raise_candidate_web_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="local_verification_disabled",
            message="Local verification is disabled.",
        )
    _enforce_mutation_rate_limit(http_request, settings)
    candidate = await _load_candidate_or_raise(session, int(principal.candidate_id))
    try:
        result = await upsert_candidate_hh_identity(
            session,
            candidate=candidate,
            me_payload={"id": f"local-applicant-{int(candidate.id)}"},
            resume_payload=_local_hh_resume_fixture(candidate),
        )
    except CandidateHHIdentityConflict:
        await session.rollback()
        _raise_candidate_web_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="hh_identity_conflict",
            message="Это HH-резюме уже связано с другим кандидатом. Нужна ручная проверка.",
        )
    await _append_hh_verified_event(
        session,
        candidate,
        has_resume=result.resume_imported,
        sync_status=result.sync_status,
    )
    await session.commit()
    return await _build_verification_response(candidate, session=session, settings=settings)


@api_router.get("/cities", response_model=list[CandidateBookingCityInfo])
async def get_candidate_web_cities(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[CandidateBookingCityInfo]:
    return await _shared_get_cities(principal, session)


@api_router.get("/recruiters", response_model=list[CandidateBookingRecruiterInfo])
async def get_candidate_web_recruiters(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    city_id: int,
) -> list[CandidateBookingRecruiterInfo]:
    return await _shared_get_recruiters(principal, session, city_id)


@api_router.get("/booking-context", response_model=CandidateBookingContextInfo)
async def get_candidate_web_booking_context(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateBookingContextInfo:
    return await _shared_get_booking_context(principal, session)


@api_router.post("/booking-context", response_model=CandidateBookingContextInfo)
async def save_candidate_web_booking_context(
    request: CandidateBookingContextRequest,
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateBookingContextInfo:
    _enforce_mutation_rate_limit(http_request, settings)
    await _ensure_candidate_web_booking_ready(principal, session)
    return await _shared_save_booking_context(request, principal, session)


@api_router.post("/manual-availability", response_model=CandidateManualAvailabilityResponse)
async def save_candidate_web_manual_availability(
    request: CandidateManualAvailabilityRequest,
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateManualAvailabilityResponse:
    _enforce_mutation_rate_limit(http_request, settings)
    await _ensure_candidate_web_booking_ready(principal, session)
    return await _shared_save_manual_availability(request, principal, session)


@api_router.get("/test1", response_model=CandidateTest1Response)
async def get_candidate_web_test1(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateTest1Response:
    await _ensure_candidate_web_test_access(principal, session)
    return await _shared_get_test1(principal, session)


@api_router.post("/test1/answers", response_model=CandidateTest1Response)
async def save_candidate_web_test1_answers(
    request: CandidateTest1AnswersRequest,
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateTest1Response:
    _enforce_mutation_rate_limit(http_request, settings)
    await _ensure_candidate_web_test_access(principal, session)
    return await _shared_save_test1_answers(request, principal, session)


@api_router.post("/test1/complete", response_model=CandidateTest1Response)
async def complete_candidate_web_test1(
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateTest1Response:
    _enforce_mutation_rate_limit(http_request, settings)
    await _ensure_candidate_web_test_access(principal, session)
    return await _shared_complete_test1(principal, session)


@api_router.get("/test2", response_model=CandidateTest2Response)
async def get_candidate_web_test2(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateTest2Response:
    return await _shared_get_test2(principal, session)


@api_router.post("/test2/answers", response_model=CandidateTest2Response)
async def submit_candidate_web_test2_answer(
    request: CandidateTest2AnswerRequest,
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateTest2Response:
    _enforce_mutation_rate_limit(http_request, settings)
    return await _shared_submit_test2_answer(request, principal, session)


@api_router.get("/intro-day", response_model=CandidateIntroDayResponse)
async def get_candidate_web_intro_day(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateIntroDayResponse:
    return await _shared_get_intro_day(principal, session)


@api_router.post("/intro-day/confirm", response_model=CandidateIntroDayResponse)
async def confirm_candidate_web_intro_day(
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateIntroDayResponse:
    _enforce_mutation_rate_limit(http_request, settings)
    return await _shared_confirm_intro_day(principal, session)


@api_router.get("/slots", response_model=list[SlotInfo])
async def get_candidate_web_slots(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    city_id: int | None = None,
    recruiter_id: int | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> list[SlotInfo]:
    return await _shared_get_slots(
        principal,
        session,
        city_id=city_id,
        recruiter_id=recruiter_id,
        from_date=from_date,
        to_date=to_date,
    )


@api_router.post("/bookings", response_model=BookingInfo, status_code=status.HTTP_201_CREATED)
async def create_candidate_web_booking(
    request: CreateBookingRequest,
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BookingInfo:
    _enforce_mutation_rate_limit(http_request, settings)
    await _ensure_candidate_web_booking_ready(principal, session)
    return await _shared_create_booking(request, principal, session)


@api_router.post("/bookings/{booking_id}/confirm", response_model=BookingInfo)
async def confirm_candidate_web_booking(
    booking_id: int,
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BookingInfo:
    _enforce_mutation_rate_limit(http_request, settings)
    await _ensure_candidate_web_booking_ready(principal, session)
    return await _shared_confirm_booking(booking_id, principal, session)


@api_router.post("/bookings/{booking_id}/reschedule", response_model=BookingInfo)
async def reschedule_candidate_web_booking(
    booking_id: int,
    request: RescheduleBookingRequest,
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BookingInfo:
    _enforce_mutation_rate_limit(http_request, settings)
    await _ensure_candidate_web_booking_ready(principal, session)
    return await _shared_reschedule_booking(booking_id, request, principal, session)


@api_router.post("/bookings/{booking_id}/cancel", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def cancel_candidate_web_booking(
    booking_id: int,
    request: CancelBookingRequest,
    http_request: Request,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_web_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    _enforce_mutation_rate_limit(http_request, settings)
    await _ensure_candidate_web_booking_ready(principal, session)
    return await _shared_cancel_booking(booking_id, request, principal, session)


__all__ = [
    "api_router",
    "shell_router",
    "bootstrap_candidate_web",
    "candidate_web_shell",
]
