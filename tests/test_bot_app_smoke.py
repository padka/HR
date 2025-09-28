import pytest

pytest.importorskip("aiogram")

from backend.apps.bot.app import BotContext, create_application
from backend.apps.bot.reminders import AsyncioReminderQueue
from backend.apps.bot.services import StateManager


@pytest.mark.asyncio
async def test_create_application_smoke():
    context = create_application("123456:ABCDEF")

    assert isinstance(context, BotContext)
    assert isinstance(context.state_manager, StateManager)
    assert context.dispatcher is not None
    assert isinstance(context.reminder_queue, AsyncioReminderQueue)

    await context.bot.session.close()
