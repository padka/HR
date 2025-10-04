import asyncio
from dataclasses import dataclass

import pytest
from fastapi import FastAPI

from backend.apps.admin_ui import state as state_module


@dataclass
class DummySettings:
    bot_enabled: bool = True
    bot_provider: str = "telegram"
    bot_token: str = ""
    bot_api_base: str = ""
    bot_use_webhook: bool = False
    bot_webhook_url: str = ""
    bot_failfast: bool = False
    test2_required: bool = False
    bot_integration_enabled: bool = True
    redis_url: str = ""
    state_ttl_seconds: int = 60
    data_dir = state_module.get_settings().data_dir  # reuse existing data dir


@pytest.mark.asyncio
async def test_setup_bot_state_without_token(monkeypatch):
    app = FastAPI()

    monkeypatch.setattr(state_module, "get_settings", lambda: DummySettings())

    integration = await state_module.setup_bot_state(app)

    try:
        assert integration.bot is None
        assert not integration.bot_service.configured
        assert app.state.bot_service is integration.bot_service
        assert app.state.reminder_service is integration.reminder_service
    finally:
        await integration.shutdown()
