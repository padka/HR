from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest
from backend.core.db import async_session
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySession,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    User,
)
from backend.domain.models import Application, ApplicationEvent
from fastapi.testclient import TestClient
from sqlalchemy import func, select

BOT_TOKEN = "max-launch-test-token"


def _generate_max_init_data(
    *,
    user_id: int,
    bot_token: str = BOT_TOKEN,
    start_param: str | None = "max_launch_ref",
    query_id: str = "query-1",
    auth_date: int | None = None,
) -> str:
    payload = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": query_id,
        "user": json.dumps(
            {
                "id": user_id,
                "username": "max_candidate",
                "first_name": "Max",
                "language_code": "ru",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    if start_param is not None:
        payload["start_param"] = start_param

    launch_params = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    payload["hash"] = hmac.new(
        secret_key,
        launch_params.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(payload)


@pytest.fixture
def max_api_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "test-max-bot")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    from backend.apps.admin_api.main import create_app

    app = create_app()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings_module.get_settings.cache_clear()


async def _seed_launch_context(
    *,
    start_param: str = "max_launch_ref",
    provider_user_id: str | None = None,
    candidate_max_user_id: str | None = None,
    with_application: bool = False,
) -> dict[str, int | str | None]:
    now = datetime.now(UTC)
    async with async_session() as session:
        next_token_id = int(
            await session.scalar(select(func.coalesce(func.max(CandidateAccessToken.id), 0) + 1))
            or 1
        )
        candidate = User(
            fio="MAX Candidate",
            city="Москва",
            messenger_platform="max",
            max_user_id=candidate_max_user_id,
            source="max",
        )
        session.add(candidate)
        await session.flush()

        application_id: int | None = None
        if with_application:
            next_application_id = int(
                await session.scalar(select(func.coalesce(func.max(Application.id), 0) + 1))
                or 1
            )
            application = Application(
                id=next_application_id,
                candidate_id=candidate.id,
                source="max",
                lifecycle_status="new",
            )
            session.add(application)
            await session.flush()
            application_id = int(application.id)

        launch_token = CandidateAccessToken(
            id=next_token_id,
            token_hash=hashlib.sha256(f"token:{start_param}".encode()).hexdigest(),
            candidate_id=candidate.id,
            application_id=application_id,
            token_kind=CandidateAccessTokenKind.LAUNCH.value,
            journey_surface=CandidateJourneySurface.MAX_MINIAPP.value,
            auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            launch_channel=CandidateLaunchChannel.MAX.value,
            start_param=start_param,
            provider_user_id=provider_user_id,
            expires_at=now + timedelta(hours=1),
        )
        session.add(launch_token)
        await session.commit()
        return {
            "candidate_id": candidate.id,
            "candidate_public_id": candidate.candidate_id,
            "token_id": launch_token.id,
            "start_param": start_param,
            "application_id": application_id,
        }


async def _count_access_sessions() -> int:
    async with async_session() as session:
        return int(
            await session.scalar(select(func.count()).select_from(CandidateAccessSession)) or 0
        )


async def _load_access_session(candidate_id: int) -> CandidateAccessSession | None:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateAccessSession)
            .where(CandidateAccessSession.candidate_id == candidate_id)
            .order_by(CandidateAccessSession.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _load_journey_session(candidate_id: int) -> CandidateJourneySession | None:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateJourneySession)
            .where(CandidateJourneySession.candidate_id == candidate_id)
            .order_by(CandidateJourneySession.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _load_token(token_id: int) -> CandidateAccessToken | None:
    async with async_session() as session:
        return await session.get(CandidateAccessToken, token_id)


async def _load_candidate_by_max_user_id(max_user_id: str) -> User | None:
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .where(User.max_user_id == max_user_id)
            .order_by(User.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _load_application_events(candidate_id: int) -> list[ApplicationEvent]:
    async with async_session() as session:
        result = await session.execute(
            select(ApplicationEvent)
            .where(ApplicationEvent.candidate_id == candidate_id)
            .order_by(ApplicationEvent.id.asc())
        )
        return list(result.scalars().all())


async def _seed_bound_candidate_without_start_param(
    *,
    max_user_id: str,
    start_param: str,
) -> dict[str, int | str | None]:
    return await _seed_launch_context(
        start_param=start_param,
        candidate_max_user_id=max_user_id,
    )


def test_max_launch_bootstraps_access_session(max_api_client):
    seeded = asyncio.run(_seed_launch_context(with_application=True))

    response = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700001)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "max_miniapp"
    assert payload["auth_method"] == "max_init_data"
    assert payload["candidate"]["id"] == seeded["candidate_id"]
    assert payload["session"]["reused"] is False
    assert payload["session"]["session_id"]
    assert payload["binding"]["chat_url"] == "https://max.ru/test-max-bot?start=max_launch_ref"
    assert "provider" not in payload
    assert "start_param" not in payload

    access_session = asyncio.run(_load_access_session(seeded["candidate_id"]))
    assert access_session is not None
    assert access_session.provider_user_id == "700001"
    assert access_session.journey_surface == "max_miniapp"
    assert access_session.auth_method == "max_init_data"
    assert payload["session"]["session_id"] == access_session.session_id
    assert access_session.metadata_json is not None
    assert "launch_auth_date" in access_session.metadata_json
    assert "start_param" not in access_session.metadata_json

    journey_session = asyncio.run(_load_journey_session(seeded["candidate_id"]))
    assert journey_session is not None
    assert journey_session.last_access_session_id == access_session.id
    assert journey_session.last_surface == "max_miniapp"

    token = asyncio.run(_load_token(seeded["token_id"]))
    assert token is not None
    assert token.provider_user_id == "700001"

    events = asyncio.run(_load_application_events(seeded["candidate_id"]))
    assert [event.event_type for event in events] == ["candidate.access_link.launched"]
    event = events[0]
    assert event.application_id == seeded["application_id"]
    assert event.channel == "max"
    assert event.source == "max"
    assert event.actor_type == "candidate"
    assert event.actor_id == "700001"
    assert event.metadata_json["launch_token_id"] == seeded["token_id"]
    assert event.metadata_json["journey_surface"] == "max_miniapp"
    assert event.metadata_json["auth_method"] == "max_init_data"
    assert event.metadata_json["provider_session_bound"] is True
    assert event.metadata_json["reused_session"] is False


def test_max_launch_reuses_existing_session_for_same_query_id(max_api_client):
    seeded = asyncio.run(_seed_launch_context(start_param="stable_ref"))
    init_data = _generate_max_init_data(
        user_id=700002,
        start_param="stable_ref",
        query_id="stable-query",
    )

    first = max_api_client.post("/api/max/launch", json={"init_data": init_data})
    second = max_api_client.post("/api/max/launch", json={"init_data": init_data})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["session"]["id"] == second.json()["session"]["id"]
    assert first.json()["session"]["session_id"] == second.json()["session"]["session_id"]
    assert second.json()["session"]["reused"] is True
    assert asyncio.run(_count_access_sessions()) == 1

    access_session = asyncio.run(_load_access_session(seeded["candidate_id"]))
    assert access_session is not None
    assert access_session.provider_session_id == "stable-query"

    events = asyncio.run(_load_application_events(seeded["candidate_id"]))
    assert len(events) == 1
    assert events[0].metadata_json["_rs_source_ref"] == "stable-query"


def test_max_launch_falls_back_to_bound_candidate_when_start_param_missing(max_api_client):
    seeded = asyncio.run(
        _seed_bound_candidate_without_start_param(
            max_user_id="700099",
            start_param="bound-system-button-ref",
        )
    )

    response = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700099, start_param=None)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["id"] == seeded["candidate_id"]
    assert payload["binding"]["chat_url"] == "https://max.ru/test-max-bot?start=bound-system-button-ref"
    access_session = asyncio.run(_load_access_session(seeded["candidate_id"]))
    assert access_session is not None
    assert access_session.provider_user_id == "700099"


def test_max_launch_rejects_ambiguous_bound_candidate_context(max_api_client):
    asyncio.run(
        _seed_bound_candidate_without_start_param(
            max_user_id="700120",
            start_param="ambiguous-ref-1",
        )
    )
    asyncio.run(
        _seed_bound_candidate_without_start_param(
            max_user_id="700120",
            start_param="ambiguous-ref-2",
        )
    )

    response = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700120, start_param=None)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["binding"]["status"] == "manual_review_required"
    assert payload["binding"]["code"] == "launch_context_ambiguous"
    assert payload["binding"]["chat_url"] == "https://max.ru/test-max-bot"


