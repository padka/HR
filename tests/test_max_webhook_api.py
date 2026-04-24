from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from backend.apps.admin_api.max_webhook import (
    _contextual_welcome_buttons,
    _stable_client_request_id,
)
from backend.core.db import async_session
from backend.core.messenger.protocol import (
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    ChatMessage,
    User,
)
from backend.domain.candidates.status import CandidateStatus
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


async def _seed_max_candidate(
    max_user_id: str = "max-user-1",
    *,
    candidate_status: CandidateStatus | None = None,
) -> int:
    async with async_session() as session:
        candidate = User(
            fio="MAX Candidate",
            city="Москва",
            source="max",
            messenger_platform="max",
            max_user_id=max_user_id,
            candidate_status=candidate_status,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return candidate.id


async def _get_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


async def _get_candidate_by_max_user_id(max_user_id: str) -> User | None:
    async with async_session() as session:
        return await session.scalar(select(User).where(User.max_user_id == max_user_id).limit(1))


async def _count_chat_sessions(max_user_id: str) -> int:
    async with async_session() as session:
        return int(
            await session.scalar(
                select(func.count(CandidateAccessSession.id)).where(
                    CandidateAccessSession.provider_user_id == max_user_id,
                    CandidateAccessSession.journey_surface == CandidateJourneySurface.MAX_CHAT.value,
                )
            )
            or 0
        )


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


def test_max_webhook_client_request_id_fits_db_limit():
    request_id = _stable_client_request_id(
        "manual-prompt",
        "aa3a7fdeeebdab697d924dc2c797a9ba7337c9d03fe57412-extra-suffix",
    )

    assert len(request_id) <= 64


def test_max_webhook_contextual_buttons_require_real_start_param():
    from types import SimpleNamespace

    buttons = _contextual_welcome_buttons(
        settings=SimpleNamespace(max_miniapp_url="https://example.test/max"),
        start_param=None,
    )

    assert buttons == []


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
    monkeypatch.setattr(
        "backend.apps.admin_api.max_candidate_chat.ensure_max_adapter",
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
    assert "Тестирование и запись на слот проходят только в mini app внутри MAX." in str(adapter.messages[0]["text"])
    assert "Сообщения от RecruitSmart, напоминания и детали встречи будут приходить в этот чат" in str(adapter.messages[0]["text"])
    assert adapter.messages[0]["buttons"] == []
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
    assert "Добро пожаловать в RecruitSmart." in str(adapter.messages[0]["text"])
    assert "Тестирование и запись на слот проходят только в mini app внутри MAX." in str(adapter.messages[0]["text"])
    assert adapter.messages[0]["buttons"] == []


def test_max_webhook_global_bot_started_bootstraps_chat_flow_when_rollout_enabled(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
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

    response = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "bot_started",
            "timestamp": 1,
            "chat_id": "chat-global-start",
            "user": {"user_id": 700104, "username": "global_max", "name": "Global User"},
        },
    )

    assert response.status_code == 200
    assert response.json()["handled"] is True
    assert adapter.messages
    assert "Тестирование и запись на слот проходят только в mini app внутри MAX." in str(adapter.messages[0]["text"])
    assert adapter.messages[0]["buttons"] == []
    candidate = asyncio.run(_get_candidate_by_max_user_id("700104"))
    assert candidate is not None
    assert candidate.fio == "Global User"
    assert asyncio.run(_count_chat_sessions("700104")) == 1
    history = asyncio.run(_chat_messages(candidate.id))
    assert len(history) == 1
    assert history[0].direction == "outbound"
    assert history[0].channel == "max"


def test_max_webhook_repeated_bot_started_with_new_timestamp_repeats_welcome(
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
    monkeypatch.setattr(
        "backend.apps.admin_api.max_candidate_chat.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    first = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "bot_started",
            "timestamp": 100,
            "chat_id": "chat-repeat-1",
            "user": {"user_id": 700199, "username": "repeat_max", "name": "Repeat User"},
            "payload": "max-start-ref",
        },
    )
    second = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "bot_started",
            "timestamp": 101,
            "chat_id": "chat-repeat-1",
            "user": {"user_id": 700199, "username": "repeat_max", "name": "Repeat User"},
            "payload": "max-start-ref",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["duplicate"] is False
    assert len(adapter.messages) == 2
    assert "Тестирование и запись на слот проходят только в mini app внутри MAX." in str(adapter.messages[0]["text"])
    assert "Тестирование и запись на слот проходят только в mini app внутри MAX." in str(adapter.messages[1]["text"])
    history = asyncio.run(_chat_messages(candidate_id))
    assert len(history) == 2


def test_max_webhook_global_bot_started_reissues_welcome_for_bound_non_self_serve_candidate(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    asyncio.run(_seed_max_candidate("700106"))
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
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

    response = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "bot_started",
            "timestamp": 1,
            "chat_id": "chat-bound-no-self-serve",
            "user": {"user_id": 700106, "username": "bound_max", "name": "Bound User"},
        },
    )

    assert response.status_code == 200
    assert response.json()["handled"] is True
    assert adapter.messages
    assert "Тестирование и запись на слот проходят только в mini app внутри MAX." in str(adapter.messages[0]["text"])
    candidate = asyncio.run(_get_candidate_by_max_user_id("700106"))
    assert candidate is not None
    history = asyncio.run(_chat_messages(candidate.id))
    assert len(history) == 1


