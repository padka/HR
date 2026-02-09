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


def test_integration_switch_tracks_source_and_reason():
    switch = IntegrationSwitch(initial=True)
    assert switch.source == "operator"
    assert switch.reason is None

    switch.set(False, source="runtime", reason="telegram_unauthorized")
    assert switch.is_enabled() is False
    assert switch.source == "runtime"
    assert switch.reason == "telegram_unauthorized"


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
        assert status_initial["switch_source"] == "operator"
        assert status_initial["switch_reason"] is None

        response = client.post("/api/bot/integration", json={"enabled": False})
        assert response.status_code == 200
        payload = response.json()
        assert payload["runtime_enabled"] is False
        assert payload["switch_source"] == "operator"
        assert payload["switch_reason"] is None

        status_after = client.get("/api/bot/integration").json()
        assert status_after["runtime_enabled"] is False
        assert status_after["switch_source"] == "operator"
        assert status_after["switch_reason"] is None

        health = client.get("/health/bot").json()
        assert health["status"] == "disabled"
        assert health["runtime"]["switch_enabled"] is False
        assert health["runtime"]["switch_source"] == "operator"
        assert health["runtime"]["switch_reason"] is None
        assert health["telegram"]["ok"] is False


def test_runtime_disable_reflected_in_health(monkeypatch):
    monkeypatch.setenv("BOT_ENABLED", "1")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "1")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr(
        "backend.apps.admin_ui.state._build_bot",
        lambda settings: (None, False),
    )

    app = create_app()

    class _FatalNotificationService:
        async def health_snapshot(self):
            return {
                "started": True,
                "loop_enabled": True,
                "broker_backend": "memory",
                "broker_kind": "InMemoryNotificationBroker",
                "scheduler_job": True,
                "watchdog_running": True,
                "circuit_open": False,
                "seconds_since_poll": 1.0,
                "fatal_error_code": "telegram_unauthorized",
                "fatal_error_at": "2026-01-01T00:00:00+00:00",
                "last_delivery_error": "telegram_unauthorized",
                "metrics": {"outbox_queue_depth": 0},
            }

        async def broker_ping(self):
            return True

    from backend.core.settings import get_settings

    settings = get_settings()
    with TestClient(app) as client:
        client.auth = (
            settings.admin_username or "admin",
            settings.admin_password or "admin",
        )
        app.state.notification_service = _FatalNotificationService()
        app.state.bot_integration_switch.set(
            False,
            source="runtime",
            reason="telegram_unauthorized",
        )

        bot_health = client.get("/health/bot")
        assert bot_health.status_code == 200
        bot_payload = bot_health.json()
        assert bot_payload["status"] == "error"
        assert bot_payload["runtime"]["switch_source"] == "runtime"
        assert bot_payload["runtime"]["switch_reason"] == "telegram_unauthorized"

        notifications_health = client.get("/health/notifications")
        assert notifications_health.status_code == 503
        notifications_payload = notifications_health.json()
        assert notifications_payload["notifications"]["fatal_error_code"] == "telegram_unauthorized"
    settings_module.get_settings.cache_clear()


def test_disabled_bot_health_endpoints_return_200(monkeypatch):
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setattr(
        "backend.apps.admin_ui.state._build_bot",
        lambda settings: (None, False),
    )

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    app = create_app()

    settings = settings_module.get_settings()
    with TestClient(app) as client:
        client.auth = (
            settings.admin_username or "admin",
            settings.admin_password or "admin",
        )

        bot_health = client.get("/health/bot")
        assert bot_health.status_code == 200
        bot_payload = bot_health.json()
        assert bot_payload["status"] == "disabled"
        assert bot_payload["runtime"]["disabled_by"] == "config"

        notifications_health = client.get("/health/notifications")
        assert notifications_health.status_code == 200
        notifications_payload = notifications_health.json()
        assert notifications_payload["status"] == "disabled"
        assert notifications_payload["notifications"]["status"] == "disabled"
    settings_module.get_settings.cache_clear()
