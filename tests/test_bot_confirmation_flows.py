import pytest
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, func

from backend.apps.bot import services
from backend.apps.bot.events import InterviewSuccessEvent
from backend.apps.bot.handlers import interview
from backend.apps.bot.services import (
    NotificationService,
    configure,
    configure_notification_service,
    get_notification_service,
    handle_attendance_yes,
    handle_approve_slot,
)
from backend.apps.bot.state_store import InMemoryStateStore, StateManager
from backend.core.db import async_session
from backend.domain import models
from backend.domain.models import (
    SlotStatus,
    NotificationLog,
    OutboxNotification,
    TelegramCallbackLog,
    MessageTemplate,
    BotMessageLog,
)
from backend.domain.repositories import add_notification_log, add_outbox_notification


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
async def test_dispatch_interview_success_sends_message_and_logs():
    store = InMemoryStateStore(ttl_seconds=120)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    dummy_bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=777))
    configure(dummy_bot, manager)

    event = InterviewSuccessEvent(
        candidate_id=987654,
        candidate_name="Иван Тестов",
        candidate_tz="Europe/Moscow",
        city_id=123,
        city_name="Москва",
        slot_id=555,
        required=True,
    )

    await services.dispatch_interview_success(event)

    assert dummy_bot.send_message.await_count == 1
    args, kwargs = dummy_bot.send_message.await_args
    assert args[0] == event.candidate_id
    assert "Поздравляем" in args[1]
    markup = kwargs.get("reply_markup")
    assert markup is not None
    assert markup.inline_keyboard[0][0].callback_data == "test2:start"

    async with async_session() as session:
        log_entry = await session.scalar(
            select(BotMessageLog)
            .where(BotMessageLog.candidate_tg_id == event.candidate_id)
            .order_by(BotMessageLog.id.desc())
        )
        assert log_entry is not None
        assert log_entry.message_type == "test2_invite"
        payload = log_entry.payload_json or {}
        assert payload.get("status") == "sent"
        assert payload.get("message_id") == 777
        assert payload.get("city_id") == event.city_id

    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_dispatch_interview_success_logs_and_raises_on_failure():
    store = InMemoryStateStore(ttl_seconds=120)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    error = TelegramBadRequest(method="sendMessage", message="bad request")
    dummy_bot.send_message = AsyncMock(side_effect=error)
    configure(dummy_bot, manager)

    event = InterviewSuccessEvent(
        candidate_id=24680,
        candidate_name="Мария Ошибка",
        candidate_tz="Europe/Moscow",
        city_id=321,
        city_name="Санкт-Петербург",
        slot_id=999,
        required=False,
    )

    with pytest.raises(TelegramBadRequest):
        await services.dispatch_interview_success(event)

    assert dummy_bot.send_message.await_count == 1

    async with async_session() as session:
        log_entry = await session.scalar(
            select(BotMessageLog)
            .where(BotMessageLog.candidate_tg_id == event.candidate_id)
            .order_by(BotMessageLog.id.desc())
        )
        assert log_entry is not None
        payload = log_entry.payload_json or {}
        assert payload.get("status") in {"bad_request", "failed"}
        assert "error" in payload

    await manager.clear()
    await manager.close()


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

    reminder_calls = []

    class _FakeReminderService:
        def __init__(self) -> None:
            self.schedule_for_slot = AsyncMock(side_effect=lambda slot_id: reminder_calls.append(slot_id))

    fake_reminder_service = _FakeReminderService()

    monkeypatch.setattr(
        "backend.apps.bot.services.get_reminder_service",
        lambda: fake_reminder_service,
    )

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
    assert reminder_calls.count(slot_id) == 1

    followup_message = DummyMessage()
    second_cb = DummyApproveCallback("ap-2", slot_id, followup_message, responses)
    await handle_approve_slot(second_cb)
    assert len(send_calls) == 1
    assert responses[-1] == ("Уже согласовано ✔️", False)
    assert reminder_calls.count(slot_id) == 1

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


