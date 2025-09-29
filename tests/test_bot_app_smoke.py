import pytest

pytest.importorskip("aiogram")

from backend.apps.bot import app as bot_app
from backend.apps.bot.services import StateManager


@pytest.mark.asyncio
async def test_create_application_smoke(monkeypatch):
    async def dummy_init_models() -> None:
        return None

    monkeypatch.setattr(bot_app, "init_models", dummy_init_models)

    bot, dispatcher, state_manager = bot_app.create_application("123456:ABCDEF")

    assert isinstance(state_manager, StateManager)
    assert dispatcher is not None

    await bot.session.close()
