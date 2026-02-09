import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.admin_ui import state as state_module
from backend.apps.admin_ui.routers import system as system_router


@dataclass
class DummySettings:
    bot_enabled: bool = True
    bot_provider: str = "telegram"
    bot_token: str = ""
    bot_api_base: str = ""
    bot_use_webhook: bool = False
    bot_webhook_url: str = ""
    bot_failfast: bool = False
    bot_autostart: bool = False
    test2_required: bool = False
    bot_integration_enabled: bool = True
    bot_callback_secret: str = "dev-secret"
    redis_url: str = ""
    state_ttl_seconds: int = 60
    environment: str = "development"
    data_dir = state_module.get_settings().data_dir  # reuse existing data dir
    log_level: str = "INFO"
    log_json: bool = False
    log_file: str = ""
    session_secret: str = "dev-secret"


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


@pytest.mark.asyncio
async def test_setup_bot_state_with_custom_api_base(monkeypatch):
    app = FastAPI()
    base_url = "https://example.invalid"

    monkeypatch.setattr(
        state_module,
        "get_settings",
        lambda: DummySettings(bot_token="123:ABC", bot_api_base=base_url),
    )

    integration = await state_module.setup_bot_state(app)

    try:
        assert integration.bot is not None
        api = integration.bot.session.api
        assert getattr(api, "api_base", base_url).startswith(base_url)
    finally:
        await integration.shutdown()


class StubNotificationService:
    def __init__(self):
        self.snapshot = {
            "started": True,
            "loop_enabled": True,
            "broker_backend": "memory",
            "broker_kind": "InMemoryNotificationBroker",
            "scheduler_job": False,
            "watchdog_running": False,
            "circuit_open": False,
            "seconds_since_poll": None,
            "metrics": {
                "outbox_queue_depth": 0,
                "poll_skipped_total": 0,
                "poll_skipped_reasons": {},
                "poll_backoff_total": 0,
                "poll_backoff_reasons": {},
                "poll_staleness_seconds": 0.0,
                "rate_limit_wait_total": 0,
                "rate_limit_wait_seconds": 0.0,
                "notifications_sent_total": {},
                "notifications_failed_total": {},
            },
        }
        self.metrics = SimpleNamespace(
            outbox_queue_depth=0,
            poll_skipped_total=0,
            poll_skipped_reasons={},
            poll_backoff_total=0,
            poll_backoff_reasons={},
            rate_limit_wait_total=0,
            rate_limit_wait_seconds=0.0,
            notifications_sent_total={"candidate_rejection": 1},
            notifications_failed_total={},
            poll_staleness_seconds=0.0,
        )

    async def health_snapshot(self):
        return self.snapshot

    async def broker_ping(self):
        return True

    async def metrics_snapshot(self):
        return self.metrics


class StubReminderService:
    def health_snapshot(self):
        return {"scheduler_running": True, "job_count": 0}


class StubBotService:
    health_status = "ready"

    def is_ready(self):
        return True


class DummyTask:
    def done(self):
        return False


def test_notifications_health_endpoint_ok(monkeypatch):
    class EnabledSettings:
        bot_enabled = True
        bot_integration_enabled = True

    monkeypatch.setattr(system_router, "get_settings", lambda: EnabledSettings())

    app = FastAPI()
    app.include_router(system_router.router)
    app.state.notification_service = StubNotificationService()
    app.state.reminder_service = StubReminderService()
    app.state.bot_service = StubBotService()
    app.state.bot_runner_task = DummyTask()

    client = TestClient(app)
    resp = client.get("/health/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notifications"]["status"] == "ok"
    assert data["bot"]["polling"] is True


def test_notifications_health_endpoint_missing_service(monkeypatch):
    class EnabledSettings:
        bot_enabled = True
        bot_integration_enabled = True

    monkeypatch.setattr(system_router, "get_settings", lambda: EnabledSettings())

    app = FastAPI()
    app.include_router(system_router.router)
    client = TestClient(app)
    resp = client.get("/health/notifications")
    assert resp.status_code == 503
    data = resp.json()
    assert data["notifications"]["status"] == "missing"


def test_notifications_metrics_endpoint_prometheus():
    app = FastAPI()
    app.include_router(system_router.router)
    app.state.notification_service = StubNotificationService()
    client = TestClient(app)
    resp = client.get("/metrics/notifications")
    assert resp.status_code == 200
    text = resp.text
    assert "notification_outbox_queue_depth" in text
    assert 'notification_sent_total{type="candidate_rejection"} 1' in text