def test_max_webhook_entry_start_chat_can_bootstrap_global_flow_without_existing_candidate(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
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

    callback = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_callback",
            "timestamp": 2,
            "user": {"user_id": "700105", "username": "global_callback", "name": "Callback User"},
            "callback": {
                "callback_id": "cb-global-start",
                "payload": "entry:start_chat",
            },
        },
    )

    assert callback.status_code == 200
    assert adapter.answers[-1] == "cb-global-start"
    assert adapter.messages
    assert "Тестирование и запись на слот проходят только в mini app внутри MAX." in str(adapter.messages[0]["text"])


def test_max_webhook_entry_start_chat_accepts_callback_aliases_and_dialog_user(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    monkeypatch.setenv("MAX_INVITE_ROLLOUT_ENABLED", "1")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
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

    callback = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_callback",
            "timestamp": 2,
            "message": {
                "sender": {"user_id": "900001", "username": "recruitsmart_bot"},
                "recipient": {
                    "chat_id": "chat-dialog-700107",
                    "dialog_with_user": {
                        "user_id": "700107",
                        "username": "dialog_callback",
                        "name": "Dialog Callback User",
                    },
                },
            },
            "callback": {
                "id": "cb-global-start-alias",
                "data": "entry:start_chat",
            },
        },
    )

    assert callback.status_code == 200
    assert adapter.answers[-1] == "cb-global-start-alias"
    assert adapter.messages
    assert "Откройте mini app через системную кнопку приложения" in str(adapter.messages[0]["text"])


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
    assert "Тестирование и запись на слот проходят только в mini app внутри MAX." in str(adapter.messages[0]["text"])
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


def test_max_webhook_manual_time_message_accepts_single_time_phrase(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    candidate_id = asyncio.run(
        _seed_max_candidate(
            "max-user-manual-single",
            candidate_status=CandidateStatus.TEST1_COMPLETED,
        )
    )
    adapter = _FakeMaxAdapter()

    async def _fake_ensure_max_adapter(*, settings=None):
        return adapter

    async def _fake_notify_recruiters_manual_availability(**kwargs):
        return True

    monkeypatch.setattr(
        "backend.apps.admin_api.max_webhook.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )
    monkeypatch.setattr(
        "backend.apps.admin_api.max_webhook.notify_recruiters_manual_availability",
        _fake_notify_recruiters_manual_availability,
    )

    request_manual = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_callback",
            "timestamp": 30,
            "user": {"user_id": "max-user-manual-single"},
            "callback": {"callback_id": "cb-manual-single", "payload": "booking:manual_time"},
        },
    )
    assert request_manual.status_code == 200

    adapter.messages.clear()
    response = max_webhook_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_created",
            "timestamp": 31,
            "message": {
                "sender": {"user_id": "max-user-manual-single", "username": "candidate_max"},
                "body": {"mid": "mid-manual-single", "text": "Завтра в 17:00"},
            },
        },
    )

    assert response.status_code == 200
    candidate = asyncio.run(_get_candidate(candidate_id))
    assert candidate is not None
    assert candidate.manual_slot_response_at is not None
    assert candidate.manual_slot_from is not None
    assert candidate.manual_slot_to is not None
    assert candidate.manual_slot_to > candidate.manual_slot_from
    assert adapter.messages
    assert "Спасибо. Передал рекрутеру ваше удобное время." in str(adapter.messages[-1]["text"])


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


def test_max_webhook_manual_time_callback_accepts_dialog_user_without_top_level_user(
    monkeypatch: pytest.MonkeyPatch,
    max_webhook_client,
):
    candidate_id = asyncio.run(_seed_max_candidate("max-user-4"))
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
            "timestamp": 4,
            "message": {
                "sender": {"user_id": "900001", "username": "recruitsmart_bot"},
                "recipient": {
                    "chat_id": "chat-dialog-max-user-4",
                    "dialog_with_user": {
                        "user_id": "max-user-4",
                        "username": "candidate_max_4",
                        "name": "MAX Candidate",
                    },
                },
            },
            "callback": {"id": "cb-4", "data": "booking:manual_time"},
        },
    )

    assert response.status_code == 200
    candidate = asyncio.run(_get_candidate(candidate_id))
    assert candidate is not None
    assert candidate.manual_slot_requested_at is not None
    assert adapter.answers == ["cb-4"]
