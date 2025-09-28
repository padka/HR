import pytest

pytest.importorskip("aiogram")

from backend.apps.bot.app import BotContext, create_application
from datetime import datetime

from backend.apps.bot.reminders import (
    AsyncioReminderQueue,
    ReminderCallback,
    ReminderQueueKey,
)
from backend.apps.bot.services import StateManager


@pytest.mark.asyncio
async def test_create_application_smoke():
    context = create_application("123456:ABCDEF")

    assert isinstance(context, BotContext)
    assert isinstance(context.state_manager, StateManager)
    assert context.dispatcher is not None
    assert isinstance(context.reminder_queue, AsyncioReminderQueue)

    await context.bot.session.close()


class _StubQueue:
    def __init__(self) -> None:
        self.enqueued: list[ReminderQueueKey] = []

    async def enqueue(
        self, key: ReminderQueueKey, when: datetime, callback: ReminderCallback
    ) -> None:
        self.enqueued.append(key)

    def cancel(self, key: ReminderQueueKey) -> None:
        pass

    async def flush(self) -> None:
        pass


@pytest.mark.asyncio
async def test_create_application_accepts_external_queue():
    queue = _StubQueue()
    context = create_application("123456:ABCDEF", reminder_queue=queue)

    assert context.reminder_queue is queue

    await context.bot.session.close()