@pytest.mark.asyncio
async def test_notification_log_overwrite_updates_existing_entry():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Сергей", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=4),
            status=SlotStatus.PENDING,
            candidate_tg_id=777,
            candidate_fio="Дубликат Тестов",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_id = slot.candidate_tg_id

    created = await add_notification_log(
        "candidate_reminder",
        slot_id,
        candidate_tg_id=candidate_id,
        payload="initial",
        delivery_status="pending",
        attempts=1,
        last_error="fail",
        next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    assert created is True

    updated_payload = "updated text"
    overwrite_result = await add_notification_log(
        "candidate_reminder",
        slot_id,
        candidate_tg_id=candidate_id,
        payload=updated_payload,
        delivery_status="sent",
        attempts=3,
        last_error=None,
        next_retry_at=None,
        overwrite=True,
        template_key="reminder",
        template_version=2,
    )
    assert overwrite_result is False

    async with async_session() as session:
        log = await session.scalar(
            select(models.NotificationLog).where(
                models.NotificationLog.booking_id == slot_id,
                models.NotificationLog.type == "candidate_reminder",
                models.NotificationLog.candidate_tg_id == candidate_id,
            )
        )
        assert log is not None
        assert log.payload == updated_payload
        assert log.delivery_status == "sent"
        assert log.attempts == 3
        assert log.last_error is None
        assert log.next_retry_at is None
        assert log.template_key == "reminder"
        assert log.template_version == 2


@pytest.mark.asyncio
async def test_no_duplicate_confirm_messages(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    service = NotificationService(poll_interval=0.05)
    configure_notification_service(service)

    send_calls = []

    async def fake_send(bot, method, correlation_id):
        send_calls.append((method, correlation_id))
        return SimpleNamespace(message_id=1)

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", fake_send)

    async with async_session() as session:
        template_exists = await session.scalar(
            select(MessageTemplate.id).where(
                MessageTemplate.key == "interview_confirmed_candidate",
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        if template_exists is None:
            session.add(
                MessageTemplate(
                    key="interview_confirmed_candidate",
                    locale="ru",
                    channel="tg",
                    body_md="Сообщение для {candidate_name}",
                    version=1,
                    is_active=True,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        recruiter = models.Recruiter(
            name="Дарья",
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
            start_utc=datetime.now(timezone.utc) + timedelta(hours=1),
            status=SlotStatus.PENDING,
            candidate_tg_id=1234,
            candidate_fio="Анастасия",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        await add_outbox_notification(
            notification_type="interview_confirmed_candidate",
            booking_id=slot.id,
            candidate_tg_id=slot.candidate_tg_id,
        )

    worker = get_notification_service()
    await worker._poll_once()
    assert len(send_calls) == 1

    async with async_session() as session:
        await add_outbox_notification(
            notification_type="interview_confirmed_candidate",
            booking_id=slot.id,
            candidate_tg_id=slot.candidate_tg_id,
            session=session,
        )
        await session.commit()

    await worker._poll_once()
    assert len(send_calls) == 1

    async with async_session() as session:
        log_entry = await session.scalar(
            select(NotificationLog).where(
                NotificationLog.booking_id == slot.id,
                NotificationLog.type == "candidate_interview_confirmed",
            )
        )
        assert log_entry is not None
        assert log_entry.delivery_status == "sent"

    await service.shutdown()
    await manager.clear()
    await manager.close()
    import backend.apps.bot.services as bot_services

    bot_services._notification_service = None


@pytest.mark.asyncio
async def test_handle_pick_slot_sends_local_summary(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace(
        send_message=AsyncMock(),
        send_document=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )

    monkeypatch.setattr(services, "_bot", dummy_bot)
    monkeypatch.setattr(services, "_state_manager", manager)
    monkeypatch.setattr(services.templates, "tpl", AsyncMock(return_value="Заявка отправлена"))

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Рекрутёр",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=777000,
        )
        city = models.City(name="Новосибирск", tz="Asia/Novosibirsk", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime(2030, 1, 1, 6, 0, tzinfo=timezone.utc),
            status=models.SlotStatus.FREE,
            tz_name=city.tz,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    candidate_id = 987123
    await manager.set(
        candidate_id,
        {
            "flow": "interview",
            "city_id": city.id,
            "city_name": city.name_plain,
            "candidate_tz": "Europe/Moscow",
            "fio": "Иван Тест",
        },
    )

    responses: list[Tuple[Optional[str], bool]] = []
    message = DummyMessage()

    class SlotCallback:
        def __init__(self) -> None:
            self.data = f"pick_slot:{recruiter.id}:{slot_id}"
            self.from_user = SimpleNamespace(id=candidate_id)
            self.message = message

        async def answer(self, text: Optional[str] = None, show_alert: bool = False) -> None:
            responses.append((text, show_alert))

    callback = SlotCallback()

    await services.handle_pick_slot(callback)

    candidate_calls = [
        call for call in dummy_bot.send_message.await_args_list if call.args and call.args[0] == candidate_id
    ]
    assert candidate_calls, "expected candidate notification"
    summary_text = candidate_calls[-1].args[1]
    assert summary_text == "Ваше время: 09:00 (по местному времени города Новосибирск — 13:00)"

    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_outbox_exactly_once(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    service = NotificationService(poll_interval=0.1)
    configure_notification_service(service)

    send_calls = []

    async def fake_send(bot, method, correlation_id):
        send_calls.append((method, correlation_id))
        return SimpleNamespace(message_id=1)

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", fake_send)

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Ирина",
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
            status=SlotStatus.PENDING,
            candidate_tg_id=4321,
            candidate_fio="Антон Антонов",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        existing_template = await session.scalar(
            select(MessageTemplate.id).where(
                MessageTemplate.key == "interview_confirmed_candidate",
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        if existing_template is None:
            session.add(
                MessageTemplate(
                    key="interview_confirmed_candidate",
                    locale="ru",
                    channel="tg",
                    body_md="{candidate_name}",
                    version=1,
                    is_active=True,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        await add_outbox_notification(
            notification_type="interview_confirmed_candidate",
            booking_id=slot.id,
            candidate_tg_id=slot.candidate_tg_id,
        )

    worker = get_notification_service()
    await worker._poll_once()
    await worker._poll_once()

    assert len(send_calls) == 1

    async with async_session() as session:
        log_row = await session.scalar(
            select(NotificationLog)
            .where(NotificationLog.booking_id == slot.id)
            .where(NotificationLog.type == "candidate_interview_confirmed")
        )
        assert log_row is not None
        assert log_row.delivery_status == "sent"
        assert log_row.template_key == "interview_confirmed_candidate"

        outbox_row = await session.scalar(
            select(OutboxNotification).where(OutboxNotification.booking_id == slot.id)
        )
        assert outbox_row is not None
        assert outbox_row.status == "sent"

    await service.shutdown()
    await manager.clear()
    await manager.close()
    import backend.apps.bot.services as bot_services

    bot_services._notification_service = None
