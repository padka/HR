import pytest
from datetime import datetime, timezone

from sqlalchemy import select, update, delete

from backend.apps.bot.template_provider import TemplateProvider
from backend.core.db import async_session
from backend.domain.models import MessageTemplate


@pytest.mark.asyncio
async def test_template_lookup_and_invalidation():
    async with async_session() as session:
        template = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == "interview_confirmed_candidate",
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
                MessageTemplate.is_active.is_(True),
            )
        )
        if template is None:
            template = MessageTemplate(
                key="interview_confirmed_candidate",
                locale="ru",
                channel="tg",
                body_md="Базовый текст для {candidate_name}",
                version=1,
                is_active=True,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
        original_body = template.body_md
        baseline_body = "Оригинальный текст для {candidate_name}"
        await session.execute(
            update(MessageTemplate)
            .where(MessageTemplate.id == template.id)
            .values(body_md=baseline_body, updated_at=datetime.now(timezone.utc))
        )
        await session.commit()
    provider = TemplateProvider(cache_ttl=60)
    context = {
        "candidate_name": "Иван",
        "recruiter_name": "Анна",
        "dt_local": "01.02 10:00 (по вашему времени)",
        "tz_name": "Europe/Moscow",
        "join_link": "https://example.com",
    }

    initial = await provider.render("interview_confirmed_candidate", context)
    assert initial is not None
    assert initial.text == baseline_body.replace("{candidate_name}", context["candidate_name"])

    async with async_session() as session:
        await session.execute(
            update(MessageTemplate)
            .where(MessageTemplate.key == "interview_confirmed_candidate")
            .where(MessageTemplate.locale == "ru")
            .where(MessageTemplate.channel == "tg")
            .values(
                body_md="Новый текст для {candidate_name}",
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    cached = await provider.render("interview_confirmed_candidate", context)
    assert cached is not None
    assert cached.text == initial.text

    await provider.invalidate(key="interview_confirmed_candidate")
    updated = await provider.render("interview_confirmed_candidate", context)
    assert updated is not None
    assert updated.text != initial.text
    assert "Новый текст" in updated.text

    async with async_session() as session:
        await session.execute(
            update(MessageTemplate)
            .where(MessageTemplate.key == "interview_confirmed_candidate")
            .where(MessageTemplate.locale == "ru")
            .where(MessageTemplate.channel == "tg")
            .values(body_md=original_body, updated_at=datetime.now(timezone.utc))
        )
        await session.commit()


@pytest.mark.asyncio
async def test_template_provider_fallback_for_missing_template():
    async with async_session() as session:
        await session.execute(
            delete(MessageTemplate).where(
                MessageTemplate.key == "candidate_rejection",
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        await session.commit()

    provider = TemplateProvider(cache_ttl=1)
    context = {
        "candidate_name": "Иван",
        "dt_local": "01.02 12:00",
        "slot_datetime_local": "01.02 12:00",
        "slot_time_local": "12:00",
        "slot_date_local": "01.02",
        "recruiter_name": "Анна",
        "join_link": "",
    }
    rendered = await provider.render("candidate_rejection", context)
    assert rendered is not None
    assert rendered.text.strip()
