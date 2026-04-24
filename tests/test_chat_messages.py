from types import SimpleNamespace

import pytest
from backend.apps.admin_ui.services import chat as chat_service
from backend.core.db import async_session
from backend.core.messenger.protocol import (
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)
from backend.core.messenger.registry import MessengerRegistry
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import ChatMessage
from sqlalchemy import select


class _DummyBotService:
    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.calls = []

    async def send_chat_message(self, telegram_id: int, text: str, reply_markup=None):
        self.calls.append((telegram_id, text))
        if self.ok:
            return SimpleNamespace(
                ok=True,
                status="sent",
                error=None,
                message=None,
                telegram_message_id=4242,
            )
        return SimpleNamespace(
            ok=False,
            status="failed",
            error="error",
            message=None,
            telegram_message_id=None,
        )


class _DummyMaxAdapter(MessengerProtocol):
    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self.calls = []

    async def configure(self, **kwargs):
        return None

    async def send_message(self, chat_id, text, *, buttons=None, parse_mode=None, correlation_id=None):
        self.calls.append((chat_id, text, buttons, parse_mode, correlation_id))
        return SendResult(success=True, message_id="max-msg-1")


@pytest.fixture(autouse=True)
def clean_chat_rate_limits():
    chat_service._clear_rate_limit_state()
    yield
    chat_service._clear_rate_limit_state()


@pytest.mark.asyncio
async def test_log_inbound_chat_message_creates_history_record():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=123456,
        fio="Интеграционный",
        city="Москва",
    )

    await candidate_services.log_inbound_chat_message(
        candidate.telegram_id,
        text="Привет!",
        telegram_message_id=999,
        payload={"type": "text"},
    )

    async with async_session() as session:
        rows = await session.execute(select(ChatMessage))
        messages = rows.scalars().all()
        assert len(messages) == 1
        message = messages[0]
        assert message.direction == "inbound"
        assert message.text == "Привет!"
        assert message.telegram_message_id == 999
        assert message.status == "received"


@pytest.mark.asyncio
async def test_log_outbound_chat_message_creates_history_record():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777001,
        fio="Бот Исходящий",
        city="Москва",
    )

    await candidate_services.log_outbound_chat_message(
        candidate.telegram_id,
        text="Ваше интервью подтверждено",
        telegram_message_id=111,
        payload={"source": "bot"},
        author_label="bot",
    )

    async with async_session() as session:
        rows = await session.execute(select(ChatMessage).order_by(ChatMessage.id.asc()))
        messages = rows.scalars().all()
        assert len(messages) == 1
        message = messages[0]
        assert message.direction == "outbound"
        assert message.text == "Ваше интервью подтверждено"
        assert message.telegram_message_id == 111
        assert message.status == "sent"
        assert message.author_label == "bot"


@pytest.mark.asyncio
async def test_send_chat_message_updates_status_and_persists():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=654321,
        fio="Исходящий",
        city="Санкт-Петербург",
    )
    bot = _DummyBotService(ok=True)

    result = await chat_service.send_chat_message(
        candidate.id,
        text="Добрый день!",
        client_request_id="req-1",
        author_label="admin",
        bot_service=bot,
    )

    assert bot.calls == [(candidate.telegram_id, "Добрый день!")]
    assert "message" in result
    message_id = result["message"]["id"]

    async with async_session() as session:
        stored = await session.get(ChatMessage, message_id)
        assert stored is not None
        assert stored.status == "sent"
        assert stored.direction == "outbound"
        assert stored.author_label == "admin"


@pytest.mark.asyncio
async def test_duplicate_client_request_id_returns_existing_message_even_when_limit_reached():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=654322,
        fio="Дубликат",
        city="Санкт-Петербург",
    )
    bot = _DummyBotService(ok=True)

    first = await chat_service.send_chat_message(
        candidate.id,
        text="Повторяемое сообщение",
        client_request_id="req-duplicate",
        author_label="admin",
        bot_service=bot,
    )
    assert first["status"] == "sent"

    for _ in range(chat_service.CHAT_RATE_LIMIT_PER_HOUR):
        chat_service._record_message_sent(candidate.id)

    duplicate = await chat_service.send_chat_message(
        candidate.id,
        text="Повторяемое сообщение",
        client_request_id="req-duplicate",
        author_label="admin",
        bot_service=bot,
    )

    assert duplicate["status"] == "duplicate"
    assert duplicate["message"]["id"] == first["message"]["id"]
    assert bot.calls == [(candidate.telegram_id, "Повторяемое сообщение")]


