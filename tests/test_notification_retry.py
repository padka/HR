import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramServerError
from aiogram.methods import SendMessage
from sqlalchemy import select, update

from backend.apps.bot.metrics import get_notification_metrics_snapshot
from backend.apps.bot.services import (
    NotificationService,
    configure,
    configure_notification_service,
    get_notification_service,
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
from backend.domain.repositories import add_outbox_notification


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
