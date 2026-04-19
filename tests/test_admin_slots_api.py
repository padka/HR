import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

os.environ.setdefault("ADMIN_USER", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.services import slots as slot_services
from backend.apps.admin_ui.services.bot_service import (
    BotSendResult,
    BotService,
    configure_bot_service,
)
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain import models
from backend.domain.candidates import services as candidate_services


def _login(
    client: TestClient,
    username: str | None = None,
    password: str | None = None,
) -> None:
    settings = get_settings()
    response = client.post(
        "/auth/login",
        data={
            "username": username or settings.admin_username or "admin",
            "password": password or settings.admin_password or "admin",
            "redirect_to": "/",
        },
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}


def _force_ready_bot(monkeypatch) -> None:
    def _fake_build(settings):
        return None, True

    monkeypatch.setenv("BOT_ENABLED", "1")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "1")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state._build_bot", _fake_build)


async def _create_booked_slot() -> tuple[int, int]:
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
            start_utc=datetime.now(UTC),
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
            start_utc=datetime.now(UTC),
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
    before_request: Callable[[Any], None] | None = None,
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


async def _async_request_with_csrf(app, method: str, path: str, **kwargs) -> Any:
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            auth=("admin", "admin"),
        ) as client:
            csrf = await client.get("/api/csrf")
            assert csrf.status_code == 200
            token = (csrf.json() or {}).get("token")
            assert token
            headers = dict(kwargs.pop("headers", {}) or {})
            headers["x-csrf-token"] = str(token)
            return await client.request(method, path, headers=headers, **kwargs)


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
    from backend.apps.admin_ui.services.bot_service import IntegrationSwitch
    from backend.apps.admin_ui.state import BotIntegration
    from backend.apps.bot.services import configure as configure_bot_services

    slot_id, candidate_id = await _create_booked_slot()

    async def fake_setup_bot_state(app):
        from unittest.mock import AsyncMock

        from backend.apps.bot.state_store import build_state_manager

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
async def test_reschedule_reuses_existing_free_target_slot(admin_slots_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=991001,
        fio="Reschedule Existing Slot",
        city="Москва",
    )

    async with async_session() as session:
        recruiter = models.Recruiter(name="Reschedule Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name="Reschedule City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        old_start = datetime(2031, 6, 1, 7, 20, tzinfo=UTC)
        target_start = datetime(2031, 6, 1, 10, 0, tzinfo=UTC)

        current_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=old_start,
            duration_min=20,
            status=models.SlotStatus.PENDING,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        reusable_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=target_start,
            duration_min=20,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([current_slot, reusable_slot])
        await session.commit()
        await session.refresh(current_slot)
        await session.refresh(reusable_slot)

        assignment = models.SlotAssignment(
            slot_id=current_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.RESCHEDULE_REQUESTED,
            offered_at=datetime.now(UTC) - timedelta(hours=1),
            reschedule_requested_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        session.add(
            models.RescheduleRequest(
                slot_assignment_id=assignment.id,
                requested_start_utc=target_start,
                requested_tz="Europe/Moscow",
                status=models.RescheduleRequestStatus.PENDING,
            )
        )
        await session.commit()
        current_slot_id = current_slot.id
        reusable_slot_id = reusable_slot.id
        assignment_id = assignment.id

    response = await _async_request_with_csrf(
        admin_slots_app,
        "post",
        f"/api/slots/{current_slot_id}/reschedule",
        json={"date": "2031-06-01", "time": "13:00"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Слот перенесён" in payload["message"]

    async with async_session() as session:
        old_slot = await session.get(models.Slot, current_slot_id)
        target_slot = await session.get(models.Slot, reusable_slot_id)
        assignment = await session.get(models.SlotAssignment, assignment_id)

        assert old_slot is not None
        assert old_slot.status == models.SlotStatus.FREE
        assert old_slot.candidate_id is None
        assert old_slot.candidate_tg_id is None

        assert target_slot is not None
        assert target_slot.status == models.SlotStatus.PENDING
        assert target_slot.candidate_id == candidate.candidate_id
        assert target_slot.candidate_tg_id == candidate.telegram_id

        assert assignment is not None
        assert assignment.slot_id == reusable_slot_id
        assert assignment.status == models.SlotAssignmentStatus.OFFERED
        assert assignment.reschedule_requested_at is None


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

    calls: dict[str, int] = {"count": 0}

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

    calls: dict[str, int] = {"count": 0}

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
            start_utc=datetime.now(UTC) + timedelta(hours=2),
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
            start_utc=datetime.now(UTC) + timedelta(hours=3),
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
async def test_api_slot_book_duplicate_candidate_returns_conflict(admin_slots_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=88001,
        fio="Дубль Кандидат",
        city="Москва",
        username="duplicate_candidate",
    )

    async with async_session() as session:
        recruiter = models.Recruiter(name="Duplicate Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name="Duplicate City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        now = datetime.now(UTC)
        occupied_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(hours=2),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz=city.tz,
            candidate_city_id=city.id,
        )
        target_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(hours=3),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([occupied_slot, target_slot])
        await session.commit()
        await session.refresh(occupied_slot)
        await session.refresh(target_slot)
        occupied_slot_id = occupied_slot.id
        target_slot_id = target_slot.id

    response = await _async_request_with_csrf(
        admin_slots_app,
        "post",
        f"/api/slots/{target_slot_id}/book",
        json={
            "candidate_tg_id": candidate.telegram_id,
            "candidate_fio": candidate.fio,
        },
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "candidate_already_booked"
    assert int(payload["existing_slot_id"]) == occupied_slot_id

    async with async_session() as session:
        target_slot = await session.get(models.Slot, target_slot_id)
        assert target_slot is not None
        assert target_slot.status == models.SlotStatus.FREE
        assert target_slot.candidate_tg_id is None


@pytest.mark.asyncio
async def test_api_slot_book_maps_integrity_error_to_conflict(admin_slots_app, monkeypatch) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=88011,
        fio="Конфликтный Кандидат",
        city="Москва",
    )

    async with async_session() as session:
        recruiter = models.Recruiter(name="Integrity Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name="Integrity City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(city)
        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(UTC) + timedelta(hours=4),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    async def _raise_integrity(*args, **kwargs):
        raise IntegrityError("duplicate", params={}, orig=Exception("dup"))

    monkeypatch.setattr("backend.apps.admin_ui.routers.api.reserve_domain_slot", _raise_integrity)

    response = await _async_request_with_csrf(
        admin_slots_app,
        "post",
        f"/api/slots/{slot_id}/book",
        json={
            "candidate_tg_id": candidate.telegram_id,
            "candidate_fio": candidate.fio,
        },
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "candidate_already_booked"


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
    with TestClient(app) as client:
        _login(client)
        response = client.get("/health/bot")
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
            start_utc=datetime(2024, 1, 1, 6, 0, tzinfo=UTC),
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


@pytest.mark.asyncio
async def test_api_slots_defaults_to_latest_first(admin_slots_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(name="Sort Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name="Sort City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        early = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime(2024, 1, 1, 8, 0, tzinfo=UTC),
            status=models.SlotStatus.FREE,
            tz_name=city.tz,
        )
        late = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            status=models.SlotStatus.FREE,
            tz_name=city.tz,
        )
        session.add_all([early, late])
        await session.commit()

        recruiter_id = recruiter.id

    response = await _async_request(
        admin_slots_app,
        "get",
        "/api/slots",
        params={"limit": 10, "recruiter_id": str(recruiter_id)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 2
    assert payload[0]["start_utc"] >= payload[1]["start_utc"]


@pytest.mark.asyncio
async def test_api_slots_bulk_create_returns_created_count(admin_slots_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(name="Bulk API Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name="Bulk API City", tz="Asia/Almaty", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        recruiter_id = recruiter.id
        city_id = city.id

    target_day = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    response = await _async_request_with_csrf(
        admin_slots_app,
        "post",
        "/api/slots/bulk_create",
        json={
            "recruiter_id": recruiter_id,
            "city_id": city_id,
            "start_date": target_day,
            "end_date": target_day,
            "start_time": "10:00",
            "end_time": "11:00",
            "break_start": "00:00",
            "break_end": "00:10",
            "step_min": 30,
            "include_weekends": True,
            "use_break": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["created"] == 2
