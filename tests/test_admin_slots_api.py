import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.services import slots as slot_services
from backend.apps.admin_ui.services.bot_service import BotSendResult, BotService, configure_bot_service
from backend.core.db import async_session
from backend.domain import models


def _force_ready_bot(monkeypatch) -> None:
    def _fake_build(settings):
        return None, True

    monkeypatch.setattr("backend.apps.admin_ui.state._build_bot", _fake_build)


async def _create_booked_slot() -> Tuple[int, int]:
    async with async_session() as session:
        recruiter = models.Recruiter(name="API", tz="Europe/Moscow", active=True)
        city = models.City(name="API City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
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


async def _async_request(
    app,
    method: str,
    path: str,
    *,
    before_request: Optional[Callable[[Any], None]] = None,
    **kwargs,
) -> Any:
    def _call() -> Any:
        with TestClient(app) as client:
            if before_request is not None:
                before_request(client.app)
            response = client.request(method, path, **kwargs)
            return response

    return await asyncio.to_thread(_call)


@pytest.fixture(autouse=True)
def clear_state_manager():
    try:
        state_manager = slot_services.get_state_manager()
    except RuntimeError:
        yield
        return
    state_manager.clear()
    yield
    state_manager.clear()


@pytest.mark.asyncio
async def test_slot_outcome_endpoint_uses_state_manager(monkeypatch):
    from backend.apps.admin_ui.state import BotIntegration
    from backend.apps.bot.services import StateManager, configure as configure_bot_services

    slot_id, candidate_id = await _create_booked_slot()

    started: Dict[str, Any] = {}

    async def fake_start_test2(user_id: int) -> None:
        started["user_id"] = user_id

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.bot_service.start_test2",
        fake_start_test2,
    )

    def fake_setup_bot_state(app):
        state_manager = StateManager()
        configure_bot_services(None, state_manager)
        service = BotService(
            state_manager=state_manager,
            enabled=True,
            configured=True,
            required=False,
        )
        configure_bot_service(service)
        app.state.bot = None
        app.state.state_manager = state_manager
        app.state.bot_service = service
        return BotIntegration(state_manager=state_manager, bot=None, bot_service=service)

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

    state = slot_services.get_state_manager().get(candidate_id)
    assert state is not None
    assert state.get("flow") == "intro"
    assert started.get("user_id") == candidate_id

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.interview_outcome == "success"
        assert updated.test2_sent_at is not None


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
async def test_health_check_reports_ok():
    app = create_app()
    response = await _async_request(app, "get", "/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["state_manager"] == "ok"
    assert payload["checks"]["bot_client"] in {"ready", "unconfigured", "disabled", "missing"}


@pytest.mark.asyncio
async def test_bot_health_endpoint_reports_status(monkeypatch):
    app = create_app()
    response = await _async_request(app, "get", "/health/bot")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"enabled", "ready", "mode"}
    assert payload["mode"] in {"real", "null"}
