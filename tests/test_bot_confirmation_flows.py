import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select, func

from backend.apps.bot.services import (
    configure,
    handle_attendance_yes,
    handle_approve_slot,
)
from backend.apps.bot.state_store import InMemoryStateStore, StateManager
from backend.core.db import async_session
from backend.domain import models
from backend.domain.models import SlotStatus, NotificationLog, TelegramCallbackLog
from backend.domain.repositories import add_notification_log


class DummyMessage:
    def __init__(self) -> None:
        self.edit_text = AsyncMock()
        self.edit_reply_markup = AsyncMock()
        self.document = None
        self.photo = None
        self.video = None
        self.animation = None


class DummyCallback:
    def __init__(self, cb_id: str, slot_id: int, message: DummyMessage, responses):
        self.id = cb_id
        self.data = f"att_yes:{slot_id}"
        self.from_user = SimpleNamespace(id=0)
        self.message = message
        self._responses = responses

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self._responses.append((text, show_alert))


class DummyApproveCallback:
    def __init__(self, cb_id: str, slot_id: int, message: DummyMessage, responses):
        self.id = cb_id
        self.data = f"approve:{slot_id}"
        self.from_user = SimpleNamespace(id=0)
        self.message = message
        self._responses = responses

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self._responses.append((text, show_alert))


@pytest.mark.asyncio
async def test_candidate_confirmation_idempotent(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Анна",
            tz="Europe/Moscow",
            telemost_url="https://telemost.example",
            active=True,
        )
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=3),
            status=SlotStatus.BOOKED,
            candidate_tg_id=12345,
            candidate_fio="Иван Иванов",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_id = slot.candidate_tg_id

    send_calls = []

    async def fake_send(bot, method, correlation_id):
        send_calls.append((method, correlation_id))
        return SimpleNamespace(message_id=1)

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", fake_send)

    responses = []
    message = DummyMessage()
    callback = DummyCallback("cb-1", slot_id, message, responses)
    callback.from_user.id = 12345

    await handle_attendance_yes(callback)

    assert send_calls, "message must be sent on first confirmation"
    sent_method, correlation_id = send_calls[0]
    assert "attendance:" in correlation_id
    assert "🔗" in sent_method.text

    assert responses[-1] == ("Подтверждено", False)
    message.edit_text.assert_awaited()
    message.edit_reply_markup.assert_awaited()

    async with async_session() as session:
        fresh = await session.get(models.Slot, slot_id)
        assert fresh is not None
        assert fresh.status == SlotStatus.CONFIRMED_BY_CANDIDATE
        logs = (
            await session.execute(
                select(NotificationLog).where(
                    NotificationLog.booking_id == slot_id,
                    NotificationLog.type == "candidate_confirm",
                    NotificationLog.candidate_tg_id == candidate_id,
                )
            )
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].candidate_tg_id == candidate_id
        cb_logs = (
            await session.execute(
                select(TelegramCallbackLog).where(
                    TelegramCallbackLog.callback_id == "cb-1"
                )
            )
        ).scalars().all()
        assert len(cb_logs) == 1

    await handle_attendance_yes(callback)
    assert len(send_calls) == 1
    assert responses[-1] == ("Уже подтверждено", False)

    second_message = DummyMessage()
    second_callback = DummyCallback("cb-2", slot_id, second_message, responses)
    second_callback.from_user.id = 12345
    await handle_attendance_yes(second_callback)
    assert len(send_calls) == 1
    assert responses[-1] == ("Уже подтверждено", False)

    async with async_session() as session:
        logs = (
            await session.execute(
                select(NotificationLog).where(
                    NotificationLog.booking_id == slot_id,
                    NotificationLog.candidate_tg_id == candidate_id,
                )
            )
        ).scalars().all()
        assert len(logs) == 1
        cb_count = await session.scalar(
            select(func.count()).select_from(TelegramCallbackLog)
        )
        assert cb_count == 2

    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_recruiter_approval_message_idempotent(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Мария",
            tz="Europe/Moscow",
            telemost_url="https://telemost.example",
            active=True,
        )
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=4),
            status=SlotStatus.PENDING,
            candidate_tg_id=67890,
            candidate_fio="Пётр Петров",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_id = slot.candidate_tg_id

    send_calls = []

    async def fake_send(bot, method, correlation_id):
        send_calls.append((method, correlation_id))
        return SimpleNamespace(message_id=42)

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", fake_send)

    responses = []
    message = DummyMessage()
    approve_cb = DummyApproveCallback("ap-1", slot_id, message, responses)

    await handle_approve_slot(approve_cb)

    assert send_calls, "approval should trigger candidate notification"
    sent_method, correlation_id = send_calls[0]
    assert "approve:" in correlation_id
    assert "✅" in message.edit_text.await_args[0][0]

    async with async_session() as session:
        fresh = await session.get(models.Slot, slot_id)
        assert fresh is not None
        assert fresh.status == SlotStatus.BOOKED
        logs = (
            await session.execute(
                select(NotificationLog).where(
                    NotificationLog.booking_id == slot_id,
                    NotificationLog.type == "candidate_interview_confirmed",
                    NotificationLog.candidate_tg_id == candidate_id,
                )
            )
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].candidate_tg_id == candidate_id

    assert responses[-1] == ("Сообщение отправлено кандидату.", False)
    assert message.edit_reply_markup.await_count == 1

    followup_message = DummyMessage()
    second_cb = DummyApproveCallback("ap-2", slot_id, followup_message, responses)
    await handle_approve_slot(second_cb)
    assert len(send_calls) == 1
    assert responses[-1] == ("Уже согласовано ✔️", False)

    async with async_session() as session:
        logs = (
            await session.execute(
                select(NotificationLog).where(
                    NotificationLog.booking_id == slot_id,
                    NotificationLog.type == "candidate_interview_confirmed",
                    NotificationLog.candidate_tg_id == candidate_id,
                )
            )
        ).scalars().all()
        assert len(logs) == 1

    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_notification_log_unique_constraint():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Олег", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=5),
            status=SlotStatus.PENDING,
            candidate_tg_id=555,
            candidate_fio="Тест",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_id = slot.candidate_tg_id

    first = await add_notification_log(
        "candidate_confirm", slot_id, candidate_tg_id=candidate_id
    )
    assert first is True
    second = await add_notification_log(
        "candidate_confirm", slot_id, candidate_tg_id=candidate_id
    )
    assert second is False

    async with async_session() as session:
        count = await session.scalar(
            select(func.count()).select_from(NotificationLog).where(
                NotificationLog.booking_id == slot_id,
                NotificationLog.type == "candidate_confirm",
                NotificationLog.candidate_tg_id == candidate_id,
            )
        )
        assert count == 1
