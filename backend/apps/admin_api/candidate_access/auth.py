"""Shared candidate-access auth dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_api.max_auth import validate_max_init_data
from backend.core.dependencies import get_async_session
from backend.core.settings import get_settings
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessSessionStatus,
    CandidateJourneySession,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    User,
)

CANDIDATE_ACCESS_SESSION_HEADER = "X-Candidate-Access-Session"
MAX_INIT_DATA_HEADER = "X-Max-Init-Data"
MAX_ACCESS_SESSION_IDLE_TTL = timedelta(hours=8)
WEB_ACCESS_SESSION_IDLE_TTL = timedelta(hours=8)


@dataclass(frozen=True)
class CandidateAccessPrincipal:
    candidate_id: int
    application_id: int | None
    access_session_id: int
    surface: str
    provider: str
    provider_user_id: str
    auth_method: str
    session_status: str
    correlation_id: str | None
    journey_session_id: int
    session_version_snapshot: int


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _raise_candidate_access_http_error(
    *,
    status_code: int,
    code: str,
    message: str,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


async def get_max_candidate_access_principal(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    x_candidate_access_session: Annotated[str, Header(..., alias=CANDIDATE_ACCESS_SESSION_HEADER)],
    x_max_init_data: Annotated[str, Header(..., alias=MAX_INIT_DATA_HEADER)],
) -> CandidateAccessPrincipal:
    settings = get_settings()
    if not getattr(settings, "max_adapter_enabled", False):
        _raise_candidate_access_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="max_adapter_disabled",
            message="MAX adapter is disabled.",
        )
    max_bot_token = str(getattr(settings, "max_bot_token", "") or "").strip()
    if not max_bot_token:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="max_bot_token_missing",
            message="MAX bot token is not configured.",
        )

    try:
        validated_init_data = validate_max_init_data(
            x_max_init_data,
            max_bot_token,
            max_age_seconds=int(getattr(settings, "max_init_data_max_age_seconds", 86400)),
        )
    except ValueError as exc:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_init_data",
            message=f"Invalid MAX initData: {exc}",
        )

    session_token = str(x_candidate_access_session or "").strip()
    if not session_token:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="candidate_access_session_not_found",
            message="Candidate access session was not found.",
        )

    now = _utcnow()
    session_lookup = await session.execute(
        select(CandidateAccessSession).where(
            CandidateAccessSession.session_id == session_token
        )
    )
    access_session = session_lookup.scalar_one_or_none()
    if access_session is None:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="candidate_access_session_not_found",
            message="Candidate access session was not found.",
        )

    if access_session.status != CandidateAccessSessionStatus.ACTIVE.value:
        if access_session.status == CandidateAccessSessionStatus.REVOKED.value:
            _raise_candidate_access_http_error(
                status_code=status.HTTP_410_GONE,
                code="candidate_access_session_revoked",
                message="Candidate access session has been revoked.",
            )
        if access_session.status == CandidateAccessSessionStatus.EXPIRED.value:
            _raise_candidate_access_http_error(
                status_code=status.HTTP_410_GONE,
                code="candidate_access_session_expired",
                message="Candidate access session has expired.",
            )
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_access_session_blocked",
            message="Candidate access session is not active.",
        )

    if access_session.revoked_at is not None:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_410_GONE,
            code="candidate_access_session_revoked",
            message="Candidate access session has been revoked.",
        )
    expires_at = _as_utc(access_session.expires_at)
    if expires_at is None or expires_at <= now:
        access_session.status = CandidateAccessSessionStatus.EXPIRED.value
        await session.commit()
        _raise_candidate_access_http_error(
            status_code=status.HTTP_410_GONE,
            code="candidate_access_session_expired",
            message="Candidate access session has expired.",
        )

    if access_session.journey_surface != CandidateJourneySurface.MAX_MINIAPP.value:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_access_surface_mismatch",
            message="Candidate access session does not belong to MAX mini-app surface.",
        )
    if access_session.auth_method != CandidateAccessAuthMethod.MAX_INIT_DATA.value:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_access_auth_method_mismatch",
            message="Candidate access session does not use MAX initData authentication.",
        )
    if access_session.launch_channel != CandidateLaunchChannel.MAX.value:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_access_provider_mismatch",
            message="Candidate access session does not belong to MAX launch channel.",
        )

    provider_user_id = str(validated_init_data.user.user_id)
    if str(access_session.provider_user_id or "").strip() != provider_user_id:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="identity_mismatch",
            message="Candidate access session is bound to a different MAX user.",
        )
    if str(access_session.provider_session_id or "").strip() != str(validated_init_data.query_id).strip():
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="provider_session_mismatch",
            message="Candidate access session is bound to a different MAX launch session.",
        )

    journey_session = await session.get(CandidateJourneySession, access_session.journey_session_id)
    if journey_session is None or journey_session.candidate_id != access_session.candidate_id:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="candidate_access_session_invalid",
            message="Candidate access session references an invalid journey session.",
        )
    if int(access_session.session_version_snapshot or 0) != int(journey_session.session_version or 0):
        _raise_candidate_access_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="stale_session_version",
            message="Candidate access session was invalidated and must be relaunched.",
        )

    candidate = await session.get(User, access_session.candidate_id)
    if candidate is None or not candidate.is_active:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="candidate_unavailable",
            message="Candidate is no longer available.",
        )

    access_session.last_seen_at = now
    access_session.refreshed_at = now
    access_session.expires_at = now + MAX_ACCESS_SESSION_IDLE_TTL
    journey_session.last_access_session_id = access_session.id
    journey_session.last_surface = access_session.journey_surface
    journey_session.last_auth_method = access_session.auth_method
    journey_session.last_activity_at = now
    journey_payload = dict(journey_session.payload_json or {})
    candidate_access_payload = dict(journey_payload.get("candidate_access") or {})
    candidate_access_payload["active_surface"] = access_session.journey_surface
    journey_payload["candidate_access"] = candidate_access_payload
    journey_session.payload_json = journey_payload
    await session.commit()

    return CandidateAccessPrincipal(
        candidate_id=access_session.candidate_id,
        application_id=access_session.application_id,
        access_session_id=access_session.id,
        surface=access_session.journey_surface,
        provider=CandidateLaunchChannel.MAX.value,
        provider_user_id=provider_user_id,
        auth_method=access_session.auth_method,
        session_status=access_session.status,
        correlation_id=access_session.correlation_id,
        journey_session_id=access_session.journey_session_id,
        session_version_snapshot=access_session.session_version_snapshot,
    )


async def get_web_candidate_access_principal(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    x_candidate_access_session: Annotated[str, Header(..., alias=CANDIDATE_ACCESS_SESSION_HEADER)],
) -> CandidateAccessPrincipal:
    settings = get_settings()
    if not getattr(settings, "candidate_web_pilot_enabled", False):
        _raise_candidate_access_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="candidate_web_disabled",
            message="Browser candidate pilot is disabled.",
        )

    session_token = str(x_candidate_access_session or "").strip()
    if not session_token:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="candidate_access_session_not_found",
            message="Candidate access session was not found.",
        )

    now = _utcnow()
    session_lookup = await session.execute(
        select(CandidateAccessSession).where(
            CandidateAccessSession.session_id == session_token
        )
    )
    access_session = session_lookup.scalar_one_or_none()
    if access_session is None:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="candidate_access_session_not_found",
            message="Candidate access session was not found.",
        )

    if access_session.status != CandidateAccessSessionStatus.ACTIVE.value:
        if access_session.status == CandidateAccessSessionStatus.REVOKED.value:
            _raise_candidate_access_http_error(
                status_code=status.HTTP_410_GONE,
                code="candidate_access_session_revoked",
                message="Candidate access session has been revoked.",
            )
        if access_session.status == CandidateAccessSessionStatus.EXPIRED.value:
            _raise_candidate_access_http_error(
                status_code=status.HTTP_410_GONE,
                code="candidate_access_session_expired",
                message="Candidate access session has expired.",
            )
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_access_session_blocked",
            message="Candidate access session is not active.",
        )

    if access_session.revoked_at is not None:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_410_GONE,
            code="candidate_access_session_revoked",
            message="Candidate access session has been revoked.",
        )
    expires_at = _as_utc(access_session.expires_at)
    if expires_at is None or expires_at <= now:
        access_session.status = CandidateAccessSessionStatus.EXPIRED.value
        await session.commit()
        _raise_candidate_access_http_error(
            status_code=status.HTTP_410_GONE,
            code="candidate_access_session_expired",
            message="Candidate access session has expired.",
        )

    if access_session.journey_surface != CandidateJourneySurface.STANDALONE_WEB.value:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_access_surface_mismatch",
            message="Candidate access session does not belong to browser candidate surface.",
        )
    if access_session.auth_method != CandidateAccessAuthMethod.SIGNED_LINK.value:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_access_auth_method_mismatch",
            message="Candidate access session does not use signed-link authentication.",
        )
    if access_session.launch_channel != CandidateLaunchChannel.WEB.value:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="candidate_access_provider_mismatch",
            message="Candidate access session does not belong to browser launch channel.",
        )

    journey_session = await session.get(CandidateJourneySession, access_session.journey_session_id)
    if journey_session is None or journey_session.candidate_id != access_session.candidate_id:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="candidate_access_session_invalid",
            message="Candidate access session references an invalid journey session.",
        )
    if int(access_session.session_version_snapshot or 0) != int(journey_session.session_version or 0):
        _raise_candidate_access_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="stale_session_version",
            message="Candidate access session was invalidated and must be relaunched.",
        )

    candidate = await session.get(User, access_session.candidate_id)
    if candidate is None or not candidate.is_active:
        _raise_candidate_access_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="candidate_unavailable",
            message="Candidate is no longer available.",
        )

    access_session.last_seen_at = now
    access_session.refreshed_at = now
    access_session.expires_at = now + WEB_ACCESS_SESSION_IDLE_TTL
    journey_session.last_access_session_id = access_session.id
    journey_session.last_surface = access_session.journey_surface
    journey_session.last_auth_method = access_session.auth_method
    journey_session.last_activity_at = now
    journey_payload = dict(journey_session.payload_json or {})
    candidate_access_payload = dict(journey_payload.get("candidate_access") or {})
    candidate_access_payload["active_surface"] = access_session.journey_surface
    candidate_access_payload["active_channel"] = CandidateLaunchChannel.WEB.value
    journey_payload["candidate_access"] = candidate_access_payload
    journey_session.payload_json = journey_payload
    await session.commit()

    return CandidateAccessPrincipal(
        candidate_id=access_session.candidate_id,
        application_id=access_session.application_id,
        access_session_id=access_session.id,
        surface=access_session.journey_surface,
        provider=CandidateLaunchChannel.WEB.value,
        provider_user_id=str(access_session.provider_user_id or access_session.candidate_id),
        auth_method=access_session.auth_method,
        session_status=access_session.status,
        correlation_id=access_session.correlation_id,
        journey_session_id=access_session.journey_session_id,
        session_version_snapshot=access_session.session_version_snapshot,
    )


def is_candidate_social_verified(candidate: User | None) -> bool:
    """Return true when the candidate has a verified social-channel identity."""
    if candidate is None:
        return False
    return bool(
        getattr(candidate, "telegram_id", None)
        or getattr(candidate, "telegram_user_id", None)
        or str(getattr(candidate, "max_user_id", "") or "").strip()
    )


__all__ = [
    "CANDIDATE_ACCESS_SESSION_HEADER",
    "MAX_INIT_DATA_HEADER",
    "CandidateAccessPrincipal",
    "get_max_candidate_access_principal",
    "get_web_candidate_access_principal",
    "is_candidate_social_verified",
]