def test_max_launch_rejects_invalid_signature(max_api_client):
    seeded = asyncio.run(_seed_launch_context())
    init_data = _generate_max_init_data(user_id=700003, start_param=str(seeded["start_param"]))
    tampered = init_data.replace("query-1", "query-2")

    response = max_api_client.post("/api/max/launch", json={"init_data": tampered})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_init_data"
    assert response.json()["detail"]["message"] == "Invalid MAX initData."


def test_max_launch_missing_init_data_returns_structured_validation_error(max_api_client):
    response = max_api_client.post("/api/max/launch", json={})

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "invalid_init_data",
        "message": "Откройте кабинет внутри MAX, чтобы передать корректный launch-контекст.",
    }


def test_max_launch_rejects_identity_mismatch(max_api_client):
    asyncio.run(_seed_launch_context(start_param="bound_ref", provider_user_id="700004"))

    response = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700005, start_param="bound_ref")},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "identity_mismatch"


def test_max_launch_rejects_invalid_start_param_shape(max_api_client):
    asyncio.run(_seed_launch_context(start_param="bad/slash"))

    response = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700006, start_param="bad/slash")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_start_param"


def test_max_launch_propagates_application_anchor(max_api_client):
    seeded = asyncio.run(_seed_launch_context(start_param="app_ref", with_application=True))

    response = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700008, start_param="app_ref")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["application_id"] == seeded["application_id"]

    access_session = asyncio.run(_load_access_session(seeded["candidate_id"]))
    journey_session = asyncio.run(_load_journey_session(seeded["candidate_id"]))
    assert access_session is not None
    assert journey_session is not None
    assert access_session.application_id == seeded["application_id"]
    assert journey_session.application_id == seeded["application_id"]


