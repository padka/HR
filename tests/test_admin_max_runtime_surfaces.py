from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from backend.apps.admin_ui.app import create_app
from backend.core import settings as settings_module
from backend.core.db import async_session
from backend.core.messenger.protocol import MessengerPlatform
from backend.core.messenger.registry import unregister_adapter
from backend.domain.candidates.max_launch_invites import create_max_launch_invite
from backend.domain.candidates.models import (
    CandidateAccessToken,
    ChatMessage,
    User,
)
from backend.domain.models import ApplicationEvent, AuditLog
from fastapi.testclient import TestClient
from sqlalchemy import select

BOT_TOKEN = "max-rollout-test-token"


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


class _FakeTimeout:
    def __init__(self, value: float):
        self.value = value


class _FakeMaxAdapter:
    is_configured = True

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_message(self, chat_id, text: str, *, buttons=None, parse_mode=None, correlation_id=None):
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "buttons": buttons,
                "parse_mode": parse_mode,
                "correlation_id": correlation_id,
            }
        )
        return SimpleNamespace(success=True, message_id=f"msg-{len(self.calls)}", error=None)


class _FakeFailingMaxAdapter(_FakeMaxAdapter):
    async def send_message(self, chat_id, text: str, *, buttons=None, parse_mode=None, correlation_id=None):
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "buttons": buttons,
                "parse_mode": parse_mode,
                "correlation_id": correlation_id,
            }
        )
        return SimpleNamespace(success=False, message_id=None, error="provider_down")


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    settings_module.get_settings.cache_clear()
    unregister_adapter(MessengerPlatform.MAX)
    yield
    unregister_adapter(MessengerPlatform.MAX)
    settings_module.get_settings.cache_clear()


@pytest.fixture
def admin_max_app(monkeypatch: pytest.MonkeyPatch):
    async def fake_setup(app):
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ALLOW_DEV_AUTOADMIN", "0")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv(
        "BOT_CALLBACK_SECRET",
        "test-bot-callback-secret-0123456789abcdef012",
    )
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    return create_app()


@pytest.fixture
def max_launch_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    settings_module.get_settings.cache_clear()

    from backend.apps.admin_api.main import create_app as create_admin_api_app

    return create_admin_api_app()


def _login(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin", "redirect_to": "/"},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}


def _csrf(client: TestClient) -> str:
    response = client.get("/api/csrf")
    assert response.status_code == 200
    token = (response.json() or {}).get("token")
    assert isinstance(token, str) and token
    return token


async def _seed_candidate(
    *,
    name: str = "MAX Rollout Candidate",
    max_user_id: str | None = None,
    messenger_platform: str | None = None,
) -> User:
    async with async_session() as session:
        candidate = User(
            fio=name,
            city="Москва",
            source="max" if max_user_id else "manual",
            messenger_platform=messenger_platform,
            max_user_id=max_user_id,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return candidate


async def _load_rollout_tokens(candidate_id: int) -> list[CandidateAccessToken]:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateAccessToken)
            .where(CandidateAccessToken.candidate_id == candidate_id)
            .order_by(CandidateAccessToken.id.asc())
        )
        return list(result.scalars().all())


async def _load_rollout_events(candidate_id: int) -> list[ApplicationEvent]:
    async with async_session() as session:
        result = await session.execute(
            select(ApplicationEvent)
            .where(ApplicationEvent.candidate_id == candidate_id)
            .order_by(ApplicationEvent.id.asc())
        )
        return list(result.scalars().all())


async def _load_rollout_audit(candidate_id: int) -> list[AuditLog]:
    async with async_session() as session:
        result = await session.execute(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "candidate",
                AuditLog.entity_id == str(candidate_id),
            )
            .order_by(AuditLog.id.asc())
        )
        return list(result.scalars().all())


async def _load_chat_messages(candidate_id: int) -> list[ChatMessage]:
    async with async_session() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.candidate_id == candidate_id)
            .order_by(ChatMessage.id.asc())
        )
        return list(result.scalars().all())


def _generate_max_init_data(
    *,
    user_id: int,
    start_param: str,
    bot_token: str = BOT_TOKEN,
    query_id: str = "qa-query-1",
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
        "start_param": start_param,
    }
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


