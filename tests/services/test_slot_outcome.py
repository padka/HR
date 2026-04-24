from datetime import datetime, timezone
import importlib

import pytest
from sqlalchemy import select

pytest.importorskip("sqlalchemy")

from backend.apps.admin_ui.services import slots as slot_services
from backend.apps.admin_ui.services.bot_service import (
    BotSendResult,
    BotService,
    IntegrationSwitch,
)
from backend.core.messenger.protocol import SendResult
from backend.apps.bot.state_store import build_state_manager
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus


@pytest.mark.asyncio
async def test_set_slot_outcome_triggers_test2(monkeypatch):
    async with async_session() as session:
        recruiter = models.Recruiter(name="Outcome", tz="Europe/Moscow", active=True)
        city = models.City(name="Outcome City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city_id = city.id

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=5555,
            candidate_fio="Иван Тест",
            candidate_tz="Europe/Moscow",
            candidate_city_id=city_id,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    calls = {}

    async def fake_send(candidate_id, candidate_tz, candidate_city, candidate_name, **_):
        calls["args"] = (candidate_id, candidate_tz, candidate_city, candidate_name)
        return BotSendResult(ok=True, status="sent")

    monkeypatch.setattr(slot_services, "_trigger_test2", fake_send)

    state_manager = build_state_manager(redis_url=None, ttl_seconds=604800)
    service = BotService(
        state_manager=state_manager,
        enabled=True,
        configured=True,
        integration_switch=IntegrationSwitch(initial=True),
        required=False,
    )

    ok, message, stored, dispatch = await slot_services.set_slot_outcome(
        slot_id,
        "success",
        bot_service=service,
    )
    assert ok is True
    assert stored == "success"
    assert "отправлен" in (message or "").lower()
    assert dispatch is not None
    assert dispatch.status == "sent_test2"
    assert dispatch.plan is not None
    assert dispatch.plan.candidate_id == 5555
    assert dispatch.plan.candidate_tz == "Europe/Moscow"
    assert dispatch.plan.candidate_city_id == city_id
    assert dispatch.plan.candidate_name == "Иван Тест"
    assert dispatch.plan.required is True

    await slot_services.execute_bot_dispatch(dispatch.plan, stored or "", service)

    await state_manager.clear()
    await state_manager.close()

    assert calls["args"] == (5555, "Europe/Moscow", city_id, "Иван Тест")

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.interview_outcome == "success"
        assert updated.test2_sent_at is not None


@pytest.mark.asyncio
async def test_set_slot_outcome_triggers_test2_for_max_only_candidate(monkeypatch):
    async with async_session() as session:
        recruiter = models.Recruiter(name="Outcome MAX", tz="Europe/Moscow", active=True)
        city = models.City(name="Outcome MAX City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        candidate = User(
            candidate_id="cand-max-outcome",
            fio="MAX Outcome Candidate",
            city="Outcome MAX City",
            is_active=True,
            max_user_id="max-user-outcome",
            messenger_platform="max",
            candidate_status=CandidateStatus.INTERVIEW_CONFIRMED,
        )
        session.add_all([recruiter, city, candidate])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.BOOKED,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=None,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    calls = {}

    async def fake_send(candidate_id, candidate_tz, candidate_city, candidate_name, **kwargs):
        calls["args"] = (candidate_id, candidate_tz, candidate_city, candidate_name)
        calls["kwargs"] = kwargs
        return BotSendResult(ok=True, status="sent")

    monkeypatch.setattr(slot_services, "_trigger_test2", fake_send)

    state_manager = build_state_manager(redis_url=None, ttl_seconds=604800)
    service = BotService(
        state_manager=state_manager,
        enabled=True,
        configured=True,
        integration_switch=IntegrationSwitch(initial=True),
        required=False,
    )

    ok, message, stored, dispatch = await slot_services.set_slot_outcome(
        slot_id,
        "success",
        bot_service=service,
    )
    assert ok is True
    assert stored == "success"
    assert "отправлен" in (message or "").lower()
    assert dispatch is not None
    assert dispatch.status == "sent_test2"
    assert dispatch.plan is not None
    assert dispatch.plan.candidate_id == 0
    assert dispatch.plan.candidate_public_id == "cand-max-outcome"
    assert dispatch.plan.candidate_tz == "Europe/Moscow"
    assert dispatch.plan.candidate_name == "MAX Outcome Candidate"
    assert dispatch.plan.required is True

    await slot_services.execute_bot_dispatch(dispatch.plan, stored or "", service)

    await state_manager.clear()
    await state_manager.close()

    assert calls["args"] == (0, "Europe/Moscow", city.id, "MAX Outcome Candidate")
    assert calls["kwargs"]["candidate_public_id"] == "cand-max-outcome"
    assert calls["kwargs"]["max_user_id"] is None

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.interview_outcome == "success"
        assert updated.test2_sent_at is not None


@pytest.mark.asyncio
async def test_set_slot_outcome_validates_choice():
    ok, message, stored, dispatch = await slot_services.set_slot_outcome(9999, "maybe")
    assert ok is False
    assert stored is None
    assert "Некорректный исход" in (message or "")
    assert dispatch is None


@pytest.mark.asyncio
async def test_set_slot_outcome_requires_candidate():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Empty", tz="Europe/Moscow", active=True)
        city = models.City(name="No Candidate", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city_id = city.id

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city_id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.BOOKED,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    ok, message, stored, dispatch = await slot_services.set_slot_outcome(slot_id, "reject")
    assert ok is False
    assert stored is None
    assert "Слот не привязан к кандидату" in (message or "")
    assert dispatch is None


@pytest.mark.asyncio
async def test_approve_slot_booking_allows_max_only_candidate():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Approve MAX", tz="Europe/Moscow", active=True)
        city = models.City(name="MAX City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        candidate = User(
            candidate_id="cand-max-approve",
            fio="MAX Candidate",
            city="MAX City",
            is_active=True,
            max_user_id="max-user-approve",
            messenger_platform="max",
            candidate_status=CandidateStatus.SLOT_PENDING,
        )
        session.add_all([recruiter, city, candidate])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.PENDING,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=None,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = int(slot.id)

    ok, message, notified = await slot_services.approve_slot_booking(slot_id)

    assert ok is True
    assert "слот подтверждён" in (message or "").lower()

    async with async_session() as session:
        refreshed_slot = await session.get(models.Slot, slot_id)
        refreshed_candidate = await session.scalar(
            select(User).where(User.candidate_id == "cand-max-approve")
        )

    assert refreshed_slot is not None
    assert refreshed_slot.status == models.SlotStatus.BOOKED
    assert refreshed_candidate is not None
    assert refreshed_candidate.candidate_status == CandidateStatus.INTERVIEW_SCHEDULED


@pytest.mark.asyncio
async def test_approve_slot_booking_bootstraps_max_delivery_when_notification_runtime_is_off(
    monkeypatch,
):
    class _DummyAdapter:
        def __init__(self) -> None:
            self.calls = []

        async def send_message(
            self,
            chat_id,
            text,
            *,
            buttons=None,
            parse_mode=None,
            correlation_id=None,
        ):
            self.calls.append(
                {
                    "chat_id": chat_id,
                    "text": text,
                    "buttons": buttons,
                    "parse_mode": parse_mode,
                    "correlation_id": correlation_id,
                }
            )
            return SendResult(success=True, message_id="max-approval-1")

    adapter = _DummyAdapter()

    async with async_session() as session:
        recruiter = models.Recruiter(name="Approve MAX Direct", tz="Europe/Moscow", active=True)
        city = models.City(name="MAX Direct City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        candidate = User(
            candidate_id="cand-max-direct",
            fio="MAX Direct Candidate",
            city="MAX Direct City",
            is_active=True,
            max_user_id="max-user-direct",
            messenger_platform="max",
            candidate_status=CandidateStatus.SLOT_PENDING,
        )
        session.add_all([recruiter, city, candidate])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            status=models.SlotStatus.PENDING,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=None,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = int(slot.id)

    def _missing_notification_service():
        raise RuntimeError("Notification service is not configured")

    bot_module = importlib.import_module("backend.apps.admin_ui.services._slots_bot")
    monkeypatch.setattr(bot_module, "get_notification_service", _missing_notification_service)

    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(
        "backend.apps.bot.services.notification_flow.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )

    ok, message, notified = await slot_services.approve_slot_booking(slot_id)

    assert ok is True
    assert notified is True
    assert "кандидату отправлено уведомление" in (message or "").lower()
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["chat_id"] == "max-user-direct"
    assert "встречу предварительно подтвердили" in str(adapter.calls[0]["text"]).lower()


@pytest.mark.asyncio
async def test_send_rejection_reports_unconfigured_bot():
    state_manager = build_state_manager(redis_url=None, ttl_seconds=604800)
    service = BotService(
        state_manager=state_manager,
        enabled=True,
        configured=False,
        integration_switch=IntegrationSwitch(initial=True),
        required=False,
    )

    result = await service.send_rejection(
        123,
        city_id=None,
        template_key="dummy",
        context={},
    )

    assert result.ok is False
    assert result.status == "skipped:not_configured"
    assert result.error == service.rejection_failure_message

    await state_manager.clear()
    await state_manager.close()
