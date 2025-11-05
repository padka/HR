import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramServerError
from aiogram.methods import SendMessage
from sqlalchemy import select, update, func, delete
from sqlalchemy.exc import IntegrityError

from backend.apps.bot.metrics import get_notification_metrics_snapshot
from backend.apps.bot.services import (
    BookingNotificationStatus,
    NotificationService,
    capture_slot_snapshot,
    configure,
    configure_notification_service,
    get_notification_service,
    reset_template_provider,
)
from backend.apps.bot.state_store import InMemoryStateStore, StateManager
from backend.core.db import async_session
from backend.domain import models
from backend.domain.models import (
    MessageTemplate,
    OutboxNotification,
    NotificationLog,
    SlotStatus,
)
from backend.domain.repositories import add_outbox_notification, get_slot


@pytest.mark.asyncio
async def test_retry_with_backoff_and_jitter(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    service = NotificationService(
        poll_interval=0.05,
        retry_base_delay=10,
        retry_max_delay=40,
        rate_limit_per_sec=10,
    )
    configure_notification_service(service)

    async with async_session() as session:
        template = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == "interview_confirmed_candidate",
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        if template is None:
            template = MessageTemplate(
                key="interview_confirmed_candidate",
                locale="ru",
                channel="tg",
                body_md="Шаблон {candidate_name}",
                version=1,
                is_active=True,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
        original_body = template.body_md
        await session.execute(
            update(MessageTemplate)
            .where(MessageTemplate.id == template.id)
            .values(
                body_md="Текст {candidate_name}",
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

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
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            status=SlotStatus.PENDING,
            candidate_tg_id=999,
            candidate_fio="Тест Тестов",
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

    def fake_uniform(low, high):
        return (low + high) / 2

    async def failing_send(bot, method, correlation_id):
        raise TelegramServerError(method=method, message="server error")

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", failing_send)
    monkeypatch.setattr("backend.apps.bot.services.random.uniform", fake_uniform)

    worker = get_notification_service()
    try:
        await worker._poll_once()

        async with async_session() as session:
            outbox = await session.scalar(
                select(OutboxNotification).where(OutboxNotification.booking_id == slot.id)
            )
            assert outbox is not None
            assert outbox.status == "pending"
            assert outbox.attempts == 1
            assert outbox.next_retry_at is not None
            next_retry = outbox.next_retry_at
            if next_retry.tzinfo is None:
                next_retry = next_retry.replace(tzinfo=timezone.utc)
            delay = (next_retry - datetime.now(timezone.utc)).total_seconds()
            assert 8.0 <= delay <= 12.0

            log = await session.scalar(
                select(NotificationLog).where(
                    NotificationLog.booking_id == slot.id,
                    NotificationLog.type == "candidate_interview_confirmed",
                )
            )
            assert log is not None
            assert log.delivery_status == "failed"
            assert log.next_retry_at is not None

        metrics = await get_notification_metrics_snapshot()
        assert metrics.send_retry_total >= 1
        assert metrics.notifications_failed_total.get("interview_confirmed_candidate", 0) >= 1
    finally:
        await service.shutdown()
        await manager.clear()
        await manager.close()
        import backend.apps.bot.services as bot_services

        bot_services._notification_service = None

    async with async_session() as session:
        await session.execute(
            update(MessageTemplate)
            .where(MessageTemplate.key == "interview_confirmed_candidate")
            .where(MessageTemplate.locale == "ru")
            .where(MessageTemplate.channel == "tg")
            .values(body_md=original_body, updated_at=datetime.now(timezone.utc))
        )
        await session.commit()


@pytest.mark.asyncio
async def test_poll_once_handles_duplicate_notification_logs(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    service = NotificationService(poll_interval=0.05, rate_limit_per_sec=10)
    configure_notification_service(service)

    send_calls = []

    async def fake_send(bot, method, correlation_id):
        send_calls.append((method, correlation_id))
        return SimpleNamespace(message_id=777)

    async def fake_render(slot):
        return (
            "Сообщение",
            slot.candidate_tz or "Europe/Moscow",
            "Москва",
            "interview_confirmed_candidate",
            1,
        )

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", fake_send)
    monkeypatch.setattr("backend.apps.bot.services._render_candidate_notification", fake_render)

    import backend.apps.bot.services as bot_services

    original_add_log = bot_services.add_notification_log
    call_state = {"count": 0}

    async def flaky_add_notification_log(*args, **kwargs):
        call_state["count"] += 1
        if call_state["count"] == 1:
            raise IntegrityError("insert notification log", params={}, orig=Exception("duplicate"))
        return await original_add_log(*args, **kwargs)

    monkeypatch.setattr(bot_services, "add_notification_log", flaky_add_notification_log)

    try:
        async with async_session() as session:
            recruiter = models.Recruiter(
                name="Иван",
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
                candidate_tg_id=4242,
                candidate_fio="Повтор Кандидат",
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

        await service._poll_once()

        assert call_state["count"] >= 2
        assert len(send_calls) == 1

        async with async_session() as session:
            log_count = await session.scalar(
                select(func.count())
                .select_from(NotificationLog)
                .where(NotificationLog.booking_id == slot.id)
                .where(NotificationLog.type == "candidate_interview_confirmed")
            )
            assert log_count == 1
            outbox = await session.scalar(
                select(OutboxNotification).where(OutboxNotification.booking_id == slot.id)
            )
            assert outbox is not None
            assert outbox.status == "sent"
    finally:
        await service.shutdown()
        await manager.clear()
        await manager.close()
        import backend.apps.bot.services as cleanup_services

        cleanup_services._notification_service = None


@pytest.mark.asyncio
async def test_candidate_rejection_uses_message_template(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    custom_body = "Кандидат {candidate_name} — индивидуальное сообщение"

    async with async_session() as session:
        await session.execute(
            delete(MessageTemplate).where(
                MessageTemplate.key == "candidate_rejection",
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        session.add(
            MessageTemplate(
                key="candidate_rejection",
                locale="ru",
                channel="tg",
                body_md=custom_body,
                version=1,
                is_active=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    reset_template_provider()

    service = NotificationService(poll_interval=0.05, rate_limit_per_sec=10)
    configure_notification_service(service)

    send_calls: List[SendMessage] = []

    async def capturing_send(bot, method, correlation_id):
        send_calls.append(method)
        return SimpleNamespace(message_id=101)

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", capturing_send)

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

        candidate_name = "Анастасия"
        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=3),
            status=SlotStatus.BOOKED,
            candidate_tg_id=8080,
            candidate_fio=candidate_name,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    slot_obj = await get_slot(slot_id)
    snapshot = await capture_slot_snapshot(slot_obj)

    result = await service.on_booking_status_changed(
        slot_id,
        BookingNotificationStatus.CANCELLED,
        snapshot=snapshot,
    )
    assert result.status == "queued"

    await service._poll_once()

    assert send_calls, "Expected outgoing message to be sent"
    message = send_calls[0]
    assert isinstance(message, SendMessage)
    expected_text = custom_body.replace("{candidate_name}", candidate_name)
    assert message.text == expected_text

    async with async_session() as session:
        log_row = await session.scalar(
            select(NotificationLog).where(
                NotificationLog.booking_id == slot_id,
                NotificationLog.type == "candidate_rejection",
            )
        )
        assert log_row is not None
        assert log_row.template_key == "candidate_rejection"
        assert log_row.template_version == 1

    await service.shutdown()
    await manager.clear()
    await manager.close()
    import backend.apps.bot.services as cleanup_services

    cleanup_services._notification_service = None


@pytest.mark.asyncio
async def test_fatal_error_marks_outbox_failed(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    service = NotificationService(poll_interval=0.05, max_attempts=2, rate_limit_per_sec=10)
    configure_notification_service(service)

    async def fake_render(slot):
        return (
            "Текст уведомления",
            slot.candidate_tz or "Europe/Moscow",
            "Москва",
            "interview_confirmed_candidate",
            1,
        )

    async def bad_request_send(bot, method, correlation_id):
        raise TelegramBadRequest(method=method, message="Bad Request: chat not found")

    monkeypatch.setattr("backend.apps.bot.services._render_candidate_notification", fake_render)
    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", bad_request_send)

    try:
        async with async_session() as session:
            recruiter = models.Recruiter(
                name="Срыв",
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
                start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
                status=SlotStatus.PENDING,
                candidate_tg_id=6060,
                candidate_fio="Ошибка Фатальная",
                candidate_tz="Europe/Moscow",
            )
            session.add(slot)
            await session.commit()
            await session.refresh(slot)

        outbox_entry = await add_outbox_notification(
            notification_type="interview_confirmed_candidate",
            booking_id=slot.id,
            candidate_tg_id=slot.candidate_tg_id,
        )

        await service._poll_once()

        async with async_session() as session:
            outbox = await session.get(OutboxNotification, outbox_entry.id)
            assert outbox is not None
            assert outbox.status == "failed"
            assert outbox.attempts == 1
            assert outbox.next_retry_at is None
            assert outbox.last_error and "chat not found" in outbox.last_error.lower()

            log = await session.scalar(
                select(NotificationLog).where(
                    NotificationLog.booking_id == slot.id,
                    NotificationLog.type == "candidate_interview_confirmed",
                )
            )
            assert log is not None
            assert log.delivery_status == "failed"
            assert log.last_error and "chat not found" in log.last_error.lower()
    finally:
        await service.shutdown()
        await manager.clear()
        await manager.close()
        import backend.apps.bot.services as cleanup_services

        cleanup_services._notification_service = None


@pytest.mark.asyncio
async def test_broker_dlq_on_max_attempts(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    from backend.apps.bot.broker import InMemoryNotificationBroker

    broker = InMemoryNotificationBroker()
    await broker.start()

    service = NotificationService(
        poll_interval=0.05,
        max_attempts=1,
        rate_limit_per_sec=10,
        broker=broker,
    )
    configure_notification_service(service)

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="DLQ",
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
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            status=SlotStatus.PENDING,
            candidate_tg_id=222,
            candidate_fio="DLQ Тест",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        outbox = await add_outbox_notification(
            notification_type="interview_confirmed_candidate",
            booking_id=slot.id,
            candidate_tg_id=slot.candidate_tg_id,
        )

    async def failing_send(bot, method, correlation_id):
        raise TelegramServerError(method=method, message="server error")

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", failing_send)

    await service._enqueue_outbox(outbox.id, attempt=outbox.attempts)
    try:
        await service._poll_once()
        dlq_messages = list(broker.dlq_messages())
        assert dlq_messages, "Expected message to be routed to DLQ"
        dlq_payload = dlq_messages[0].payload
        assert dlq_payload.get("outbox_id") == outbox.id
        assert "failed_at" in dlq_payload
    finally:
        await service.shutdown()
        await manager.clear()
        await manager.close()
        import backend.apps.bot.services as bot_services

        bot_services._notification_service = None


@pytest.mark.asyncio
async def test_broker_bootstrap_from_outbox(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace()
    configure(dummy_bot, manager)

    from backend.apps.bot.broker import InMemoryNotificationBroker

    broker = InMemoryNotificationBroker()
    await broker.start()

    service = NotificationService(
        poll_interval=0.05,
        rate_limit_per_sec=10,
        broker=broker,
    )
    configure_notification_service(service)

    async with async_session() as session:
        template = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == "interview_confirmed_candidate",
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        if template is None:
            template = MessageTemplate(
                key="interview_confirmed_candidate",
                locale="ru",
                channel="tg",
                body_md="Текст {candidate_name}",
                version=1,
                is_active=True,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)

        recruiter = models.Recruiter(
            name="Bootstrap",
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
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            status=SlotStatus.PENDING,
            candidate_tg_id=333,
            candidate_fio="Бутстрап Тест",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        outbox = await add_outbox_notification(
            notification_type="interview_confirmed_candidate",
            booking_id=slot.id,
            candidate_tg_id=slot.candidate_tg_id,
        )

    send_calls = []

    async def successful_send(bot, method, correlation_id):
        send_calls.append(method)
        return SimpleNamespace(message_id=1)

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", successful_send)

    async def fake_render(slot):
        return (
            "Бутстрап",
            slot.candidate_tz or "Europe/Moscow",
            "",
            "interview_confirmed_candidate",
            1,
        )

    monkeypatch.setattr(
        "backend.apps.bot.services._render_candidate_notification",
        fake_render,
    )

    worker = get_notification_service()
    try:
        await worker._poll_once()

        assert send_calls, "ожидалась отправка сообщения через брокер после бутстрапа"

        async with async_session() as session:
            entry = await session.scalar(
                select(OutboxNotification).where(OutboxNotification.id == outbox.id)
            )
            assert entry is not None
            assert entry.status == "sent"
            assert entry.attempts == 1

            log = await session.scalar(
                select(NotificationLog).where(
                    NotificationLog.booking_id == slot.id,
                    NotificationLog.type == "candidate_interview_confirmed",
                )
            )
            assert log is not None
            assert log.delivery_status == "sent"
    finally:
        await service.shutdown()
        await manager.clear()
        await manager.close()
        import backend.apps.bot.services as bot_services

        bot_services._notification_service = None