def test_max_runtime_health_reports_disabled_snapshot(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("MAX_INVITE_ROLLOUT_ENABLED", raising=False)
    monkeypatch.delenv("MAX_ADAPTER_ENABLED", raising=False)
    monkeypatch.delenv("MAX_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MAX_BOT_API_SECRET", raising=False)
    monkeypatch.delenv("MAX_WEBHOOK_SECRET", raising=False)
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.get("/health/max")

    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"] == "max"
    assert payload["status"] == "disabled"
    assert payload["runtime"]["status"] == "disabled"
    assert payload["runtime"]["invite_rollout_enabled"] is False
    assert payload["config"]["invite_rollout_enabled"] is False
    assert payload["config"]["bot_token_configured"] is False
    assert payload["config"]["bot_api_secret_configured"] is False
    assert payload["config"]["webhook_secret_configured"] is False


def test_max_runtime_health_reports_canonical_secret_configuration(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_BOT_API_SECRET", "max-api-secret")
    monkeypatch.delenv("MAX_WEBHOOK_SECRET", raising=False)
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.get("/health/max")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["bot_api_secret_configured"] is True
    assert payload["config"]["webhook_secret_configured"] is True


def test_max_runtime_sync_requires_csrf(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post("/health/max/sync")

    assert response.status_code == 403


def test_max_runtime_sync_fails_closed_when_adapter_disabled(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post(
            "/health/max/sync",
            headers={"x-csrf-token": _csrf(client)},
        )

    assert response.status_code == 409
    payload = response.json()
    assert payload["sync"]["ok"] is False
    assert payload["sync"]["error"] == "max_adapter_disabled"


def test_max_runtime_sync_returns_remote_profile_and_subscriptions(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    class _FakeAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method: str, path: str):
            assert self.kwargs["headers"]["Authorization"] == "max-token"
            if method == "GET" and path == "/me":
                return SimpleNamespace(
                    status_code=200,
                    json=lambda: {
                        "user_id": 42,
                        "username": "rs_max_bot",
                        "first_name": "RecruitSmart",
                        "is_bot": True,
                    },
                    text="",
                )
            if method == "GET" and path == "/subscriptions":
                return SimpleNamespace(
                    status_code=200,
                    json=lambda: {
                        "subscriptions": [
                            {
                                "url": "https://example.test/max/webhook",
                                "update_types": ["message_created", "bot_started"],
                                "secret": "super-secret-value",
                            }
                        ]
                    },
                    text="",
                )
            raise AssertionError(f"Unexpected MAX request: {method} {path}")

    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "rs_max_bot")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr(
        "backend.apps.admin_ui.services.max_runtime.httpx",
        SimpleNamespace(AsyncClient=_FakeAsyncClient, Timeout=_FakeTimeout),
    )

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post(
            "/health/max/sync",
            headers={"x-csrf-token": _csrf(client)},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["sync"]["ok"] is True
    assert payload["sync"]["profile"]["user_id"] == 42
    assert payload["sync"]["subscriptions"]["count"] == 1
    item = payload["sync"]["subscriptions"]["items"][0]
    assert item["url"] == "https://example.test/max/webhook"
    assert item["update_types"] == ["message_created", "bot_started"]
    assert item["secret_configured"] is True
    assert payload["channel_health"]["status"] == "healthy"


def test_max_runtime_sync_marks_channel_degraded_on_profile_failure(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    class _FakeAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method: str, path: str):
            assert method == "GET"
            assert path == "/me"
            return SimpleNamespace(
                status_code=401,
                json=lambda: {"message": "invalid token"},
                text="invalid token",
            )

    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "bad-token")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr(
        "backend.apps.admin_ui.services.max_runtime.httpx",
        SimpleNamespace(AsyncClient=_FakeAsyncClient, Timeout=_FakeTimeout),
    )

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post(
            "/health/max/sync",
            headers={"x-csrf-token": _csrf(client)},
        )

    assert response.status_code == 502
    payload = response.json()
    assert payload["sync"]["ok"] is False
    assert payload["sync"]["error"] == "profile_probe_failed"
    assert payload["channel_health"]["status"] == "degraded"
    assert payload["channel_health"]["reason"] == "max:profile_probe_failed"


def test_max_rollout_issue_requires_csrf(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="max-user-700", messenger_platform="max")
    )
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            json={},
        )

    assert response.status_code == 403


def test_max_rollout_issue_requires_authenticated_admin(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(_seed_candidate(max_user_id="max-user-authz", messenger_platform="max"))
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        response = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            json={},
        )

    assert response.status_code == 401


def test_max_rollout_issue_fails_closed_when_flag_disabled(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(_seed_candidate(max_user_id="max-user-701"))
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(client)},
            json={},
        )

    assert response.status_code == 409
    payload = response.json()
    assert payload["detail"]["error"] == "max_rollout_disabled"


