from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from backend.apps.bot import services
from backend.core.db import async_session
from backend.domain.models import MessageTemplate, Slot, SlotStatus


@pytest.mark.asyncio
async def test_intro_day_template_defaults_without_city_specific():
    key = "intro_day_invitation"
    async with async_session() as session:
        await session.execute(delete(MessageTemplate).where(MessageTemplate.key == key))
        session.add(
            MessageTemplate(
                key=key,
                locale="ru",
                channel="tg",
                city_id=None,
                body_md="default-intro",
                version=1,
                is_active=True,
                updated_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    provider = services.get_template_provider()
    rendered = await provider.render(key, {}, city_id=123, strict=True)

    assert rendered is not None
    assert rendered.text == "default-intro"
    assert rendered.city_id is None


@pytest.mark.asyncio
async def test_intro_day_template_prefers_city_specific():
    key = "intro_day_invitation"
    city_id = 777
    async with async_session() as session:
        await session.execute(delete(MessageTemplate).where(MessageTemplate.key == key))
        now = datetime.now(timezone.utc)
        session.add(
            MessageTemplate(
                key=key,
                locale="ru",
                channel="tg",
                city_id=None,
                body_md="default-intro",
                version=1,
                is_active=True,
                updated_at=now,
                created_at=now,
            )
        )
        session.add(
            MessageTemplate(
                key=key,
                locale="ru",
                channel="tg",
                city_id=city_id,
                body_md="city-intro",
                version=1,
                is_active=True,
                updated_at=now,
                created_at=now,
            )
        )
        await session.commit()

    provider = services.get_template_provider()
    rendered = await provider.render(key, {}, city_id=city_id, strict=True)

    assert rendered is not None
    assert rendered.text == "city-intro"
    assert rendered.city_id == city_id


def _build_slot(*, purpose: str = "intro_day") -> Slot:
    return Slot(
        recruiter_id=1,
        city_id=1,
        start_utc=datetime.now(timezone.utc) + timedelta(hours=1),
        duration_min=60,
        status=SlotStatus.BOOKED,
        purpose=purpose,
        tz_name="Europe/Moscow",
        candidate_tg_id=101,
        candidate_fio="Тест Кандидат",
        candidate_tz="Europe/Moscow",
    )


@pytest.mark.asyncio
async def test_render_candidate_notification_uses_intro_template(monkeypatch):
    slot = _build_slot(purpose="intro_day")
    slot.intro_address = "г. Казань, ул. Центральная, 1"
    slot.intro_contact = "HR Контакт"

    calls = []

    class DummyProvider:
        async def render(self, key, context, locale="ru", channel="tg", city_id=None, strict=False):
            calls.append(key)
            return SimpleNamespace(text=f"{key}:{context['candidate_name']}", key=key, version=1)

    monkeypatch.setattr(services, "get_template_provider", lambda: DummyProvider())

    text, tz, city_name, template_key, version = await services._render_candidate_notification(slot)

    assert calls == ["intro_day_invitation"]
    assert template_key == "intro_day_invitation"
    assert "intro_day_invitation" in text
    assert tz == "Europe/Moscow"
    assert version == 1
    assert city_name == ""


@pytest.mark.asyncio
async def test_render_candidate_notification_for_interview(monkeypatch):
    slot = _build_slot(purpose="interview")

    calls = []

    class DummyProvider:
        async def render(self, key, context, locale="ru", channel="tg", city_id=None, strict=False):
            calls.append(key)
            return SimpleNamespace(text=f"{key}:{context['candidate_name']}", key=key, version=2)

    monkeypatch.setattr(services, "get_template_provider", lambda: DummyProvider())

    text, _, _, template_key, version = await services._render_candidate_notification(slot)

    assert calls == ["interview_confirmed_candidate"]
    assert template_key == "interview_confirmed_candidate"
    assert "interview_confirmed_candidate" in text
    assert version == 2