def test_max_launch_global_entry_creates_draft_candidate_and_access_session(max_api_client):
    response = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700099, start_param=None)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["binding"]["status"] == "bound"
    assert payload["binding"]["requires_contact"] is False
    assert payload["binding"]["start_param"]
    assert payload["binding"]["chat_url"] == (
        f"https://max.ru/test-max-bot?start={payload['binding']['start_param']}"
    )
    assert payload["candidate"] is not None
    assert payload["session"] is not None

    candidate = asyncio.run(_load_candidate_by_max_user_id("700099"))
    assert candidate is not None
    assert candidate.id == payload["candidate"]["id"]
    assert candidate.lifecycle_state == "draft"
    assert candidate.candidate_status is None
    assert candidate.messenger_platform == "max"
    assert candidate.source == "max"

    journey_session = asyncio.run(_load_journey_session(int(candidate.id)))
    assert journey_session is not None
    assert journey_session.current_step_key == "test1"
    assert journey_session.entry_channel == "max"

    access_session = asyncio.run(_load_access_session(int(candidate.id)))
    assert access_session is not None
    assert access_session.provider_user_id == "700099"
    assert access_session.application_id is None

    token = asyncio.run(_load_token(int(access_session.origin_token_id)))
    assert token is not None
    assert token.start_param == payload["binding"]["start_param"]
    assert token.journey_session_id == journey_session.id
    assert token.provider_user_id == "700099"


def test_max_launch_global_entry_reuses_same_draft_candidate_for_repeat_visits(max_api_client):
    first = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700199, start_param=None, query_id="draft-query-1")},
    )
    second = max_api_client.post(
        "/api/max/launch",
        json={"init_data": _generate_max_init_data(user_id=700199, start_param=None, query_id="draft-query-2")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["candidate"]["id"] == second.json()["candidate"]["id"]
    assert first.json()["binding"]["start_param"] == second.json()["binding"]["start_param"]


@pytest.mark.skip(reason="Pending PostgreSQL-only proof for MAX launch bind concurrency.")
def test_max_launch_concurrent_first_bind_requires_postgres_proof():
    pass


def test_max_launch_returns_404_when_adapter_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    from backend.apps.admin_api.main import create_app

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/max/launch",
            json={"init_data": _generate_max_init_data(user_id=700007)},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "max_adapter_disabled"


def test_max_launch_rejects_global_entry_when_invite_rollout_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "test-max-bot")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    from backend.apps.admin_api.main import create_app

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/max/launch",
            json={"init_data": _generate_max_init_data(user_id=700909, start_param=None)},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "max_rollout_disabled"
    assert asyncio.run(_load_candidate_by_max_user_id("700909")) is None


def test_max_launch_allows_bound_candidate_recovery_when_invite_rollout_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    asyncio.run(
        _seed_bound_candidate_without_start_param(
            max_user_id="700910",
            start_param="rollout-disabled-bound-ref",
        )
    )
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "test-max-bot")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    from backend.apps.admin_api.main import create_app

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/max/launch",
            json={"init_data": _generate_max_init_data(user_id=700910, start_param=None)},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["binding"]["status"] == "bound"
    assert payload["candidate"]["id"]