def test_max_rollout_issue_reuses_token_and_skips_duplicate_send(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="max-user-702", messenger_platform="max")
    )
    adapter = _FakeMaxAdapter()
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max?from=crm")
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "rs_max_bot")
    settings_module.get_settings.cache_clear()

    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.max_rollout.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    with TestClient(admin_max_app) as client:
        _login(client)
        headers = {"x-csrf-token": _csrf(client)}
        first = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers=headers,
            json={"send": True},
        )
        second = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(client)},
            json={"send": True},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["reused_existing"] is False
    assert second_payload["reused_existing"] is True
    assert first_payload["send_state"] == "sent"
    assert second_payload["send_state"] == "sent"
    assert second_payload["status"] == "sent"
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["chat_id"] == "max-user-702"
    tokens = asyncio.run(_load_rollout_tokens(candidate.id))
    assert len(tokens) == 1


def test_max_rollout_dry_run_preview_hides_token_and_persists_safe_audit_trail(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="max-user-704", messenger_platform="max")
    )
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(client)},
            json={"dry_run": True, "send": False},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "preview_ready"
    assert payload["dry_run"] is True
    assert payload["send_state"] == "preview_only"
    assert payload["launch_artifact"]["launch_url"]
    assert payload["launch_artifact"]["launch_url_redacted"] is None
    serialized = json.dumps(payload)
    assert "start_param" not in serialized
    assert "token_hash" not in serialized
    assert "secret_hash" not in serialized

    events = asyncio.run(_load_rollout_events(candidate.id))
    assert [event.event_type for event in events] == ["candidate.access_link.issued"]
    assert "launch_url" not in json.dumps(events[0].metadata_json or {})

    audit_logs = asyncio.run(_load_rollout_audit(candidate.id))
    assert [entry.action for entry in audit_logs] == ["max_invite_issue"]
    assert "launch_url" not in json.dumps(audit_logs[0].changes or {})
    assert "start_param" not in json.dumps(audit_logs[0].changes or {})


def test_max_rollout_rotate_creates_new_token_and_revokes_previous(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="max-user-705", messenger_platform="max")
    )
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        headers = {"x-csrf-token": _csrf(client)}
        first = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers=headers,
            json={"send": False},
        )
        rotate_headers = {"x-csrf-token": _csrf(client)}
        rotated = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers=rotate_headers,
            json={"send": False, "reuse_policy": "rotate_active"},
        )

    assert first.status_code == 200
    assert rotated.status_code == 200
    rotated_payload = rotated.json()
    assert rotated_payload["reused_existing"] is False
    assert rotated_payload["status"] == "issued"

    tokens = asyncio.run(_load_rollout_tokens(candidate.id))
    assert len(tokens) == 2
    assert tokens[0].revoked_at is not None
    assert tokens[1].revoked_at is None
    assert tokens[0].start_param != tokens[1].start_param

    events = asyncio.run(_load_rollout_events(candidate.id))
    assert [event.event_type for event in events] == [
        "candidate.access_link.issued",
        "candidate.access_link.rotated",
    ]

    audit_logs = asyncio.run(_load_rollout_audit(candidate.id))
    assert [entry.action for entry in audit_logs] == ["max_invite_issue", "max_invite_rotate"]


def test_max_rollout_send_fails_closed_when_adapter_disabled(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="max-user-706", messenger_platform="max")
    )
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(client)},
            json={"send": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "send_failed"
    assert payload["send_state"] == "preview_only"

    messages = asyncio.run(_load_chat_messages(candidate.id))
    assert messages == []
    events = asyncio.run(_load_rollout_events(candidate.id))
    assert [event.event_type for event in events] == ["candidate.access_link.issued"]


def test_max_rollout_preview_after_send_request_reuses_token_without_event_conflict(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="max-user-706-preview", messenger_platform="max")
    )
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as client:
        _login(client)
        first = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(client)},
            json={"dry_run": True, "send": False},
        )
        second = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(client)},
            json={"dry_run": False, "send": True},
        )
        third = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(client)},
            json={"dry_run": True, "send": False},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert first.json()["status"] == "preview_ready"
    assert second.json()["status"] == "send_failed"
    assert third.json()["status"] == "preview_ready"
    assert third.json()["reused_existing"] is True

    events = asyncio.run(_load_rollout_events(candidate.id))
    assert [event.event_type for event in events] == [
        "candidate.access_link.issued",
        "candidate.access_link.reused",
        "candidate.access_link.reused",
    ]


