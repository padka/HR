import pytest

pytest.importorskip("aiogram")

from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.apps.bot import services
from backend.apps.bot.config import DEFAULT_TZ, State
from backend.apps.bot.state_store import InMemoryStateStore, StateManager
from backend.core.db import async_session
from backend.domain import models

USER_ID = 987654


@pytest.mark.asyncio
async def test_manual_contact_links_responsible_recruiter(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace(
        send_message=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )

    monkeypatch.setattr(services, "_bot", dummy_bot)
    monkeypatch.setattr(services, "_state_manager", manager)

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Анна Рекрутер",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=123456789,
        )
        session.add(recruiter)
        await session.flush()
        city = models.City(
            name="Тестоград",
            tz="Europe/Moscow",
            active=True,
            responsible_recruiter_id=recruiter.id,
        )
        session.add(city)
        await session.commit()
        city_id = city.id

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            city_id=city_id,
            candidate_tz=DEFAULT_TZ,
        ),
    )

    first = await services.send_manual_scheduling_prompt(USER_ID)
    assert first is True
    assert dummy_bot.send_message.await_count == 1

    call = dummy_bot.send_message.await_args_list[0]
    kwargs = call.kwargs
    markup = kwargs.get("reply_markup")
    assert markup is not None, "expected contact link for responsible recruiter"
    button = markup.inline_keyboard[0][0]
    assert button.url == "tg://user?id=123456789"
    assert "Анна" in kwargs.get("text", "")

    state = await manager.get(USER_ID)
    assert state.get("manual_contact_prompt_sent") is True

    second = await services.send_manual_scheduling_prompt(USER_ID)
    assert second is False
    assert dummy_bot.send_message.await_count == 1

    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_manual_contact_without_responsible_link(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace(
        send_message=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )

    monkeypatch.setattr(services, "_bot", dummy_bot)
    monkeypatch.setattr(services, "_state_manager", manager)

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Без Чата",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=None,
        )
        session.add(recruiter)
        await session.flush()
        city = models.City(
            name="Нетлинк",
            tz="Europe/Moscow",
            active=True,
            responsible_recruiter_id=recruiter.id,
        )
        session.add(city)
        await session.commit()
        city_id = city.id

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            city_id=city_id,
            candidate_tz=DEFAULT_TZ,
        ),
    )

    first = await services.send_manual_scheduling_prompt(USER_ID)
    assert first is True

    call = dummy_bot.send_message.await_args_list[0]
    kwargs = call.kwargs
    markup = kwargs.get("reply_markup")
    assert markup is None, "no link expected when recruiter chat is missing"

    second = await services.send_manual_scheduling_prompt(USER_ID)
    assert second is False
    assert dummy_bot.send_message.await_count == 1

    await manager.clear()
    await manager.close()