@pytest.mark.asyncio
async def test_retry_chat_message_success_counts_against_rate_limit():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=654323,
        fio="Повторная отправка",
        city="Санкт-Петербург",
    )
    bot = _DummyBotService(ok=True)

    async with async_session() as session:
        message = ChatMessage(
            candidate_id=candidate.id,
            telegram_user_id=candidate.telegram_id,
            direction="outbound",
            channel="telegram",
            text="Нужно отправить повторно",
            status="failed",
            author_label="admin",
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        message_id = message.id

    before_allowed, before_remaining = chat_service._check_rate_limit(candidate.id)
    assert before_allowed is True
    assert before_remaining == chat_service.CHAT_RATE_LIMIT_PER_HOUR

    retried = await chat_service.retry_chat_message(
        candidate.id,
        message_id,
        bot_service=bot,
    )
    assert retried["status"] == "sent"

    after_allowed, after_remaining = chat_service._check_rate_limit(candidate.id)
    assert after_allowed is True
    assert after_remaining == chat_service.CHAT_RATE_LIMIT_PER_HOUR - 1


@pytest.mark.asyncio
async def test_send_chat_message_falls_back_to_web_inbox_without_messenger_binding():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=None,
        fio="Web Inbox Candidate",
        city="Москва",
    )

    bot = _DummyBotService(ok=True)
    result = await chat_service.send_chat_message(
        candidate.id,
        text="Сообщение только в веб-кабинет",
        client_request_id="req-web-1",
        author_label="admin",
        bot_service=bot,
    )

    assert bot.calls == []
    assert result["status"] == "sent"
    assert result["message"]["channel"] == "web"
    assert result["message"]["origin_channel"] == "crm"
    assert result["message"]["delivery_channels"] == ["web"]
    assert result["message"]["author_role"] == "recruiter"

    async with async_session() as session:
        stored_message = await session.get(ChatMessage, result["message"]["id"])
        assert stored_message is not None
        assert stored_message.channel == "web"
        assert stored_message.status == "sent"
        assert stored_message.telegram_user_id is None


@pytest.mark.asyncio
async def test_send_chat_message_prefers_max_channel_when_candidate_is_max_linked(monkeypatch: pytest.MonkeyPatch):
    import backend.core.messenger.registry as registry_module

    previous_registry = registry_module._registry
    registry_module._registry = MessengerRegistry()
    adapter = _DummyMaxAdapter()
    registry_module._registry.register(adapter)

    try:
        async with async_session() as session:
            candidate = await candidate_services.create_or_update_user(
                telegram_id=700001,
                fio="MAX Linked Candidate",
                city="Москва",
            )
            db_candidate = await session.get(type(candidate), candidate.id)
            if db_candidate is not None:
                db_candidate.max_user_id = "max-user-42"
                db_candidate.messenger_platform = "max"
                await session.commit()

        candidate = await candidate_services.get_user_by_candidate_id(candidate.candidate_id)
        assert candidate is not None

        bot = _DummyBotService(ok=True)
        result = await chat_service.send_chat_message(
            candidate.id,
            text="Сообщение в MAX",
            client_request_id="req-max-1",
            author_label="admin",
            bot_service=bot,
        )

        assert bot.calls == []
        assert adapter.calls
        assert adapter.calls[0][0] == "max-user-42"
        assert result["status"] == "sent"
        assert result["message"]["channel"] == "max"
        assert result["message"]["provider_message_id"] == "max-msg-1"
    finally:
        registry_module._registry = previous_registry


@pytest.mark.asyncio
async def test_send_chat_message_bootstraps_max_adapter_when_registry_is_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.core.messenger.registry as registry_module

    previous_registry = registry_module._registry
    registry_module._registry = MessengerRegistry()
    adapter = _DummyMaxAdapter()

    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        registry_module._registry.register(adapter)
        return adapter

    monkeypatch.setattr(chat_service, "ensure_max_adapter", _fake_ensure_max_adapter)

    try:
        async with async_session() as session:
            candidate = await candidate_services.create_or_update_user(
                telegram_id=700002,
                fio="MAX Bootstrapped Candidate",
                city="Москва",
            )
            db_candidate = await session.get(type(candidate), candidate.id)
            if db_candidate is not None:
                db_candidate.max_user_id = "max-user-43"
                db_candidate.messenger_platform = "max"
                await session.commit()

        candidate = await candidate_services.get_user_by_candidate_id(candidate.candidate_id)
        assert candidate is not None

        bot = _DummyBotService(ok=True)
        result = await chat_service.send_chat_message(
            candidate.id,
            text="Сообщение в MAX после lazy bootstrap",
            client_request_id="req-max-lazy-1",
            author_label="admin",
            bot_service=bot,
        )

        assert bot.calls == []
        assert adapter.calls
        assert adapter.calls[0][0] == "max-user-43"
        assert result["status"] == "sent"
        assert result["message"]["channel"] == "max"
    finally:
        registry_module._registry = previous_registry
