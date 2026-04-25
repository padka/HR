from __future__ import annotations

import re
from itertools import count
from urllib.parse import parse_qs, urlparse

import pytest
from backend.core import settings as settings_module
from backend.core.db import async_session
from backend.domain.candidates.max_launch_invites import (
    MaxLaunchInviteError,
    MaxLaunchInviteLifecycleAction,
    create_max_launch_invite,
)
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


_MAX_USER_ID_SEQ = count(1)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


async def _seed_candidate(
    *,
    name: str = "MAX Launch Candidate",
    max_user_id: str | None = None,
) -> User:
    async with async_session() as session:
        candidate = User(
            fio=name,
            city="Москва",
            source="max",
            messenger_platform="max",
            max_user_id=max_user_id or f"max-user-{next(_MAX_USER_ID_SEQ)}",
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return candidate


async def _seed_application(candidate_id: int) -> Application:
    async with async_session() as session:
        application_id = None
        bind = session.get_bind()
        if bind is not None and bind.dialect.name == "sqlite":
            application_id = int(
                await session.scalar(select(func.coalesce(func.max(Application.id), 0) + 1))
                or 1
            )
        application = Application(
            id=application_id,
            candidate_id=candidate_id,
            source="max",
            lifecycle_status="new",
        )
        session.add(application)
        await session.commit()
        await session.refresh(application)
        return application


async def _load_tokens(candidate_id: int) -> list[CandidateAccessToken]:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateAccessToken)
            .where(CandidateAccessToken.candidate_id == candidate_id)
            .order_by(CandidateAccessToken.id.asc())
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_create_max_launch_invite_creates_preview_and_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")

    candidate = await _seed_candidate()
    application = await _seed_application(candidate.id)

    preview = await create_max_launch_invite(candidate.id, application.id)

    assert preview.dry_run is True
    assert re.fullmatch(r"[A-Za-z0-9_-]{10,64}", preview.start_param)
    assert "MAX Launch Candidate" not in preview.message_preview
    assert preview.max_launch_url is not None
    assert preview.lifecycle.action == MaxLaunchInviteLifecycleAction.ISSUED
    assert preview.lifecycle.active_token_id is not None
    assert preview.lifecycle.revoked_token_ids == ()

    tokens = await _load_tokens(candidate.id)
    assert len(tokens) == 1
    token = tokens[0]
    assert token.application_id == application.id
    assert token.token_kind == CandidateAccessTokenKind.LAUNCH.value
    assert token.journey_surface == CandidateJourneySurface.MAX_MINIAPP.value
    assert token.auth_method == CandidateAccessAuthMethod.MAX_INIT_DATA.value
    assert token.launch_channel == CandidateLaunchChannel.MAX.value
    assert token.start_param == preview.start_param
    assert token.token_hash
    assert token.secret_hash


@pytest.mark.asyncio
async def test_create_max_launch_invite_reuses_active_launch_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")

    candidate = await _seed_candidate(name="Reusable Launch Candidate")

    first = await create_max_launch_invite(candidate.id)
    second = await create_max_launch_invite(candidate.id)

    assert first.start_param == second.start_param
    assert second.lifecycle.action == MaxLaunchInviteLifecycleAction.REUSED
    assert second.lifecycle.active_token_id == first.lifecycle.active_token_id
    tokens = await _load_tokens(candidate.id)
    assert len(tokens) == 1


@pytest.mark.asyncio
async def test_create_max_launch_invite_builds_launch_url_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max?from=crm")

    candidate = await _seed_candidate(name="Enabled MAX Candidate")

    preview = await create_max_launch_invite(candidate.id)

    assert preview.dry_run is False
    assert preview.max_launch_url is not None
    parsed = urlparse(preview.max_launch_url)
    query = parse_qs(parsed.query)
    assert query["from"] == ["crm"]
    assert query["startapp"] == [preview.start_param]


@pytest.mark.asyncio
async def test_create_max_launch_invite_rotates_existing_launch_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")

    candidate = await _seed_candidate(name="Rotate Launch Candidate")

    first = await create_max_launch_invite(candidate.id)
    rotated = await create_max_launch_invite(
        candidate.id,
        rotate_active=True,
        revoke_reason="operator_rotated",
    )

    assert rotated.start_param is not None
    assert rotated.start_param != first.start_param
    assert rotated.lifecycle.action == MaxLaunchInviteLifecycleAction.ROTATED
    assert rotated.lifecycle.replaced_token_id == first.lifecycle.active_token_id
    assert rotated.lifecycle.revoked_token_ids == (first.lifecycle.active_token_id,)

    tokens = await _load_tokens(candidate.id)
    assert len(tokens) == 2
    revoked_token, active_token = tokens
    assert revoked_token.revoked_at is not None
    assert revoked_token.metadata_json["revocation_reason"] == "operator_rotated"
    assert active_token.start_param == rotated.start_param
    assert active_token.revoked_at is None


@pytest.mark.asyncio
async def test_create_max_launch_invite_revokes_existing_launch_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")

    candidate = await _seed_candidate(name="Revoke Launch Candidate")

    first = await create_max_launch_invite(candidate.id)
    revoked = await create_max_launch_invite(
        candidate.id,
        revoke_active=True,
        revoke_reason="manual_revoke",
    )

    assert revoked.start_param is None
    assert revoked.max_launch_url is None
    assert revoked.max_chat_url is None
    assert revoked.expires_at is None
    assert revoked.lifecycle.action == MaxLaunchInviteLifecycleAction.REVOKED
    assert revoked.lifecycle.revoked_token_ids == (first.lifecycle.active_token_id,)

    tokens = await _load_tokens(candidate.id)
    assert len(tokens) == 1
    assert tokens[0].revoked_at is not None
    assert tokens[0].metadata_json["revocation_reason"] == "manual_revoke"


@pytest.mark.asyncio
async def test_create_max_launch_invite_rejects_foreign_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")

    candidate = await _seed_candidate(name="Launch Owner")
    foreign_candidate = await _seed_candidate(name="Foreign Owner")
    foreign_application = await _seed_application(foreign_candidate.id)

    with pytest.raises(MaxLaunchInviteError, match="Application is unavailable"):
        await create_max_launch_invite(candidate.id, foreign_application.id)

    tokens = await _load_tokens(candidate.id)
    assert tokens == []
