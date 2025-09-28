import pytest

from backend.apps.bot.app import create_application
from backend.apps.bot.services import StateManager


@pytest.mark.asyncio
async def test_create_application_smoke():
    bot, dispatcher, state_manager = create_application("123456:ABCDEF")

    assert isinstance(state_manager, StateManager)
    assert dispatcher is not None

    await bot.session.close()
