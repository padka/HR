"""Bounded MAX mini-app launch preview issuance."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.core.db import async_session
from backend.core.settings import Settings, get_settings
from backend.domain.applications.contracts import ApplicationEventType
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    User,
)
from backend.domain.models import Application
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

MAX_LAUNCH_DEFAULT_TTL = timedelta(hours=24)
MAX_START_PARAM_LENGTH_BYTES = 16


class MaxLaunchInviteError(ValueError):
    """Raised when MAX launch preview issuance cannot continue safely."""


class MaxLaunchInviteLifecycleAction(str, Enum):
    ISSUED = "issued"
    REUSED = "reused"
    ROTATED = "rotated"
    REVOKED = "revoked"


@dataclass(frozen=True)
class MaxLaunchInviteLifecycleMetadata:
    action: MaxLaunchInviteLifecycleAction
    event_type: str
    active_token_id: int | None
    revoked_token_ids: tuple[int, ...] = ()
    replaced_token_id: int | None = None


@dataclass(frozen=True)
class MaxLaunchInvitePreview:
    start_param: str | None
    max_launch_url: str | None
    max_chat_url: str | None
    message_preview: str
    expires_at: datetime | None
    dry_run: bool
    lifecycle: MaxLaunchInviteLifecycleMetadata


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_ttl(expires_in: timedelta | None) -> timedelta:
    ttl = expires_in or MAX_LAUNCH_DEFAULT_TTL
    if ttl <= timedelta(0):
        raise MaxLaunchInviteError("MAX launch invite TTL must be positive.")
    return ttl


async def _sqlite_next_pk(session: AsyncSession) -> int | None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return None
    next_id = await session.scalar(
        select(func.coalesce(func.max(CandidateAccessToken.id), 0) + 1)
    )
    return int(next_id or 1)


def _generate_start_param() -> str:
    return secrets.token_urlsafe(MAX_START_PARAM_LENGTH_BYTES).rstrip("=")


def _hash_token_material(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _load_candidate(
    session: AsyncSession,
    candidate_id: int,
) -> User:
    candidate = await session.get(User, candidate_id)
    if candidate is None or not candidate.is_active:
        raise MaxLaunchInviteError("Candidate is unavailable for MAX launch preview.")
    return candidate


async def _load_application(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int,
) -> Application:
    application = await session.get(Application, application_id)
    if (
        application is None
        or int(application.candidate_id) != int(candidate_id)
        or application.archived_at is not None
    ):
        raise MaxLaunchInviteError(
            "Application is unavailable for the requested MAX launch preview."
        )
    return application


async def _find_reusable_launch_token(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int | None,
    now: datetime,
) -> CandidateAccessToken | None:
    stmt = (
        select(CandidateAccessToken)
        .where(
            CandidateAccessToken.candidate_id == candidate_id,
            CandidateAccessToken.application_id.is_(application_id)
            if application_id is None
            else CandidateAccessToken.application_id == application_id,
            CandidateAccessToken.token_kind == CandidateAccessTokenKind.LAUNCH.value,
            CandidateAccessToken.journey_surface
            == CandidateJourneySurface.MAX_MINIAPP.value,
            CandidateAccessToken.auth_method
            == CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            CandidateAccessToken.launch_channel == CandidateLaunchChannel.MAX.value,
            CandidateAccessToken.revoked_at.is_(None),
            CandidateAccessToken.expires_at > now,
            CandidateAccessToken.start_param.is_not(None),
        )
        .order_by(CandidateAccessToken.created_at.desc(), CandidateAccessToken.id.desc())
        .limit(1)
        .with_for_update()
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_active_launch_tokens(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int | None,
    now: datetime,
) -> list[CandidateAccessToken]:
    stmt = (
        select(CandidateAccessToken)
        .where(
            CandidateAccessToken.candidate_id == candidate_id,
            CandidateAccessToken.application_id.is_(application_id)
            if application_id is None
            else CandidateAccessToken.application_id == application_id,
            CandidateAccessToken.token_kind == CandidateAccessTokenKind.LAUNCH.value,
            CandidateAccessToken.journey_surface
            == CandidateJourneySurface.MAX_MINIAPP.value,
            CandidateAccessToken.auth_method
            == CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            CandidateAccessToken.launch_channel == CandidateLaunchChannel.MAX.value,
            CandidateAccessToken.revoked_at.is_(None),
            CandidateAccessToken.expires_at > now,
            CandidateAccessToken.start_param.is_not(None),
        )
        .order_by(CandidateAccessToken.created_at.desc(), CandidateAccessToken.id.desc())
        .with_for_update()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _build_max_launch_url(
    settings: Settings,
    *,
    start_param: str,
) -> str | None:
    base_url = str(getattr(settings, "max_miniapp_url", "") or "").strip()
    if not base_url:
        return None
    parsed = urlsplit(base_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("startapp", start_param))
    return urlunsplit(parsed._replace(query=urlencode(query)))


def _build_max_chat_url(
    settings: Settings,
    *,
    start_param: str,
) -> str | None:
    public_bot_name = str(getattr(settings, "max_public_bot_name", "") or "").strip()
    if not public_bot_name:
        return None
    return f"https://max.ru/{public_bot_name}?start={start_param}"


def _build_message_preview(
    *,
    action: MaxLaunchInviteLifecycleAction,
    dry_run: bool,
) -> str:
    if action == MaxLaunchInviteLifecycleAction.REVOKED:
        return "MAX launch invite has been revoked."
    prefix = "[DRY RUN] " if dry_run else ""
    return (
        f"{prefix}Откройте мини-приложение MAX, чтобы продолжить путь кандидата "
        "и перейти к следующему шагу после анкеты."
    )


def _event_type_for_action(action: MaxLaunchInviteLifecycleAction) -> str:
    mapping = {
        MaxLaunchInviteLifecycleAction.ISSUED: ApplicationEventType.CANDIDATE_ACCESS_LINK_ISSUED.value,
        MaxLaunchInviteLifecycleAction.REUSED: ApplicationEventType.CANDIDATE_ACCESS_LINK_REUSED.value,
        MaxLaunchInviteLifecycleAction.ROTATED: ApplicationEventType.CANDIDATE_ACCESS_LINK_ROTATED.value,
        MaxLaunchInviteLifecycleAction.REVOKED: ApplicationEventType.CANDIDATE_ACCESS_LINK_REVOKED.value,
    }
    return mapping[action]


def _mark_token_revoked(
    token: CandidateAccessToken,
    *,
    now: datetime,
    reason: str,
) -> None:
    token.revoked_at = now
    metadata = dict(token.metadata_json or {})
    metadata["revocation_reason"] = reason
    token.metadata_json = metadata


async def _issue_launch_preview(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int | None,
    expires_in: timedelta | None,
    issued_by_type: str | None,
    issued_by_id: str | None,
    idempotency_key: str | None,
    correlation_id: str | None,
    settings: Settings,
    now: datetime,
    rotate_active: bool,
    revoke_active: bool,
    revoke_reason: str | None,
) -> MaxLaunchInvitePreview:
    if rotate_active and revoke_active:
        raise MaxLaunchInviteError("MAX launch invite cannot rotate and revoke in one call.")

    candidate = await _load_candidate(session, candidate_id)
    await session.scalar(select(User.id).where(User.id == candidate.id).with_for_update())
    if application_id is not None:
        await _load_application(
            session,
            candidate_id=candidate.id,
            application_id=application_id,
        )

    active_tokens = await _load_active_launch_tokens(
        session,
        candidate_id=candidate.id,
        application_id=application_id,
        now=now,
    )

    if revoke_active:
        revoked_token_ids: tuple[int, ...] = tuple(int(token.id) for token in active_tokens)
        for token in active_tokens:
            _mark_token_revoked(
                token,
                now=now,
                reason=revoke_reason or "operator_revoked",
            )
        return MaxLaunchInvitePreview(
            start_param=None,
            max_launch_url=None,
            max_chat_url=None,
            message_preview=_build_message_preview(
                action=MaxLaunchInviteLifecycleAction.REVOKED,
                dry_run=False,
            ),
            expires_at=None,
            dry_run=True,
            lifecycle=MaxLaunchInviteLifecycleMetadata(
                action=MaxLaunchInviteLifecycleAction.REVOKED,
                event_type=_event_type_for_action(MaxLaunchInviteLifecycleAction.REVOKED),
                active_token_id=None,
                revoked_token_ids=revoked_token_ids,
            ),
        )

    reusable = active_tokens[0] if active_tokens else None
    if reusable is not None and reusable.start_param and not rotate_active:
        start_param = str(reusable.start_param)
        expires_at = _as_utc(reusable.expires_at)
        lifecycle = MaxLaunchInviteLifecycleMetadata(
            action=MaxLaunchInviteLifecycleAction.REUSED,
            event_type=_event_type_for_action(MaxLaunchInviteLifecycleAction.REUSED),
            active_token_id=int(reusable.id),
        )
    else:
        replaced_token_id: int | None = None
        revoked_token_ids: tuple[int, ...] = ()
        if rotate_active and active_tokens:
            revoked_token_ids = tuple(int(token.id) for token in active_tokens)
            replaced_token_id = int(active_tokens[0].id)
            for token in active_tokens:
                _mark_token_revoked(
                    token,
                    now=now,
                    reason=revoke_reason or "rotated",
                )
        ttl = _normalize_ttl(expires_in)
        expires_at = now + ttl
        start_param = _generate_start_param()
        token_id = await _sqlite_next_pk(session)
        launch_token = CandidateAccessToken(
            id=token_id,
            token_hash=_hash_token_material(secrets.token_urlsafe(24)),
            candidate_id=candidate.id,
            application_id=application_id,
            token_kind=CandidateAccessTokenKind.LAUNCH.value,
            journey_surface=CandidateJourneySurface.MAX_MINIAPP.value,
            auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            launch_channel=CandidateLaunchChannel.MAX.value,
            start_param=start_param,
            correlation_id=correlation_id or str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            issued_by_type=issued_by_type,
            issued_by_id=issued_by_id,
            expires_at=expires_at,
            secret_hash=_hash_token_material(secrets.token_urlsafe(24)),
            launch_payload_json={"preview_kind": "max_miniapp_launch"},
        )
        session.add(launch_token)
        await session.flush()
        lifecycle_action = (
            MaxLaunchInviteLifecycleAction.ROTATED
            if revoked_token_ids
            else MaxLaunchInviteLifecycleAction.ISSUED
        )
        lifecycle = MaxLaunchInviteLifecycleMetadata(
            action=lifecycle_action,
            event_type=_event_type_for_action(lifecycle_action),
            active_token_id=int(launch_token.id),
            revoked_token_ids=revoked_token_ids,
            replaced_token_id=replaced_token_id,
        )

    launch_url = _build_max_launch_url(settings, start_param=start_param)
    chat_url = _build_max_chat_url(settings, start_param=start_param)
    dry_run = not bool(getattr(settings, "max_adapter_enabled", False)) or not bool(
        str(getattr(settings, "max_bot_token", "") or "").strip()
    )
    return MaxLaunchInvitePreview(
        start_param=start_param,
        max_launch_url=launch_url,
        max_chat_url=chat_url,
        message_preview=_build_message_preview(
            action=lifecycle.action,
            dry_run=dry_run,
        ),
        expires_at=expires_at,
        dry_run=dry_run or launch_url is None,
        lifecycle=lifecycle,
    )


async def create_max_launch_invite(
    candidate_id: int,
    application_id: int | None = None,
    *,
    session: AsyncSession | None = None,
    expires_in: timedelta | None = None,
    issued_by_type: str | None = None,
    issued_by_id: str | None = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    now: datetime | None = None,
    settings: Settings | None = None,
    rotate_active: bool = False,
    revoke_active: bool = False,
    revoke_reason: str | None = None,
) -> MaxLaunchInvitePreview:
    resolved_now = now or _utcnow()
    resolved_settings = settings or get_settings()

    async def _run(db_session: AsyncSession) -> MaxLaunchInvitePreview:
        return await _issue_launch_preview(
            db_session,
            candidate_id=candidate_id,
            application_id=application_id,
            expires_in=expires_in,
            issued_by_type=issued_by_type,
            issued_by_id=issued_by_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            settings=resolved_settings,
            now=resolved_now,
            rotate_active=rotate_active,
            revoke_active=revoke_active,
            revoke_reason=revoke_reason,
        )

    if session is not None:
        return await _run(session)

    async with async_session() as db_session:
        async with db_session.begin():
            preview = await _run(db_session)
        return preview


__all__ = [
    "MaxLaunchInviteError",
    "MaxLaunchInviteLifecycleAction",
    "MaxLaunchInviteLifecycleMetadata",
    "MaxLaunchInvitePreview",
    "create_max_launch_invite",
]
