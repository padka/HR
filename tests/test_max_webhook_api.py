from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from backend.core.db import async_session
from backend.core.messenger.protocol import (
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    ChatMessage,
    User,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select


class _FakeMaxAdapter(MessengerProtocol):
    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.answers: list[str] = []

    async def configure(self, **kwargs):
        return None

    async def send_message(self, chat_id, text, *, buttons=None, parse_mode=None, correlation_id=None):
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "buttons": buttons,
                "parse_mode": parse_mode,
                "correlation_id": correlation_id,
            }
        )
        return SendResult(success=True, message_id=f"msg-{len(self.messages)}")

    async def answer_callback(self, callback_id: str, *, message=None, notification=None):
        self.answers.append(callback_id)
        return {"success": True, "notification": notification, "message": message}


@pytest.fixture
def max_webhook_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    monkeypatch.setenv("MAX_WEBHOOK_SECRET", "test-max-secret")
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


async def _seed_launch_context(start_param: str = "max-start-ref") -> int:
    now = datetime.now(UTC)
    async with async_session() as session:
        token_id = int(
            await session.scalar(select(func.coalesce(func.max(CandidateAccessToken.id), 0) + 1))
            or 1
        )
        candidate = User(
            fio="Webhook Candidate",
            city="Москва",
            source="bot",
            messenger_platform="telegram",
        )
        session.add(candidate)
        await session.flush()

        token = CandidateAccessToken(
            id=token_id,
            token_hash=hashlib.sha256(f"token:{start_param}".encode()).hexdigest(),
            candidate_id=candidate.id,
            token_kind=CandidateAccessTokenKind.LAUNCH.value,
            journey_surface=CandidateJourneySurface.MAX_MINIAPP.value,
            auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            launch_channel=CandidateLaunchChannel.MAX.value,
            start_param=start_param,
            expires_at=now + timedelta(hours=1),
        )
        session.add(token)
        await session.commit()
        return candidate.id


async def _seed_max_candidate(max_user_id: str = "max-user-1") -> int:
    async with async_session() as session:
        candidate = User(
            fio="MAX Candidate",
            city="Москва",
            source="max",
            messenger_platform="max",
            max_user_id=max_user_id,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return candidate.id


async def _get_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


async def _chat_messages(candidate_id: int) -> list[ChatMessage]:
    async with async_session() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.candidate_id == candidate_id)
            .order_by(ChatMessage.id.asc())
        )
        return list(result.scalars().all())


def test_max_webhook_rejects_secret_mismatch(max_webhook_client):
    response = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "wrong-secret"},
        json={"update_type": "bot_started"},
    )

    assert response.status_code == 403


