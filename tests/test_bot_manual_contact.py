import pytest

pytest.importorskip("aiogram")

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select

from backend.apps.bot import services
from backend.apps.bot.config import DEFAULT_TZ, State
from backend.apps.bot.state_store import InMemoryStateStore, StateManager
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User as CandidateUser
from backend.domain.candidates.status import CandidateStatus

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
        )
        city.recruiters.append(recruiter)
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
    args = call.args
    kwargs = call.kwargs
    markup = kwargs.get("reply_markup")
    assert markup is not None, "expected ForceReply prompt"
    assert getattr(markup, "force_reply", False) is True
    text = kwargs.get("text")
    if text is None and len(args) >= 2:
        text = args[1]
    assert text and "Свободных слотов" in text

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
        )
        city.recruiters.append(recruiter)
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

    second = await services.send_manual_scheduling_prompt(USER_ID)
    assert second is False
    assert dummy_bot.send_message.await_count == 1

    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_manual_availability_response_records_window(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace(
        send_message=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )

    monkeypatch.setattr(services, "_bot", dummy_bot)
    monkeypatch.setattr(services, "_state_manager", manager)

    async with async_session() as session:
        user = CandidateUser(
            telegram_id=USER_ID,
            username="tester",
            fio="Тест Тестов",
            city="Москва",
            last_activity=datetime.now(timezone.utc),
            is_active=True,
        )
        session.add(user)
        await session.commit()

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            manual_availability_expected=True,
            candidate_tz=DEFAULT_TZ,
        ),
    )

    handled = await services.record_manual_availability_response(USER_ID, "25.12 12:00-14:00")
    assert handled is True
    assert dummy_bot.send_message.await_count == 1

    async with async_session() as session:
        db_user = await session.scalar(select(CandidateUser).where(CandidateUser.telegram_id == USER_ID))
        assert db_user.manual_slot_from is not None
        assert db_user.manual_slot_to is not None
        assert db_user.manual_slot_comment.startswith("25.12")

    state = await manager.get(USER_ID)
    assert state.get("manual_availability_expected") is False

    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_manual_availability_response_stores_note_when_unparsed(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace(
        send_message=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )

    monkeypatch.setattr(services, "_bot", dummy_bot)
    monkeypatch.setattr(services, "_state_manager", manager)

    async with async_session() as session:
        user = CandidateUser(
            telegram_id=USER_ID,
            username="tester",
            fio="Тест Тестов",
            city="Москва",
            last_activity=datetime.now(timezone.utc),
            is_active=True,
        )
        session.add(user)
        await session.commit()

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            manual_availability_expected=True,
            candidate_tz=DEFAULT_TZ,
        ),
    )

    message = "После 18:00 в любой будний день"
    handled = await services.record_manual_availability_response(USER_ID, message)
    assert handled is True

    async with async_session() as session:
        db_user = await session.scalar(select(CandidateUser).where(CandidateUser.telegram_id == USER_ID))
        assert db_user.manual_slot_from is None
        assert db_user.manual_slot_to is None
        assert db_user.manual_slot_comment == message

    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_manual_availability_sets_waiting_status(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace(
        send_message=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )

    monkeypatch.setattr(services, "_bot", dummy_bot)
    monkeypatch.setattr(services, "_state_manager", manager)

    async with async_session() as session:
        user = CandidateUser(
            telegram_id=USER_ID,
            username="tester",
            fio="Тест Тестов",
            city="Москва",
            candidate_status=CandidateStatus.TEST1_COMPLETED,
            last_activity=datetime.now(timezone.utc),
            is_active=True,
        )
        session.add(user)
        await session.commit()

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            manual_availability_expected=True,
            candidate_tz=DEFAULT_TZ,
        ),
    )

    await services.record_manual_availability_response(USER_ID, "01.08 10:00-12:00")

    async with async_session() as session:
        db_user = await session.scalar(select(CandidateUser).where(CandidateUser.telegram_id == USER_ID))
        assert db_user.candidate_status == CandidateStatus.WAITING_SLOT

    await manager.clear()
    await manager.close()
