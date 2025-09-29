from datetime import datetime, timezone

import pytest

pytest.importorskip("sqlalchemy")

from backend.apps.admin_ui.services import slots as slot_services
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_set_slot_outcome_triggers_test2(monkeypatch):
    async with async_session() as session:
        recruiter = models.Recruiter(name="Outcome", tz="Europe/Moscow", active=True)
        city = models.City(name="Outcome City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
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
        return True, None, None

    monkeypatch.setattr(slot_services, "_send_test2", fake_send)

    ok, message, stored = await slot_services.set_slot_outcome(slot_id, "passed")
    assert ok is True
    assert stored == "passed"
    assert "отправлен" in (message or "").lower()
    assert calls["args"] == (5555, "Europe/Moscow", city_id, "Иван Тест")

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.interview_outcome == "passed"


@pytest.mark.asyncio
async def test_set_slot_outcome_validates_choice():
    ok, message, stored = await slot_services.set_slot_outcome(9999, "maybe")
    assert ok is False
    assert stored is None
    assert "Некорректный исход" in (message or "")


@pytest.mark.asyncio
async def test_set_slot_outcome_requires_candidate():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Empty", tz="Europe/Moscow", active=True)
        city = models.City(name="No Candidate", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
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

    ok, message, stored = await slot_services.set_slot_outcome(slot_id, "failed")
    assert ok is False
    assert stored is None
    assert "Слот не привязан к кандидату" in (message or "")
