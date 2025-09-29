from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.apps.bot.services import handle_recruiter_identity_command
from backend.core.db import async_session
from backend.domain import models
from backend.domain.repositories import (
    approve_slot,
    get_active_recruiters,
    get_active_recruiters_for_city,
    get_candidate_cities,
    get_city,
    get_city_by_name,
    get_free_slots_by_recruiter,
    get_recruiter,
    get_slot,
    get_template,
    reserve_slot,
    reject_slot,
    set_recruiter_chat_id_by_command,
)


@pytest.mark.asyncio
async def test_recruiter_and_city_queries():
    async with async_session() as session:
        recruiter_active = models.Recruiter(name="Михаил", tz="Europe/Moscow", active=True)
        recruiter_inactive = models.Recruiter(name="Иван", tz="Europe/Moscow", active=False)
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        session.add_all([recruiter_active, recruiter_inactive, city])
        await session.commit()
        await session.refresh(recruiter_active)
        await session.refresh(recruiter_inactive)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter_active.id
        await session.commit()

    active = await get_active_recruiters()
    assert [r.name for r in active] == ["Михаил"]

    by_city = await get_active_recruiters_for_city(city.id)
    assert [r.name for r in by_city] == ["Михаил"]

    fetched = await get_recruiter(recruiter_active.id)
    assert fetched is not None
    assert fetched.name == "Михаил"

    city_by_name = await get_city_by_name("Москва")
    assert city_by_name is not None
    assert city_by_name.id == city.id

    city_by_id = await get_city(city.id)
    assert city_by_id.name == "Москва"


@pytest.mark.asyncio
async def test_city_recruiter_lookup_includes_slot_owners():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        responsible = models.Recruiter(name="Ответственный", tz="Europe/Moscow", active=True)
        extra = models.Recruiter(name="Помощник", tz="Europe/Moscow", active=True)
        city = models.City(name="Казань", tz="Europe/Moscow", active=True)
        session.add_all([responsible, extra, city])
        await session.commit()
        await session.refresh(responsible)
        await session.refresh(extra)
        await session.refresh(city)

        city.responsible_recruiter_id = responsible.id

        session.add(
            models.Slot(
                recruiter_id=extra.id,
                city_id=city.id,
                start_utc=now + timedelta(hours=2),
                status=models.SlotStatus.FREE,
            )
        )

        await session.commit()

    recruiters = await get_active_recruiters_for_city(city.id)
    names = {r.name for r in recruiters}
    assert names == {"Ответственный", "Помощник"}


@pytest.mark.asyncio
async def test_candidate_city_lookup_includes_responsible_and_slot_cities():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        resp_active = models.Recruiter(name="Координатор", tz="Europe/Moscow", active=True)
        resp_inactive = models.Recruiter(name="Неактивен", tz="Europe/Moscow", active=False)
        slot_owner = models.Recruiter(name="Слотер", tz="Europe/Moscow", active=True)

        city_resp = models.City(name="Екатеринбург", tz="Asia/Yekaterinburg", active=True)
        city_slot = models.City(name="Самара", tz="Europe/Samara", active=True)
        city_inactive = models.City(name="Томск", tz="Asia/Tomsk", active=True)

        session.add_all([resp_active, resp_inactive, slot_owner, city_resp, city_slot, city_inactive])
        await session.commit()

        await session.refresh(resp_active)
        await session.refresh(resp_inactive)
        await session.refresh(slot_owner)
        await session.refresh(city_resp)
        await session.refresh(city_slot)
        await session.refresh(city_inactive)

        city_resp.responsible_recruiter_id = resp_active.id
        city_slot.responsible_recruiter_id = resp_inactive.id

        session.add(
            models.Slot(
                recruiter_id=slot_owner.id,
                city_id=city_slot.id,
                start_utc=now + timedelta(hours=3),
                status=models.SlotStatus.FREE,
            )
        )

        session.add(
            models.Slot(
                recruiter_id=resp_inactive.id,
                city_id=city_inactive.id,
                start_utc=now + timedelta(hours=4),
                status=models.SlotStatus.FREE,
            )
        )

        await session.commit()

    cities = await get_candidate_cities()
    names = [city.name for city in cities]

    assert names == ["Екатеринбург", "Самара"]


@pytest.mark.asyncio
async def test_slot_workflow_and_templates():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Мария", tz="Europe/Moscow", active=True)
        city = models.City(name="Санкт-Петербург", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()

        slot_free = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=4),
            status=models.SlotStatus.FREE,
        )
        slot_pending = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=5),
            status=models.SlotStatus.PENDING,
        )
        session.add_all([slot_free, slot_pending])

        template_city = models.Template(city_id=city.id, key="invite", content="hello")
        template_global = models.Template(city_id=None, key="invite", content="global")
        session.add_all([template_city, template_global])
        await session.commit()
        await session.refresh(slot_free)
        await session.refresh(slot_pending)

    free_slots = await get_free_slots_by_recruiter(recruiter.id, now_utc=now)
    assert len(free_slots) == 1
    assert free_slots[0].id == slot_free.id

    filtered_slots = await get_free_slots_by_recruiter(
        recruiter.id, now_utc=now, city_id=city.id
    )
    assert [s.id for s in filtered_slots] == [slot_free.id]

    reserved = await reserve_slot(
        slot_free.id,
        candidate_tg_id=999,
        candidate_fio="Кандидат",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
    )
    assert reserved is not None
    assert reserved.status == models.SlotStatus.PENDING
    assert reserved.candidate_city_id == city.id

    approved = await approve_slot(slot_free.id)
    assert approved is not None
    assert approved.status == models.SlotStatus.BOOKED

    rejected = await reject_slot(slot_free.id)
    assert rejected is not None
    assert rejected.status == models.SlotStatus.FREE
    assert rejected.candidate_tg_id is None

    not_reserved = await reserve_slot(12345, candidate_tg_id=1, candidate_fio="", candidate_tz="", candidate_city_id=None)
    assert not_reserved is None

    slot_loaded = await get_slot(slot_pending.id)
    assert slot_loaded is not None
    assert slot_loaded.status == models.SlotStatus.PENDING

    tmpl = await get_template(city.id, "invite")
    assert tmpl is not None
    assert tmpl.content == "hello"

    not_found = await get_template(city.id, "missing")
    assert not_found is None

    updated = await set_recruiter_chat_id_by_command("Мария", chat_id=123456)
    assert updated is not None
    assert updated.tg_chat_id == 123456

    again = await set_recruiter_chat_id_by_command("unknown", chat_id=1)
    assert again is None


@pytest.mark.asyncio
async def test_iam_command_updates_recruiter_chat_id():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Софья", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    responses = []

    class DummyMessage:
        def __init__(self, text: str, chat_id: int) -> None:
            self.text = text
            self.chat = SimpleNamespace(id=chat_id)
            self.from_user = SimpleNamespace(id=chat_id)

        async def answer(self, text: str, **kwargs) -> None:
            responses.append(text)

    message = DummyMessage("/iam Софья", chat_id=987654321)

    await handle_recruiter_identity_command(message)

    async with async_session() as session:
        updated = await session.get(models.Recruiter, recruiter_id)
        assert updated is not None
        assert updated.tg_chat_id == 987654321

    assert any("Готово" in resp for resp in responses)
