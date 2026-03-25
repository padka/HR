import pytest
from fastapi.testclient import TestClient

from backend.core.db import async_session
from backend.core.messenger.channel_state import (
    get_messenger_channel_health,
    mark_messenger_channel_healthy,
    set_messenger_channel_degraded,
)
from backend.domain.models import NotificationLog, OutboxNotification
from backend.domain import models


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


def _csrf(client: TestClient) -> str:
    resp = client.get("/api/csrf", auth=("admin", "admin"))
    assert resp.status_code == 200
    token = (resp.json() or {}).get("token") or ""
    assert token
    return str(token)


@pytest.fixture
def notifications_feed_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    import importlib

    state_module = importlib.import_module("backend.apps.admin_ui.state")
    app_module = importlib.import_module("backend.apps.admin_ui.app")
    importlib.reload(state_module)
    app_module = importlib.reload(app_module)
    monkeypatch.setattr(state_module, "setup_bot_state", fake_setup)
    monkeypatch.setattr(app_module, "setup_bot_state", fake_setup, raising=False)
    app = app_module.create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


def test_notifications_feed_returns_degraded_payload_when_db_unavailable(
    notifications_feed_app,
):
    with TestClient(notifications_feed_app) as client:
        notifications_feed_app.state.db_available = False
        response = client.get(
            "/api/notifications/feed?after_id=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["latest_id"] == 10
    assert payload["degraded"] is True


def test_notifications_logs_returns_degraded_payload_when_db_unavailable(
    notifications_feed_app,
):
    with TestClient(notifications_feed_app) as client:
        notifications_feed_app.state.db_available = False
        response = client.get(
            "/api/notifications/logs?after_id=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["latest_id"] == 10
    assert payload["degraded"] is True


def test_notifications_feed_returns_outbox_items(notifications_feed_app):
    import asyncio

    def _run(coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    async def _seed() -> int:
        async with async_session() as session:
            entry = OutboxNotification(
                type="candidate_reschedule_prompt",
                status="failed",
                attempts=2,
                last_error="telegram_timeout",
                candidate_tg_id=123,
                recruiter_tg_id=456,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return int(entry.id)

    entry_id = _run(_seed())

    with TestClient(notifications_feed_app) as client:
        response = client.get(
            "/api/notifications/feed?after_id=0&limit=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["degraded"] is False
    assert payload["latest_id"] >= entry_id
    item = next(item for item in payload["items"] if item["id"] == entry_id)
    assert item["channel"] == "telegram"
    assert item["failure_class"] is None
    assert item["failure_code"] is None
    assert item["provider_message_id"] is None
    assert item["dead_lettered_at"] is None
    assert "degraded_reason" in item


def test_notifications_logs_returns_items(notifications_feed_app):
    import asyncio
    from datetime import datetime, timedelta, timezone

    def _run(coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    async def _seed() -> int:
        async with async_session() as session:
            recruiter = models.Recruiter(name="Logs Rec", tz="Europe/Moscow", active=True)
            city = models.City(name="Logs City", tz="Europe/Moscow", active=True)
            session.add_all([recruiter, city])
            await session.commit()
            await session.refresh(recruiter)
            await session.refresh(city)

            slot = models.Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name=city.tz,
                start_utc=datetime.now(timezone.utc) + timedelta(days=1),
                duration_min=60,
                status=models.SlotStatus.BOOKED,
                candidate_tg_id=123,
                candidate_tz="Europe/Moscow",
            )
            session.add(slot)
            await session.commit()
            await session.refresh(slot)

            entry = NotificationLog(
                booking_id=slot.id,
                candidate_tg_id=123,
                type="slot_reminder",
                delivery_status="failed",
                channel="max",
                attempts=2,
                attempt_no=2,
                last_error="telegram_timeout",
                failure_class="transient",
                provider_message_id="provider-42",
                template_key="confirm_2h",
                template_version=1,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return int(entry.id)

    entry_id = _run(_seed())

    with TestClient(notifications_feed_app) as client:
        response = client.get(
            "/api/notifications/logs?after_id=0&limit=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["degraded"] is False
    assert payload["latest_id"] >= entry_id
    item = next(item for item in payload["items"] if item["id"] == entry_id)
    assert item["channel"] == "max"
    assert item["attempt_no"] == 2
    assert item["failure_class"] == "transient"
    assert item["provider_message_id"] == "provider-42"


def test_system_messenger_health_returns_channel_snapshot(notifications_feed_app):
    import asyncio

    def _run(coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    async def _seed() -> None:
        async with async_session() as session:
            pending = OutboxNotification(
                type="slot_reminder",
                status="pending",
                attempts=0,
                messenger_channel="telegram",
                candidate_tg_id=1001,
            )
            dead_letter = OutboxNotification(
                type="slot_reminder",
                status="dead_letter",
                attempts=2,
                messenger_channel="max",
                candidate_tg_id=1002,
                failure_class="misconfiguration",
                failure_code="invalid_token",
            )
            session.add_all([pending, dead_letter])
            await session.commit()

    _run(_seed())
    _run(set_messenger_channel_degraded("max", reason="max:invalid_token"))

    try:
        with TestClient(notifications_feed_app) as client:
            response = client.get(
                "/api/system/messenger-health",
                auth=("admin", "admin"),
                headers={"Accept": "application/json"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["channels"]["telegram"]["queue_depth"] >= 1
        assert payload["channels"]["max"]["dead_letter_count"] >= 1
        assert payload["channels"]["max"]["degraded"] is True
        assert payload["channels"]["max"]["degraded_reason"] == "max:invalid_token"
    finally:
        _run(mark_messenger_channel_healthy("max"))


def test_notifications_retry_and_cancel_endpoints(notifications_feed_app):
    import asyncio

    def _run(coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    async def _seed() -> tuple[int, int]:
        async with async_session() as session:
            failed = OutboxNotification(
                type="slot_assignment_offer",
                status="dead_letter",
                attempts=1,
                last_error="telegram_unauthorized",
                messenger_channel="max",
                failure_class="misconfiguration",
                failure_code="invalid_token",
            )
            pending = OutboxNotification(
                type="slot_assignment_offer",
                status="pending",
                attempts=0,
            )
            session.add_all([failed, pending])
            await session.commit()
            await session.refresh(failed)
            await session.refresh(pending)
            return int(failed.id), int(pending.id)

    failed_id, pending_id = _run(_seed())
    _run(set_messenger_channel_degraded("max", reason="max:invalid_token"))

    with TestClient(notifications_feed_app) as client:
        token = _csrf(client)
        retry_resp = client.post(
            f"/api/notifications/{failed_id}/retry",
            auth=("admin", "admin"),
            headers={"Accept": "application/json", "x-csrf-token": token},
        )
        assert retry_resp.status_code == 200
        assert retry_resp.json()["ok"] is True

        cancel_resp = client.post(
            f"/api/notifications/{pending_id}/cancel",
            auth=("admin", "admin"),
            headers={"Accept": "application/json", "x-csrf-token": token},
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["ok"] is True

    async def _fetch(outbox_id: int) -> OutboxNotification | None:
        async with async_session() as session:
            return await session.get(OutboxNotification, outbox_id)

    failed_entry = _run(_fetch(failed_id))
    pending_entry = _run(_fetch(pending_id))
    assert failed_entry is not None
    assert pending_entry is not None
    assert (failed_entry.status or "").lower() == "pending"
    assert failed_entry.failure_class is None
    assert failed_entry.failure_code is None
    assert failed_entry.dead_lettered_at is None
    assert (pending_entry.status or "").lower() == "failed"
    health = _run(get_messenger_channel_health())
    assert health["max"]["status"] == "degraded"

    with TestClient(notifications_feed_app) as client:
        token = _csrf(client)
        recover_resp = client.post(
            "/api/system/messenger-health/max/recover",
            auth=("admin", "admin"),
            headers={"Accept": "application/json", "x-csrf-token": token},
        )

    assert recover_resp.status_code == 200
    assert recover_resp.json() == {"ok": True, "channel": "max"}
    health = _run(get_messenger_channel_health())
    assert health["max"]["status"] == "healthy"
    _run(mark_messenger_channel_healthy("max"))