def test_max_webhook_accepts_canonical_secret_without_legacy_env(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    monkeypatch.delenv("MAX_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("MAX_BOT_API_SECRET", "test-max-secret")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    response = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={"update_type": "unsupported_update_type"},
    )

    assert response.status_code == 200
    assert response.json()["handled"] is False


def test_max_webhook_bot_started_binds_candidate_and_sends_welcome(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    candidate_id = asyncio.run(_seed_launch_context())
    adapter = _FakeMaxAdapter()

    async def _fake_ensure_max_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr(
        "backend.apps.admin_api.max_webhook.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    response = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "bot_started",
            "timestamp": 1,
            "chat_id": "chat-1",
            "user": {"user_id": 700101, "username": "max_user", "name": "Max User"},
            "payload": "max-start-ref",
        },
    )

    assert response.status_code == 200
    assert response.json()["handled"] is True
    candidate = asyncio.run(_get_candidate(candidate_id))
    assert candidate is not None
    assert candidate.max_user_id == "700101"
    assert candidate.messenger_platform == "max"
    assert candidate.source == "max"
    assert adapter.messages
    assert "Вас ждёт короткая анкета RecruitSmart" in str(adapter.messages[0]["text"])
    assert "выбрать удобные дату и время онлайн-собеседования" in str(adapter.messages[0]["text"])
    buttons = adapter.messages[0]["buttons"]
    assert buttons is not None
    assert len(buttons) == 2
    assert buttons[0][0].text == "Пройти в чате"
    assert buttons[0][0].callback_data == "entry:start_chat:max-start-ref"
    assert buttons[1][0].text == "Нужно другое время"
    assert buttons[1][0].callback_data == "booking:manual_time"
    assert buttons[1][0].kind == "callback"
    assert buttons[1][0].url is None
    history = asyncio.run(_chat_messages(candidate_id))
    assert len(history) == 1
    assert history[0].channel == "max"
    assert history[0].direction == "outbound"


def test_max_webhook_generic_bot_started_sends_orientation_message(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    adapter = _FakeMaxAdapter()

    async def _fake_ensure_max_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr(
        "backend.apps.admin_api.max_webhook.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    response = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "bot_started",
            "timestamp": 1,
            "chat_id": "chat-generic",
            "user": {"user_id": 700102, "username": "generic_max", "name": "Generic User"},
        },
    )

    assert response.status_code == 200
    assert response.json()["handled"] is True
    assert adapter.messages
    assert "Когда RecruitSmart откроет для вас следующий шаг" in str(adapter.messages[0]["text"])
    assert adapter.messages[0]["buttons"] == []


def test_max_webhook_entry_start_chat_bootstraps_questionnaire_without_miniapp_launch(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    candidate_id = asyncio.run(_seed_launch_context("max-start-chat"))
    adapter = _FakeMaxAdapter()

    async def _fake_ensure_max_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr(
        "backend.apps.admin_api.max_webhook.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )
    monkeypatch.setattr(
        "backend.apps.admin_api.max_candidate_chat.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    started = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "bot_started",
            "timestamp": 1,
            "chat_id": "chat-1",
            "user": {"user_id": 700103, "username": "max_user", "name": "Max User"},
            "payload": "max-start-chat",
        },
    )

    assert started.status_code == 200
    adapter.messages.clear()

    callback = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_callback",
            "timestamp": 2,
            "user": {"user_id": "700103"},
            "callback": {
                "callback_id": "cb-entry-start",
                "payload": "entry:start_chat:max-start-chat",
            },
        },
    )

    assert callback.status_code == 200
    assert adapter.answers[-1] == "cb-entry-start"
    assert adapter.messages
    assert "Шаг 1 из" in str(adapter.messages[0]["text"])
    history = asyncio.run(_chat_messages(candidate_id))
    assert any(message.direction == "outbound" and message.channel == "max" for message in history)
    candidate = asyncio.run(_get_candidate(candidate_id))
    assert candidate is not None
    assert candidate.max_user_id == "700103"


def test_max_webhook_message_created_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    candidate_id = asyncio.run(_seed_max_candidate("max-user-2"))

    async def _fake_ensure_max_adapter(*, settings=None):
        return None

    monkeypatch.setattr(
        "backend.apps.admin_api.max_webhook.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    payload = {
        "update_type": "message_created",
        "timestamp": 2,
        "message": {
            "sender": {"user_id": "max-user-2", "username": "candidate_max"},
            "body": {"mid": "mid-1", "text": "Добрый день"},
        },
    }
    headers = {"X-Max-Bot-Api-Secret": "test-max-secret"}

    first = max_webhook_client.post("/api/max/webhook", headers=headers, json=payload)
    second = max_webhook_client.post("/api/max/webhook", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    history = asyncio.run(_chat_messages(candidate_id))
    assert len(history) == 1
    assert history[0].direction == "inbound"
    assert history[0].channel == "max"


def test_max_webhook_manual_time_callback_marks_request(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    candidate_id = asyncio.run(_seed_max_candidate("max-user-3"))
    adapter = _FakeMaxAdapter()

    async def _fake_ensure_max_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr(
        "backend.apps.admin_api.max_webhook.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    response = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_callback",
            "timestamp": 3,
            "user": {"user_id": "max-user-3"},
            "callback": {"callback_id": "cb-1", "payload": "booking:manual_time"},
        },
    )

    assert response.status_code == 200
    candidate = asyncio.run(_get_candidate(candidate_id))
    assert candidate is not None
    assert candidate.manual_slot_requested_at is not None
    assert adapter.answers == ["cb-1"]
    history = asyncio.run(_chat_messages(candidate_id))
    assert len(history) == 1
    assert history[0].direction == "outbound"
    assert history[0].channel == "max"
