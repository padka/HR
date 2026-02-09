import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Tuple

import os

import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("ADMIN_USER", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.services import slots as slot_services
from backend.apps.admin_ui.services.bot_service import BotSendResult, BotService, configure_bot_service
from backend.core.settings import get_settings
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates import services as candidate_services


def _force_ready_bot(monkeypatch) -> None:
    def _fake_build(settings):
        return None, True

    monkeypatch.setenv("BOT_ENABLED", "1")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "1")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state._build_bot", _fake_build)


async def _create_booked_slot() -> Tuple[int, int]:
    async with async_session() as session:
        recruiter = models.Recruiter(name="API", tz="Europe/Moscow", active=True)
        city = models.City(name="API City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=7777,
            candidate_fio="API Candidate",
            candidate_city_id=city.id,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        return slot.id, int(slot.candidate_tg_id)


async def _create_booked_slot_no_telegram() -> int:
    async with async_session() as session:
        recruiter = models.Recruiter(name="API", tz="Europe/Moscow", active=True)
        city = models.City(name="API City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.BOOKED,
            candidate_id="cand-001",
            candidate_fio="API Candidate",
            candidate_city_id=city.id,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        return slot.id


async def _async_request(
    app,
    method: str,
    path: str,
    *,
    before_request: Optional[Callable[[Any], None]] = None,
    **kwargs,
) -> Any:
    if before_request is not None:
        before_request(app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            auth=("admin", "admin"),
        ) as client:
            return await client.request(method, path, **kwargs)


@pytest.fixture
def admin_slots_app(monkeypatch) -> Any:
    class _DummyIntegration:
        async def shutdown(self) -> None:
            return None

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
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def clear_state_manager():
    try:
        state_manager = slot_services.get_state_manager()
    except RuntimeError:
        yield
        return
    await state_manager.clear()
    yield
    await state_manager.clear()


@pytest.mark.asyncio
async def test_slot_outcome_endpoint_uses_state_manager(monkeypatch):
    from backend.apps.admin_ui.state import BotIntegration
    from backend.apps.bot.services import StateManager, configure as configure_bot_services
    from backend.apps.admin_ui.services.bot_service import IntegrationSwitch

    slot_id, candidate_id = await _create_booked_slot()

    async def fake_setup_bot_state(app):
        from backend.apps.bot.state_store import build_state_manager
        from unittest.mock import AsyncMock

        state_manager = build_state_manager(redis_url=None, ttl_seconds=604800)

        # Create a dummy bot mock
        class DummyBot:
            def __init__(self):
                self.session = AsyncMock()
                self.session.close = AsyncMock()

            async def send_message(self, *args, **kwargs):
                return AsyncMock()

        dummy_bot = DummyBot()
        configure_bot_services(dummy_bot, state_manager)
        switch = IntegrationSwitch(initial=True)
        class _DummyReminderService:
            async def schedule_for_slot(self, *_args, **_kwargs):
                return None

            async def cancel_for_slot(self, *_args, **_kwargs):
                return None

            async def shutdown(self):
                return None

            def stats(self):
                return {"total": 0, "reminders": 0, "confirm_prompts": 0}

        reminder_service = _DummyReminderService()

        class _DummyNotificationService:
            async def send_notification(self, *_args, **_kwargs):
                return None

            async def shutdown(self):
                return None

        notification_service = _DummyNotificationService()
        notification_broker = None

        service = BotService(
            state_manager=state_manager,
            enabled=True,
            configured=True,
            integration_switch=switch,
            required=False,
        )
        configure_bot_service(service)
        app.state.bot = dummy_bot
        app.state.state_manager = state_manager
        app.state.bot_service = service
        app.state.bot_integration_switch = switch
        app.state.reminder_service = reminder_service
        app.state.notification_service = notification_service
        app.state.notification_broker = notification_broker
        return BotIntegration(
            state_manager=state_manager,
            bot=dummy_bot,
            bot_service=service,
            integration_switch=switch,
            reminder_service=reminder_service,
            notification_service=notification_service,
            notification_broker=notification_broker,
        )

    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup_bot_state)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup_bot_state)

    app = create_app()

    response = await _async_request(
        app,
        "post",
        f"/slots/{slot_id}/outcome",
        json={"outcome": "success"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["outcome"] == "success"
    assert response.headers.get("X-Bot") == "sent_test2"


@pytest.mark.asyncio
async def test_reschedule_endpoint_falls_back_when_notifications_missing(admin_slots_app):
    slot_id, _ = await _create_booked_slot()

    response = await _async_request(
        admin_slots_app,
        "post",
        f"/slots/{slot_id}/reschedule",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Слот освобождён" in payload["message"]

    async with async_session() as session:
        slot = await session.get(models.Slot, slot_id)
        assert slot is not None
        assert slot.status == models.SlotStatus.FREE


@pytest.mark.asyncio
async def test_reject_endpoint_falls_back_when_notifications_missing(admin_slots_app):
    slot_id, candidate_id = await _create_booked_slot()

    response = await _async_request(
        admin_slots_app,
        "post",
        f"/slots/{slot_id}/reject_booking",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Слот освобождён" in payload["message"]

    async with async_session() as session:
        slot = await session.get(models.Slot, slot_id)
        assert slot is not None
        assert slot.status == models.SlotStatus.FREE

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.interview_outcome is None
        assert updated.test2_sent_at is None


@pytest.mark.asyncio
async def test_reject_booking_without_telegram_id_releases_slot(admin_slots_app):
    slot_id = await _create_booked_slot_no_telegram()

    response = await _async_request(
        admin_slots_app,
        "post",
        f"/slots/{slot_id}/reject_booking",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Слот освобождён" in payload["message"]

    async with async_session() as session:
        refreshed = await session.get(models.Slot, slot_id)
        assert refreshed is not None
        assert refreshed.status == models.SlotStatus.FREE
        assert refreshed.candidate_id is None
        assert refreshed.candidate_tg_id is None


@pytest.mark.asyncio
async def test_reschedule_without_telegram_id_releases_slot(admin_slots_app):
    slot_id = await _create_booked_slot_no_telegram()

    response = await _async_request(
        admin_slots_app,
        "post",
        f"/slots/{slot_id}/reschedule",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Слот освобождён" in payload["message"]

    async with async_session() as session:
        refreshed = await session.get(models.Slot, slot_id)
        assert refreshed is not None
        assert refreshed.status == models.SlotStatus.FREE
        assert refreshed.candidate_id is None
        assert refreshed.candidate_tg_id is None


@pytest.mark.asyncio
async def test_reject_booking_handles_notification_errors(monkeypatch, admin_slots_app):
    slot_id, _ = await _create_booked_slot()

    def failing_notification_service():
        class DummyService:
            async def on_booking_status_changed(self, *_args, **_kwargs):
                raise RuntimeError("Bot is not configured")
        return DummyService()

    monkeypatch.setattr(slot_services, "get_notification_service", failing_notification_service)

    response = await _async_request(
        admin_slots_app,
        "post",
        f"/slots/{slot_id}/reject_booking",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Слот освобождён" in payload["message"]

    async with async_session() as session:
        refreshed = await session.get(models.Slot, slot_id)
        assert refreshed is not None
        assert refreshed.status == models.SlotStatus.FREE


@pytest.mark.asyncio
async def test_reschedule_handles_notification_errors(monkeypatch, admin_slots_app):
    slot_id, _ = await _create_booked_slot()

    def failing_notification_service():
        class DummyService:
            async def on_booking_status_changed(self, *_args, **_kwargs):
                raise RuntimeError("Bot is not configured")
        return DummyService()

    monkeypatch.setattr(slot_services, "get_notification_service", failing_notification_service)

    response = await _async_request(
        admin_slots_app,
        "post",
        f"/slots/{slot_id}/reschedule",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Слот освобождён" in payload["message"]

    async with async_session() as session:
        refreshed = await session.get(models.Slot, slot_id)
        assert refreshed is not None
        assert refreshed.status == models.SlotStatus.FREE


@pytest.mark.asyncio
async def test_slot_outcome_endpoint_returns_200_when_bot_unavailable(monkeypatch):
    slot_id, _ = await _create_booked_slot()
    _force_ready_bot(monkeypatch)
    app = create_app()

    async def fake_send_test2(*_args, **_kwargs):
        return BotSendResult(ok=False, status="skipped:error", error="Бот недоступен. Проверьте его конфигурацию.")

    monkeypatch.setattr(slot_services, "_trigger_test2", fake_send_test2)

    response = await _async_request(app, "post", f"/slots/{slot_id}/outcome", json={"outcome": "success"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert response.headers.get("X-Bot") == "sent_test2"

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.test2_sent_at is None


@pytest.mark.asyncio
async def test_slot_outcome_endpoint_skips_when_bot_optional(monkeypatch):
    slot_id, _ = await _create_booked_slot()
    _force_ready_bot(monkeypatch)
    app = create_app()

    async def fake_send_test2(*_args, **_kwargs):
        return BotSendResult(ok=True, status="skipped:not_configured", message="Отправка Теста 2 пропущена")

    monkeypatch.setattr(slot_services, "_trigger_test2", fake_send_test2)

    response = await _async_request(app, "post", f"/slots/{slot_id}/outcome", json={"outcome": "success"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert response.headers.get("X-Bot") == "sent_test2"

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.test2_sent_at is None


@pytest.mark.asyncio
async def test_slot_outcome_success_idempotent(monkeypatch):
    slot_id, _ = await _create_booked_slot()
    _force_ready_bot(monkeypatch)
    app = create_app()

    calls: Dict[str, int] = {"count": 0}

    async def fake_send_test2(*_args, **_kwargs):
        calls["count"] += 1
        return BotSendResult(ok=True, status="sent")

    monkeypatch.setattr(slot_services, "_trigger_test2", fake_send_test2)

    first = await _async_request(app, "post", f"/slots/{slot_id}/outcome", json={"outcome": "success"})
    assert first.status_code == 200
    assert first.headers.get("X-Bot") == "sent_test2"

    second = await _async_request(app, "post", f"/slots/{slot_id}/outcome", json={"outcome": "success"})
    assert second.status_code == 200
    assert second.headers.get("X-Bot") == "skipped:already_sent"

    await asyncio.sleep(0.05)

    assert calls["count"] == 1

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.test2_sent_at is not None


@pytest.mark.asyncio
async def test_slot_outcome_reject_triggers_rejection(monkeypatch):
    slot_id, _ = await _create_booked_slot()
    _force_ready_bot(monkeypatch)
    app = create_app()

    calls: Dict[str, int] = {"count": 0}

    async def fake_send_rejection(*_args, **_kwargs):
        calls["count"] += 1
        return BotSendResult(ok=True, status="sent_rejection")

    monkeypatch.setattr(slot_services, "_trigger_rejection", fake_send_rejection)

    first = await _async_request(app, "post", f"/slots/{slot_id}/outcome", json={"outcome": "reject"})
    assert first.status_code == 200
    assert first.headers.get("X-Bot") == "sent_rejection"

    second = await _async_request(app, "post", f"/slots/{slot_id}/outcome", json={"outcome": "reject"})
    assert second.status_code == 200
    assert second.headers.get("X-Bot") == "skipped:already_sent"

    await asyncio.sleep(0.05)

    assert calls["count"] == 1

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.rejection_sent_at is not None


@pytest.mark.asyncio
async def test_health_check_reports_ok(admin_slots_app):
    response = await _async_request(admin_slots_app, "get", "/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
    # In test mode, state_manager is optional (set to None by fixture)
    assert payload["checks"]["state_manager"] in {"ok", "missing"}
    assert payload["checks"]["bot_client"] in {"ready", "unconfigured", "disabled", "missing"}


@pytest.mark.asyncio
async def test_slots_create_returns_422_when_required_fields_missing(admin_slots_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(name="Slot Admin", tz="Europe/Moscow", active=True)
        city = models.City(name="Slot City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        recruiter_id = recruiter.id

    response = await _async_request(
        admin_slots_app,
        "post",
        "/slots/create",
        data={
            "recruiter_id": str(recruiter_id),
            "city_id": "",
            "date": "",
            "time": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Укажите город" in response.text


@pytest.mark.asyncio
async def test_candidate_slot_can_be_approved_via_admin(monkeypatch, admin_slots_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=55001,
        fio="Админ Проверка",
        city="Москва",
    )

    async with async_session() as session:
        recruiter = models.Recruiter(name="Approve Admin", tz="Europe/Moscow", active=True)
        city = models.City(name="Approve City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            status=models.SlotStatus.PENDING,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_city_id=city.id,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    called = {}

    class DummyResult:
        status = "approved"
        message = "ok"
        slot = None
        summary_html = None

    async def fake_approve(slot_id: int, *, force_notify: bool = False):
        called["slot_id"] = slot_id
        called["force_notify"] = force_notify
        return DummyResult()

    monkeypatch.setattr(
        "backend.apps.admin_ui.routers.candidates.approve_slot_and_notify",
        fake_approve,
    )

    response = await _async_request(
        admin_slots_app,
        "post",
        f"/candidates/{candidate.id}/slots/{slot_id}/approve",
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers.get("location", "")
    assert f"/candidates/{candidate.id}" in location
    assert "approval=approved" in location
    assert called.get("slot_id") == slot_id


@pytest.mark.asyncio
async def test_candidate_slot_approval_validates_owner(monkeypatch, admin_slots_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=66001,
        fio="Несовпадение",
        city="Самара",
    )
    other = await candidate_services.create_or_update_user(
        telegram_id=66002,
        fio="Другой",
        city="Самара",
    )

    async with async_session() as session:
        recruiter = models.Recruiter(name="Approve Guard", tz="Europe/Moscow", active=True)
        city = models.City(name="Approve Guard City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=3),
            status=models.SlotStatus.PENDING,
            candidate_tg_id=other.telegram_id,
            candidate_fio=other.fio,
            candidate_city_id=city.id,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    async def fail_if_called(_slot_id: int):
        raise AssertionError("helper should not be invoked when slot mismatched")

    monkeypatch.setattr(
        "backend.apps.admin_ui.routers.candidates.approve_slot_and_notify",
        fail_if_called,
    )

    response = await _async_request(
        admin_slots_app,
        "post",
        f"/candidates/{candidate.id}/slots/{slot_id}/approve",
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers.get("location", "")
    assert "approval=invalid_candidate" in location


@pytest.mark.asyncio
async def test_slots_create_returns_422_when_city_id_invalid(admin_slots_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(name="Slot Admin 2", tz="Europe/Moscow", active=True)
        city = models.City(name="Slot City 2", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        recruiter_id = recruiter.id

    response = await _async_request(
        admin_slots_app,
        "post",
        "/slots/create",
        data={
            "recruiter_id": str(recruiter_id),
            "city_id": "abc",
            "date": "2024-10-10",
            "time": "10:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Укажите корректный город" in response.text


@pytest.mark.asyncio
async def test_bot_health_endpoint_reports_status(monkeypatch):
    app = create_app()
    response = await _async_request(app, "get", "/health/bot")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"status", "config", "runtime", "telegram", "state_store", "queues"}
    assert payload["status"] in {"ok", "disabled", "degraded", "error"}
    assert payload["runtime"]["mode"] in {"real", "null"}
    assert "switch_enabled" in payload["runtime"]
    assert "integration_enabled" in payload["config"]


@pytest.mark.asyncio
async def test_api_slots_returns_local_time(admin_slots_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(name="Local TZ", tz="Europe/Moscow", active=True)
        city = models.City(name="Новосибирск", tz="Asia/Novosibirsk", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc),
            duration_min=45,
            status=models.SlotStatus.FREE,
            tz_name=city.tz,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    response = await _async_request(
        admin_slots_app,
        "get",
        "/api/slots",
        params={"limit": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    found = next((item for item in payload if item["id"] == slot.id), None)
    assert found is not None
    assert found["tz_name"] == "Asia/Novosibirsk"
    # Accept both with and without timezone suffix
    assert found["start_utc"] in ["2024-01-01T06:00:00+00:00", "2024-01-01T06:00:00"]
    assert found["local_time"] in ["2024-01-01T13:00:00+07:00", "2024-01-01T13:00:00"]
