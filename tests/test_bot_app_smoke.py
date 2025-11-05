import pytest

pytest.importorskip("aiogram")

from backend.apps.bot import app as bot_app
from backend.apps.bot.services import StateManager
from backend.apps.bot.state_store import InMemoryStateStore


@pytest.mark.asyncio
async def test_create_application_smoke(monkeypatch):
    async def dummy_init_models() -> None:
        return None

    monkeypatch.setattr(bot_app, "init_models", dummy_init_models)

    bot, dispatcher, state_manager, reminder_service, notification_service = await bot_app.create_application(
        "123456:ABCDEF"
    )

    assert isinstance(state_manager, StateManager)
    assert dispatcher is not None

    await bot.session.close()
    await state_manager.close()
    await reminder_service.shutdown()
    await notification_service.shutdown()


@pytest.mark.asyncio
async def test_state_manager_get_with_default():
    manager = StateManager(InMemoryStateStore(ttl_seconds=5))
    default_state = {"flow": "intro"}

    assert await manager.get(1, default_state) is default_state

    existing_state = {"flow": "interview"}
    await manager.set(1, existing_state)  # type: ignore[arg-type]

    loaded = await manager.get(1, default_state)
    assert loaded == existing_state

    await manager.close()
