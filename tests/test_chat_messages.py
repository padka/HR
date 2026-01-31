import pytest
from types import SimpleNamespace
from sqlalchemy import select

from backend.core.db import async_session
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
