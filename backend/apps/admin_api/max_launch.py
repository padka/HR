"""Bounded MAX mini-app launch boundary."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_api.max_auth import MaxInitData, validate_max_init_data
from backend.core.dependencies import get_async_session
from backend.core.settings import Settings, get_settings
from backend.domain.applications import ApplicationEventType
from backend.domain.applications.idempotency import (
    fingerprint_payload,
    scoped_idempotency_key,
)
from backend.domain.candidates.journey import LIFECYCLE_DRAFT
from backend.domain.candidates.max_launch_invites import create_max_launch_invite
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessSessionStatus,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    User,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.workflow import (
    WorkflowStatus,
    workflow_status_from_raw_value,
)
from backend.domain.models import ApplicationEvent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["max"])

MAX_START_PARAM_RE = re.compile(r"^[A-Za-z0-9_-]{1,512}$")
MAX_ACCESS_SESSION_IDLE_TTL = timedelta(hours=8)
_ACTIVE_REPEAT_BLOCKING_CANDIDATE_STATUSES = {
    CandidateStatus.SLOT_PENDING,
    CandidateStatus.INTERVIEW_SCHEDULED,
    CandidateStatus.INTERVIEW_CONFIRMED,
    CandidateStatus.TEST2_SENT,
    CandidateStatus.TEST2_COMPLETED,
    CandidateStatus.INTRO_DAY_SCHEDULED,
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
}
_ACTIVE_REPEAT_BLOCKING_WORKFLOW_STATUSES = {
    WorkflowStatus.INTERVIEW_SCHEDULED,
    WorkflowStatus.INTERVIEW_CONFIRMED,
    WorkflowStatus.TEST_SENT,
    WorkflowStatus.ONBOARDING_DAY_SCHEDULED,
    WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
}


class MaxLaunchRequest(BaseModel):
    init_data: str = Field(..., min_length=1)
    start_param: str | None = Field(default=None, max_length=512)


class MaxLaunchCapabilities(BaseModel):
    request_contact: bool
    open_link: bool
    open_max_link: bool


class MaxLaunchCandidateSummary(BaseModel):
    id: int
    candidate_id: str
    application_id: int | None = None


class MaxLaunchSessionSummary(BaseModel):
    id: int
    session_id: str
    journey_session_id: int
    status: str
    surface: str
    auth_method: str
    launch_channel: str
    reused: bool


class MaxLaunchBindingInfo(BaseModel):
    status: str
    code: str | None = None
    message: str
    requires_contact: bool = False
    start_param: str | None = None
    chat_url: str | None = None


class MaxLaunchResponse(BaseModel):
    ok: bool = True
    surface: str
    auth_method: str
    candidate: MaxLaunchCandidateSummary | None = None
    session: MaxLaunchSessionSummary | None = None
    capabilities: MaxLaunchCapabilities
    binding: MaxLaunchBindingInfo


class MaxLaunchError(ValueError):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class _BootstrapResult:
    candidate: User
    token: CandidateAccessToken
    journey_session: CandidateJourneySession
    access_session: CandidateAccessSession
    start_param: str | None
    reused: bool


@dataclass(frozen=True)
class _PrebindResult:
    status: str
    code: str
    message: str
    requires_contact: bool


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _sqlite_next_pk(
    session: AsyncSession,
    model_cls: type[CandidateAccessSession] | type[CandidateAccessToken] | type[ApplicationEvent],
) -> int | None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return None
    next_id = await session.scalar(select(func.coalesce(func.max(model_cls.id), 0) + 1))
    return int(next_id or 1)


def _normalize_start_param(start_param: str | None) -> str | None:
    normalized = str(start_param or "").strip() or None
    if normalized is None:
        return None
    if not MAX_START_PARAM_RE.fullmatch(normalized):
        raise MaxLaunchError(
            "MAX start_param must be a short opaque reference using only A-Z, a-z, 0-9, '_' or '-'.",
            code="invalid_start_param",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return normalized


def _resolve_start_param(*, init_data: MaxInitData, request_value: str | None) -> str | None:
    request_start_param = _normalize_start_param(request_value)
    init_start_param = _normalize_start_param(init_data.start_param)
    if request_start_param and init_start_param and request_start_param != init_start_param:
        raise MaxLaunchError(
            "Body start_param must match the signed MAX initData start_param.",
            code="start_param_mismatch",
            status_code=status.HTTP_409_CONFLICT,
        )
    return request_start_param or init_start_param


async def _load_launch_token(
    session: AsyncSession,
    *,
    start_param: str,
    now: datetime,
) -> CandidateAccessToken:
    result = await session.execute(
        select(CandidateAccessToken)
        .where(CandidateAccessToken.start_param == start_param)
        .order_by(CandidateAccessToken.created_at.desc(), CandidateAccessToken.id.desc())
        .limit(1)
        .with_for_update()
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise MaxLaunchError(
            "MAX launch context was not found for the provided start_param.",
            code="launch_context_missing",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if token.token_kind not in {
        CandidateAccessTokenKind.INVITE.value,
        CandidateAccessTokenKind.LAUNCH.value,
        CandidateAccessTokenKind.RESUME.value,
    }:
        raise MaxLaunchError(
            "MAX launch context is not valid for mini-app bootstrap.",
            code="launch_context_invalid",
            status_code=status.HTTP_409_CONFLICT,
        )
    if token.revoked_at is not None:
        raise MaxLaunchError(
            "MAX launch context has been revoked.",
            code="launch_context_revoked",
            status_code=status.HTTP_410_GONE,
        )
    token_expires_at = _as_utc(token.expires_at)
    if token_expires_at is not None and token_expires_at <= now:
        raise MaxLaunchError(
            "MAX launch context has expired.",
            code="launch_context_expired",
            status_code=status.HTTP_410_GONE,
    )
    return token


async def _load_bound_launch_token(
    session: AsyncSession,
    *,
    provider_user_id: str,
    now: datetime,
) -> CandidateAccessToken | None:
    candidate_rows = (
        await session.execute(
            select(User)
            .where(
                User.max_user_id == provider_user_id,
                User.is_active.is_(True),
            )
            .order_by(User.id.desc())
            .limit(2)
        )
    ).scalars().all()
    if not candidate_rows:
        return None
    if len(candidate_rows) > 1:
        raise MaxLaunchError(
            "MAX launch is ambiguous for the current user.",
            code="launch_context_ambiguous",
            status_code=status.HTTP_409_CONFLICT,
        )

    candidate_id = int(candidate_rows[0].id)
    token_rows = (
        await session.execute(
            select(CandidateAccessToken)
            .where(
                CandidateAccessToken.candidate_id == candidate_id,
                CandidateAccessToken.token_kind.in_(
                    [
                        CandidateAccessTokenKind.INVITE.value,
                        CandidateAccessTokenKind.LAUNCH.value,
                        CandidateAccessTokenKind.RESUME.value,
                    ]
                ),
                CandidateAccessToken.journey_surface == CandidateJourneySurface.MAX_MINIAPP.value,
                CandidateAccessToken.auth_method == CandidateAccessAuthMethod.MAX_INIT_DATA.value,
                CandidateAccessToken.launch_channel == CandidateLaunchChannel.MAX.value,
                CandidateAccessToken.revoked_at.is_(None),
                CandidateAccessToken.expires_at > now,
                CandidateAccessToken.start_param.is_not(None),
            )
            .order_by(CandidateAccessToken.created_at.desc(), CandidateAccessToken.id.desc())
            .limit(2)
            .with_for_update()
        )
    ).scalars().all()
    if not token_rows:
        return None
    if len(token_rows) > 1:
        raise MaxLaunchError(
            "MAX launch is ambiguous for the current user.",
            code="launch_context_ambiguous",
            status_code=status.HTTP_409_CONFLICT,
        )
    return token_rows[0]


async def _load_candidate_or_raise(session: AsyncSession, candidate_id: int) -> User:
    candidate = await session.get(User, candidate_id)
    if candidate is None or not candidate.is_active:
        raise MaxLaunchError(
            "Candidate launch context is no longer active.",
            code="candidate_unavailable",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return candidate


def _enforce_identity_binding(
    *,
    candidate: User,
    token: CandidateAccessToken,
    provider_user_id: str,
) -> None:
    if token.provider_user_id and str(token.provider_user_id).strip() != provider_user_id:
        raise MaxLaunchError(
            "MAX launch context is bound to a different MAX user.",
            code="identity_mismatch",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    candidate_max_user_id = str(getattr(candidate, "max_user_id", "") or "").strip()
    if candidate_max_user_id and candidate_max_user_id != provider_user_id:
        raise MaxLaunchError(
            "Candidate identity is already bound to a different MAX user.",
            code="identity_mismatch",
            status_code=status.HTTP_403_FORBIDDEN,
        )


async def _ensure_journey_session(
    session: AsyncSession,
    *,
    token: CandidateAccessToken,
    now: datetime,
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
            entry_channel=CandidateLaunchChannel.MAX.value,
            last_surface=CandidateJourneySurface.MAX_MINIAPP.value,
            last_auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            last_activity_at=now,
        )
        session.add(journey_session)
        await session.flush()
        token.journey_session_id = journey_session.id

    return journey_session


async def _load_existing_access_session(
    session: AsyncSession,
    *,
    provider_user_id: str,
    query_id: str,
    now: datetime,
) -> CandidateAccessSession | None:
    result = await session.execute(
        select(CandidateAccessSession)
        .where(
            CandidateAccessSession.provider_user_id == provider_user_id,
            CandidateAccessSession.provider_session_id == query_id,
            CandidateAccessSession.journey_surface == CandidateJourneySurface.MAX_MINIAPP.value,
            CandidateAccessSession.status == CandidateAccessSessionStatus.ACTIVE.value,
            CandidateAccessSession.expires_at > now,
        )
        .order_by(CandidateAccessSession.issued_at.desc(), CandidateAccessSession.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _capabilities(settings: Settings) -> MaxLaunchCapabilities:
    max_public_bot_name = str(getattr(settings, "max_public_bot_name", "") or "").strip()
    max_miniapp_url = str(getattr(settings, "max_miniapp_url", "") or "").strip()
    crm_public_url = str(getattr(settings, "crm_public_url", "") or "").strip()
    return MaxLaunchCapabilities(
        request_contact=True,
        open_link=bool(max_miniapp_url or crm_public_url),
        open_max_link=bool(max_public_bot_name or max_miniapp_url),
    )


def _chat_url(
    settings: Settings,
    *,
    start_param: str | None = None,
) -> str | None:
    public_bot_name = str(getattr(settings, "max_public_bot_name", "") or "").strip().lstrip("@")
    if not public_bot_name:
        return None
    if start_param:
        return f"https://max.ru/{public_bot_name}?start={start_param}"
    return f"https://max.ru/{public_bot_name}"


def _candidate_blocks_test1_restart(candidate: User) -> bool:
    candidate_status = getattr(candidate, "candidate_status", None)
    if candidate_status in _ACTIVE_REPEAT_BLOCKING_CANDIDATE_STATUSES:
        return True

    workflow_status = workflow_status_from_raw_value(getattr(candidate, "workflow_status", None))
    if workflow_status in _ACTIVE_REPEAT_BLOCKING_WORKFLOW_STATUSES:
        return True

    return False


def _should_restart_bound_candidate_test1(candidate: User) -> bool:
    lifecycle_state = str(getattr(candidate, "lifecycle_state", "") or "").strip().lower()
    has_candidate_status = getattr(candidate, "candidate_status", None) is not None
    has_workflow_status = workflow_status_from_raw_value(getattr(candidate, "workflow_status", None)) is not None
    return (
        lifecycle_state != LIFECYCLE_DRAFT
        and (has_candidate_status or has_workflow_status)
        and not _candidate_blocks_test1_restart(candidate)
    )


def _normalized_max_candidate_name(
    *,
    display_name: str | None,
    provider_user_id: str,
) -> str:
    full_name = str(display_name or "").strip()
    if full_name:
        return full_name
    return f"MAX {provider_user_id}"


def _should_refresh_candidate_name(
    *,
    existing_name: str | None,
    candidate_name: str | None,
    provider_user_id: str,
) -> bool:
    normalized_existing = str(existing_name or "").strip()
    normalized_candidate = str(candidate_name or "").strip()
    if not normalized_candidate:
        return False
    candidate_parts = [part for part in normalized_candidate.split() if part]
    if len(candidate_parts) < 2:
        return False
    if not normalized_existing:
        return True
    if normalized_existing.casefold() in {
        f"MAX {provider_user_id}".casefold(),
        "MAX Candidate".casefold(),
        "MAX User".casefold(),
    }:
        return True
    existing_parts = [part for part in normalized_existing.split() if part]
    if len(candidate_parts) > len(existing_parts) and normalized_candidate.casefold().startswith(normalized_existing.casefold()):
        return True
    return False


async def _load_bound_candidate(
    session: AsyncSession,
    *,
    provider_user_id: str,
) -> User | None:
    candidate_rows = (
        await session.execute(
            select(User)
            .where(
                User.max_user_id == provider_user_id,
                User.is_active.is_(True),
            )
            .order_by(User.id.desc())
            .limit(2)
            .with_for_update()
        )
    ).scalars().all()
    if not candidate_rows:
        return None
    if len(candidate_rows) > 1:
        raise MaxLaunchError(
            "MAX launch is ambiguous for the current user.",
            code="launch_context_ambiguous",
            status_code=status.HTTP_409_CONFLICT,
        )
    return candidate_rows[0]


async def _acquire_max_identity_bootstrap_lock(
    session: AsyncSession,
    *,
    provider_user_id: str,
) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    digest = hashlib.sha256(
        f"max-global-bootstrap:{provider_user_id}".encode()
    ).digest()
    lock_key = int.from_bytes(digest[:8], "big", signed=True)
    await session.execute(select(func.pg_advisory_xact_lock(lock_key)))


async def _load_latest_journey_session(
    session: AsyncSession,
    *,
    candidate_id: int,
) -> CandidateJourneySession | None:
    return await session.scalar(
        select(CandidateJourneySession)
        .where(CandidateJourneySession.candidate_id == int(candidate_id))
        .order_by(
            CandidateJourneySession.last_activity_at.desc(),
            CandidateJourneySession.id.desc(),
        )
        .limit(1)
        .with_for_update()
    )


async def _create_max_intake_draft_candidate(
    session: AsyncSession,
    *,
    candidate_name: str | None,
    username: str | None,
    provider_user_id: str,
    now: datetime,
) -> User:
    normalized_username = str(username or "").strip() or None
    candidate = User(
        fio=_normalized_max_candidate_name(
            display_name=candidate_name,
            provider_user_id=provider_user_id,
        ),
        username=normalized_username,
        telegram_username=normalized_username,
        messenger_platform="max",
        max_user_id=provider_user_id,
        source="max",
        lifecycle_state=LIFECYCLE_DRAFT,
        candidate_status=None,
        last_activity=now,
    )
    session.add(candidate)
    await session.flush()
    return candidate


async def _ensure_max_intake_journey_session(
    session: AsyncSession,
    *,
    candidate: User,
    application_id: int | None,
    now: datetime,
    force_new: bool = False,
) -> CandidateJourneySession:
    journey_session = None if force_new else await _load_latest_journey_session(session, candidate_id=int(candidate.id))
    if journey_session is not None:
        if journey_session.application_id is None and application_id is not None:
            journey_session.application_id = application_id
        if str(journey_session.current_step_key or "").strip().lower() in {"", "profile"}:
            journey_session.current_step_key = "test1"
        journey_session.last_surface = CandidateJourneySurface.MAX_MINIAPP.value
        journey_session.last_auth_method = CandidateAccessAuthMethod.MAX_INIT_DATA.value
        journey_session.last_activity_at = now
        if journey_session.status != CandidateJourneySessionStatus.ACTIVE.value:
            journey_session.status = CandidateJourneySessionStatus.ACTIVE.value
        return journey_session

    journey_session = CandidateJourneySession(
        candidate_id=int(candidate.id),
        application_id=application_id,
        journey_key="candidate_portal",
        journey_version="v1",
        entry_channel=CandidateLaunchChannel.MAX.value,
        current_step_key="test1",
        last_surface=CandidateJourneySurface.MAX_MINIAPP.value,
        last_auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
        status=CandidateJourneySessionStatus.ACTIVE.value,
        last_activity_at=now,
    )
    session.add(journey_session)
    await session.flush()
    return journey_session


async def _issue_max_intake_launch_token(
    session: AsyncSession,
    *,
    candidate: User,
    provider_user_id: str,
    now: datetime,
    force_new_journey: bool = False,
    rotate_active: bool = False,
) -> CandidateAccessToken:
    journey_session = await _ensure_max_intake_journey_session(
        session,
        candidate=candidate,
        application_id=None,
        now=now,
        force_new=force_new_journey,
    )
    preview = await create_max_launch_invite(
        int(candidate.id),
        application_id=journey_session.application_id,
        session=session,
        issued_by_type="candidate_self_serve",
        issued_by_id=provider_user_id,
        rotate_active=rotate_active,
    )
    token = await session.scalar(
        select(CandidateAccessToken)
        .where(CandidateAccessToken.id == int(preview.lifecycle.active_token_id))
        .limit(1)
        .with_for_update()
    )
    if token is None:
        raise MaxLaunchError(
            "MAX launch context could not be created for the current user.",
            code="launch_context_missing",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    token.journey_session_id = journey_session.id
    token.provider_user_id = provider_user_id
    token.last_seen_at = now
    if token.session_version_snapshot is None:
        token.session_version_snapshot = max(1, int(journey_session.session_version or 1))
    return token


async def _resolve_or_create_global_intake_token(
    session: AsyncSession,
    *,
    candidate_name: str | None,
    username: str | None,
    provider_user_id: str,
    now: datetime,
    restart_test1: bool = False,
) -> CandidateAccessToken:
    candidate = await _load_bound_candidate(
        session,
        provider_user_id=provider_user_id,
    )
    if candidate is None:
        candidate = await _create_max_intake_draft_candidate(
            session,
            candidate_name=candidate_name,
            username=username,
            provider_user_id=provider_user_id,
            now=now,
        )
    else:
        candidate.messenger_platform = "max"
        candidate.max_user_id = provider_user_id
        candidate.source = candidate.source or "max"
        if _should_refresh_candidate_name(
            existing_name=getattr(candidate, "fio", None),
            candidate_name=candidate_name,
            provider_user_id=provider_user_id,
        ):
            candidate.fio = str(candidate_name or "").strip()
        candidate.last_activity = now
    return await _issue_max_intake_launch_token(
        session,
        candidate=candidate,
        provider_user_id=provider_user_id,
        now=now,
        force_new_journey=restart_test1,
        rotate_active=restart_test1,
    )


async def _has_self_serve_max_history(
    session: AsyncSession,
    *,
    candidate_id: int,
) -> bool:
    existing = await session.scalar(
        select(CandidateAccessToken.id)
        .where(
            CandidateAccessToken.candidate_id == int(candidate_id),
            CandidateAccessToken.launch_channel == CandidateLaunchChannel.MAX.value,
            CandidateAccessToken.issued_by_type == "candidate_self_serve",
        )
        .limit(1)
    )
    return existing is not None


async def bootstrap_max_global_intake_token(
    session: AsyncSession,
    *,
    settings: Settings,
    provider_user_id: str,
    candidate_name: str | None,
    username: str | None,
    now: datetime | None = None,
) -> CandidateAccessToken:
    current_time = now or _utcnow()
    await _acquire_max_identity_bootstrap_lock(
        session,
        provider_user_id=provider_user_id,
    )
    candidate = await _load_bound_candidate(
        session,
        provider_user_id=provider_user_id,
    )
    restart_test1 = candidate is not None and _should_restart_bound_candidate_test1(candidate)
    if not restart_test1:
        token = await _load_bound_launch_token(
            session,
            provider_user_id=provider_user_id,
            now=current_time,
        )
        if token is not None:
            if candidate is not None:
                candidate.messenger_platform = "max"
                candidate.max_user_id = provider_user_id
                candidate.source = candidate.source or "max"
                if _should_refresh_candidate_name(
                    existing_name=getattr(candidate, "fio", None),
                    candidate_name=candidate_name,
                    provider_user_id=provider_user_id,
                ):
                    candidate.fio = str(candidate_name or "").strip()
                candidate.last_activity = current_time
            return token
    if candidate is not None:
        is_draft = str(getattr(candidate, "lifecycle_state", "") or "").strip().lower() == LIFECYCLE_DRAFT
        if not is_draft and not await _has_self_serve_max_history(
            session,
            candidate_id=int(candidate.id),
        ):
            raise MaxLaunchError(
                "MAX launch context is not available for the current user.",
                code="launch_context_missing",
                status_code=status.HTTP_404_NOT_FOUND,
            )
    if not bool(getattr(settings, "max_invite_rollout_enabled", False)):
        raise MaxLaunchError(
            "MAX launch rollout is disabled for unbound candidate entry.",
            code="max_rollout_disabled",
            status_code=status.HTTP_409_CONFLICT,
        )
    return await _resolve_or_create_global_intake_token(
        session,
        candidate_name=candidate_name,
        username=username,
        provider_user_id=provider_user_id,
        now=current_time,
        restart_test1=restart_test1,
    )


async def _append_launch_observed_event(
    session: AsyncSession,
    *,
    result: _BootstrapResult,
    init_data: MaxInitData,
    observed_at: datetime,
) -> None:
    producer_family = "max-launch"
    raw_idempotency_key = f"launch-observed:{result.token.token_id}:{init_data.query_id}"
    scoped_key = scoped_idempotency_key(producer_family, raw_idempotency_key)
    existing = await session.scalar(
        select(ApplicationEvent).where(ApplicationEvent.idempotency_key == scoped_key).limit(1)
    )
    if existing is not None:
        return

    metadata = {
        "launch_token_id": result.token.id,
        "launch_token_kind": result.token.token_kind,
        "journey_surface": result.access_session.journey_surface,
        "auth_method": result.access_session.auth_method,
        "provider_session_bound": bool(
            str(result.access_session.provider_session_id or "").strip()
        ),
        "reused_session": result.reused,
    }
    payload_fingerprint = fingerprint_payload(
        {
            "event_type": ApplicationEventType.CANDIDATE_ACCESS_LINK_LAUNCHED.value,
            "candidate_id": result.candidate.id,
            "application_id": result.access_session.application_id,
            "source_system": "max",
            "source_ref": init_data.query_id,
            "actor_type": "candidate",
            "actor_id": result.access_session.provider_user_id,
            "channel": CandidateLaunchChannel.MAX.value,
            "metadata_json": metadata,
        }
    )
    event = ApplicationEvent(
        id=await _sqlite_next_pk(session, ApplicationEvent),
        event_id=str(uuid.uuid4()),
        occurred_at=observed_at,
        actor_type="candidate",
        actor_id=result.access_session.provider_user_id,
        candidate_id=result.candidate.id,
        application_id=result.access_session.application_id,
        requisition_id=None,
        event_type=ApplicationEventType.CANDIDATE_ACCESS_LINK_LAUNCHED.value,
        source="max",
        channel=CandidateLaunchChannel.MAX.value,
        idempotency_key=scoped_key,
        correlation_id=result.access_session.correlation_id or str(uuid.uuid4()),
        metadata_json={
            **metadata,
            "_rs_producer_family": producer_family,
            "_rs_source_ref": init_data.query_id,
            "_rs_payload_fingerprint": payload_fingerprint,
            "_rs_raw_idempotency_key": raw_idempotency_key,
        },
    )
    session.add(event)
    await session.flush()


async def bootstrap_max_launch(
    session: AsyncSession,
    *,
    settings: Settings,
    init_data: MaxInitData,
    request_start_param: str | None,
) -> _BootstrapResult | _PrebindResult:
    now = _utcnow()
    effective_start_param = _resolve_start_param(init_data=init_data, request_value=request_start_param)
    provider_user_id = str(init_data.user.user_id)
    if effective_start_param:
        token = await _load_launch_token(session, start_param=effective_start_param, now=now)
    else:
        try:
            bound_candidate = await _load_bound_candidate(
                session,
                provider_user_id=provider_user_id,
            )
            restart_test1 = bound_candidate is not None and _should_restart_bound_candidate_test1(bound_candidate)
            token = None if restart_test1 else await _load_bound_launch_token(
                session,
                provider_user_id=provider_user_id,
                now=now,
            )
        except MaxLaunchError as exc:
            if exc.code == "launch_context_ambiguous":
                return _PrebindResult(
                    status="manual_review_required",
                    code=exc.code,
                    message=(
                        "Не удалось безопасно восстановить анкету автоматически. "
                        "Продолжим после ручной проверки."
                    ),
                    requires_contact=False,
                )
            raise
        if token is None:
            token = await bootstrap_max_global_intake_token(
                session,
                settings=settings,
                candidate_name=init_data.user.full_name,
                username=init_data.user.username,
                provider_user_id=provider_user_id,
                now=now,
            )
        effective_start_param = str(token.start_param or "").strip() or None
        if effective_start_param is None:
            raise MaxLaunchError(
                "MAX launch context could not be prepared for the current user.",
                code="launch_context_missing",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    candidate = await _load_candidate_or_raise(session, token.candidate_id)
    _enforce_identity_binding(
        candidate=candidate,
        token=token,
        provider_user_id=provider_user_id,
    )
    if _should_refresh_candidate_name(
        existing_name=getattr(candidate, "fio", None),
        candidate_name=init_data.user.full_name,
        provider_user_id=provider_user_id,
    ):
        candidate.fio = str(init_data.user.full_name or "").strip()
    candidate.messenger_platform = "max"
    candidate.max_user_id = provider_user_id
    candidate.source = candidate.source or "max"
    candidate.last_activity = now

    journey_session = await _ensure_journey_session(session, token=token, now=now)
    access_session = await _load_existing_access_session(
        session,
        provider_user_id=provider_user_id,
        query_id=init_data.query_id,
        now=now,
    )

    reused = access_session is not None
    expires_at = now + MAX_ACCESS_SESSION_IDLE_TTL
    if access_session is None:
        session_id = await _sqlite_next_pk(session, CandidateAccessSession)
        access_session = CandidateAccessSession(
            id=session_id,
            candidate_id=candidate.id,
            application_id=token.application_id,
            journey_session_id=journey_session.id,
            origin_token_id=token.id,
            journey_surface=CandidateJourneySurface.MAX_MINIAPP.value,
            auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            launch_channel=CandidateLaunchChannel.MAX.value,
            provider_session_id=init_data.query_id,
            provider_user_id=provider_user_id,
            session_version_snapshot=max(1, int(journey_session.session_version or 1)),
            phone_verification_state=token.phone_verification_state,
            phone_delivery_channel=token.phone_delivery_channel,
            status=CandidateAccessSessionStatus.ACTIVE.value,
            issued_at=now,
            last_seen_at=now,
            refreshed_at=now,
            expires_at=expires_at,
            correlation_id=token.correlation_id or str(uuid.uuid4()),
            metadata_json={
                "launch_auth_date": init_data.auth_date,
            },
        )
        session.add(access_session)
        await session.flush()
    else:
        if access_session.candidate_id != candidate.id:
            raise MaxLaunchError(
                "MAX launch session is bound to a different candidate.",
                code="identity_mismatch",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        access_session.last_seen_at = now
        access_session.refreshed_at = now
        access_session.expires_at = expires_at
        access_session.journey_session_id = journey_session.id
        access_session.application_id = token.application_id
        access_session.session_version_snapshot = max(1, int(journey_session.session_version or 1))
        if access_session.origin_token_id is None:
            access_session.origin_token_id = token.id
        access_session.metadata_json = {
            **(access_session.metadata_json or {}),
            "launch_auth_date": init_data.auth_date,
        }

    token.last_seen_at = now
    token.provider_user_id = token.provider_user_id or provider_user_id
    if token.session_version_snapshot is None:
        token.session_version_snapshot = max(1, int(journey_session.session_version or 1))

    journey_session.last_access_session_id = access_session.id
    journey_session.last_surface = CandidateJourneySurface.MAX_MINIAPP.value
    journey_session.last_auth_method = CandidateAccessAuthMethod.MAX_INIT_DATA.value
    journey_session.last_activity_at = now
    if journey_session.application_id is None and token.application_id is not None:
        journey_session.application_id = token.application_id
    if journey_session.status != CandidateJourneySessionStatus.ACTIVE.value:
        journey_session.status = CandidateJourneySessionStatus.ACTIVE.value

    return _BootstrapResult(
        candidate=candidate,
        token=token,
        journey_session=journey_session,
        access_session=access_session,
        start_param=effective_start_param,
        reused=reused,
    )


def _raise_max_http_error(
    *,
    status_code: int,
    code: str,
    message: str,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


@router.post("/launch", response_model=MaxLaunchResponse)
async def launch_max_miniapp(
    request: MaxLaunchRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> MaxLaunchResponse:
    settings = get_settings()
    if not getattr(settings, "max_adapter_enabled", False):
        _raise_max_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="max_adapter_disabled",
            message="MAX adapter is disabled.",
        )
    max_bot_token = str(getattr(settings, "max_bot_token", "") or "").strip()
    if not max_bot_token:
        _raise_max_http_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="max_bot_token_missing",
            message="MAX bot token is not configured.",
        )

    try:
        validated_init_data = validate_max_init_data(
            request.init_data,
            max_bot_token,
            max_age_seconds=int(getattr(settings, "max_init_data_max_age_seconds", 86400)),
        )
        async with session.begin():
            result = await bootstrap_max_launch(
                session,
                settings=settings,
                init_data=validated_init_data,
                request_start_param=request.start_param,
            )
            if isinstance(result, _BootstrapResult):
                await _append_launch_observed_event(
                    session,
                    result=result,
                    init_data=validated_init_data,
                    observed_at=_utcnow(),
                )
    except MaxLaunchError as exc:
        logger.warning("max.launch.validation_failed", extra={"code": exc.code})
        _raise_max_http_error(
            status_code=exc.status_code,
            code=exc.code,
            message=str(exc),
        )
    except ValueError as exc:
        logger.warning(
            "max.launch.init_data_invalid",
            extra={"reason": exc.__class__.__name__},
        )
        _raise_max_http_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_init_data",
            message="Invalid MAX initData.",
        )

    return MaxLaunchResponse(
        surface=CandidateJourneySurface.MAX_MINIAPP.value,
        auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
        capabilities=_capabilities(settings),
        binding=(
            MaxLaunchBindingInfo(
                status="bound",
                code=None,
                message="Кандидатский доступ готов.",
                requires_contact=False,
                start_param=result.start_param,
                chat_url=_chat_url(settings, start_param=result.start_param),
            )
            if isinstance(result, _BootstrapResult)
            else MaxLaunchBindingInfo(
                status=result.status,
                code=result.code,
                message=result.message,
                requires_contact=result.requires_contact,
                start_param=None,
                chat_url=_chat_url(settings),
            )
        ),
        candidate=(
            MaxLaunchCandidateSummary(
                id=result.candidate.id,
                candidate_id=result.candidate.candidate_id,
                application_id=result.access_session.application_id,
            )
            if isinstance(result, _BootstrapResult)
            else None
        ),
        session=(
            MaxLaunchSessionSummary(
                id=result.access_session.id,
                session_id=result.access_session.session_id,
                journey_session_id=result.journey_session.id,
                status=result.access_session.status,
                surface=result.access_session.journey_surface,
                auth_method=result.access_session.auth_method,
                launch_channel=result.access_session.launch_channel,
                reused=result.reused,
            )
            if isinstance(result, _BootstrapResult)
            else None
        ),
    )


__all__ = [
    "router",
    "launch_max_miniapp",
    "bootstrap_max_launch",
    "bootstrap_max_global_intake_token",
    "MaxLaunchError",
]
