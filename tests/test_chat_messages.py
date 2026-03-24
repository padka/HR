import pytest
from types import SimpleNamespace
from sqlalchemy import select

import backend.core.messenger.registry as registry_mod
from backend.core.db import async_session
from backend.core.messenger.protocol import MessengerPlatform, MessengerProtocol, SendResult
from backend.core.messenger.registry import MessengerRegistry
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import ChatMessage
from backend.apps.admin_ui.services import chat as chat_service


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

    async def send_message(self, chat_id, text, *, buttons=None, parse_mode=None, correlation_id=None) -> SendResult:
        self.calls.append((chat_id, text, correlation_id))
        return SendResult(success=True, message_id="mx-1")


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
async def test_send_chat_message_routes_to_max_candidate():
    old_registry = registry_mod._registry
    registry = MessengerRegistry()
    max_adapter = _DummyMaxAdapter()
    registry.register(max_adapter)
    registry_mod._registry = registry
    try:
        candidate = await candidate_services.create_or_update_user(
            telegram_id=None,
            fio="MAX Candidate",
            city="Москва",
        )
        async with async_session() as session:
            stored = await session.get(type(candidate), candidate.id)
            stored.max_user_id = "mx-user-1"
            stored.messenger_platform = "max"
            await session.commit()

        bot = _DummyBotService(ok=True)
        result = await chat_service.send_chat_message(
            candidate.id,
            text="Сообщение через MAX",
            client_request_id="req-max-1",
            author_label="admin",
            bot_service=bot,
        )

        assert bot.calls == []
        assert max_adapter.calls == [("mx-user-1", "Сообщение через MAX", f"candidate-chat:{candidate.id}")]
        assert result["status"] == "sent"
        assert result["message"]["channel"] == "max"

        async with async_session() as session:
            stored_message = await session.get(ChatMessage, result["message"]["id"])
            assert stored_message is not None
            assert stored_message.channel == "max"
            assert stored_message.status == "sent"
            assert stored_message.telegram_user_id is None
    finally:
        registry_mod._registry = old_registry
