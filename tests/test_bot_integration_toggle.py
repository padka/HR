from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.services.bot_service import (
    BotService,
    BotSendResult,
    IntegrationSwitch,
)
from backend.apps.bot.state_store import build_state_manager


@pytest.mark.asyncio
async def test_bot_service_switch_blocks_dispatch(monkeypatch):
    state_manager = build_state_manager(redis_url=None, ttl_seconds=60)

    async def fake_start_test2(_user_id: int) -> None:
        return None

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.bot_service.start_test2",
        fake_start_test2,
    )

    switch = IntegrationSwitch(initial=True)
    service = BotService(
        state_manager=state_manager,
        enabled=True,
        configured=True,
        integration_switch=switch,
        required=False,
    )

    switch.set(False)

    result: BotSendResult = await service.send_test2(
        candidate_id=101,
        candidate_tz="Europe/Moscow",
        candidate_city=1,
        candidate_name="Тест",
    )

    assert result.status == "skipped:disabled"

    await state_manager.clear()
    await state_manager.close()


def test_api_integration_toggle(monkeypatch):
    monkeypatch.setattr(
        "backend.apps.admin_ui.state._build_bot",
        lambda settings: (None, False),
    )

    app = create_app()

    from backend.core.settings import get_settings
    settings = get_settings()

    with TestClient(app) as client:
        client.auth = (
            settings.admin_username or "admin",
            settings.admin_password or "admin",
        )

        status_initial = client.get("/api/bot/integration").json()
        assert status_initial["runtime_enabled"] in {True, False}

        response = client.post("/api/bot/integration", json={"enabled": False})
        assert response.status_code == 200
        payload = response.json()
        assert payload["runtime_enabled"] is False

        status_after = client.get("/api/bot/integration").json()
        assert status_after["runtime_enabled"] is False

        health = client.get("/health/bot").json()
        assert health["runtime"]["switch_enabled"] is False
        assert health["telegram"]["ok"] is False