def test_max_rollout_send_failure_records_message_failed_event_and_audit(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="max-user-707", messenger_platform="max")
    )
    adapter = _FakeFailingMaxAdapter()
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "rs_max_bot")
    settings_module.get_settings.cache_clear()

    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.max_rollout.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    with TestClient(admin_max_app) as client:
        _login(client)
        response = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(client)},
            json={"send": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "send_failed"
    assert payload["send_state"] == "failed"

    messages = asyncio.run(_load_chat_messages(candidate.id))
    assert len(messages) == 1
    assert messages[0].status == "failed"
    assert messages[0].error == "provider_down"

    events = asyncio.run(_load_rollout_events(candidate.id))
    assert [event.event_type for event in events] == [
        "candidate.access_link.issued",
        "message.intent_created",
        "message.failed",
    ]
    assert (events[-1].metadata_json or {}).get("failure_code") == "provider_down"

    audit_logs = asyncio.run(_load_rollout_audit(candidate.id))
    assert [entry.action for entry in audit_logs] == ["max_invite_issue", "max_invite_send"]


def test_candidate_detail_includes_max_rollout_summary_and_revoke_endpoint(
    admin_max_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="max-user-703", messenger_platform="max")
    )
    adapter = _FakeMaxAdapter()
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "rs_max_bot")
    settings_module.get_settings.cache_clear()
    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.max_rollout.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )
    asyncio.run(create_max_launch_invite(candidate.id))

    with TestClient(admin_max_app) as client:
        _login(client)
        detail_response = client.get(f"/api/candidates/{candidate.id}")
        revoke_response = client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite/revoke",
            headers={"x-csrf-token": _csrf(client)},
        )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["max_rollout"]["enabled"] is True
    assert detail_payload["max_rollout"]["status"] == "issued"
    assert detail_payload["max_rollout"]["status_label"] == "Выдано"
    assert detail_payload["max_rollout"]["summary"] == "Приглашение подготовлено и готово к отправке кандидату."
    assert detail_payload["max_rollout"]["hint"] == "Проверьте предпросмотр перед отправкой."
    assert detail_payload["max_rollout"]["launch_state"] == "not_launched"
    assert detail_payload["max_rollout"]["launch_observation"]["launched"] is False
    assert detail_payload["max_rollout"]["access_token_id"] is not None
    assert detail_payload["max_rollout"]["actions"]["preview"]["label"] == "Предпросмотр"
    assert detail_payload["max_rollout"]["actions"]["send"]["label"] == "Отправить"
    assert detail_payload["max_rollout"]["actions"]["reissue"]["label"] == "Перевыпустить"
    assert detail_payload["max_rollout"]["flow_statuses"][-1]["label"] == "Ручная проверка"

    assert revoke_response.status_code == 200
    revoke_payload = revoke_response.json()
    assert revoke_payload["status"] == "revoked"
    assert revoke_payload["summary"]["status"] == "revoked"
    assert revoke_payload["summary"]["revoked_at"] is not None


def test_max_rollout_revoke_fails_closed_on_follow_up_max_launch(
    admin_max_app,
    max_launch_app,
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = asyncio.run(
        _seed_candidate(max_user_id="700703", messenger_platform="max")
    )
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    settings_module.get_settings.cache_clear()

    with TestClient(admin_max_app) as admin_client:
        _login(admin_client)
        issue_response = admin_client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite",
            headers={"x-csrf-token": _csrf(admin_client)},
            json={"dry_run": True, "send": False},
        )
        assert issue_response.status_code == 200

        active_token = asyncio.run(_load_rollout_tokens(candidate.id))[-1]
        start_param = str(active_token.start_param or "")
        assert start_param

        revoke_response = admin_client.post(
            f"/api/candidates/{candidate.id}/max-launch-invite/revoke",
            headers={"x-csrf-token": _csrf(admin_client)},
        )
        assert revoke_response.status_code == 200

    with TestClient(max_launch_app) as launch_client:
        launch_response = launch_client.post(
            "/api/max/launch",
            json={"init_data": _generate_max_init_data(user_id=700703, start_param=start_param)},
        )

    assert launch_response.status_code == 410
    assert launch_response.json()["detail"]["code"] == "launch_context_revoked"
