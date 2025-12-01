import pytest
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete

from backend.apps.bot.template_provider import TemplateProvider, TemplateResolutionError
from backend.core.db import async_session
from backend.domain.models import City, MessageTemplate


async def _cleanup_template(key: str) -> None:
    async with async_session() as session:
        await session.execute(delete(MessageTemplate).where(MessageTemplate.key == key))
        await session.commit()


@pytest.mark.asyncio
async def test_city_template_overrides_default():
    key = "intro_day_invitation"
    await _cleanup_template(key)
    async with async_session() as session:
        city = City(name=f"Тестоград-{uuid.uuid4().hex}", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.flush()
        city_id = city.id
        now = datetime.now(timezone.utc)
        session.add(
            MessageTemplate(
                key=key,
                locale="ru",
                channel="tg",
                city_id=None,
                body_md="default-template",
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
                body_md="city-template",
                version=1,
                is_active=True,
                updated_at=now,
                created_at=now,
            )
        )
        await session.commit()

    provider = TemplateProvider(cache_ttl=1)
    rendered = await provider.render(key, {}, city_id=city_id, strict=True)

    assert rendered is not None
    assert rendered.text == "city-template"
    assert rendered.city_id == city_id


@pytest.mark.asyncio
async def test_template_falls_back_to_default_when_city_missing():
    key = "confirm_6h"
    await _cleanup_template(key)
    async with async_session() as session:
        city = City(name=f"Fallback City-{uuid.uuid4().hex}", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.flush()
        city_id = city.id
        now = datetime.now(timezone.utc)
        session.add(
            MessageTemplate(
                key=key,
                locale="ru",
                channel="tg",
                city_id=None,
                body_md="base-default",
                version=1,
                is_active=True,
                updated_at=now,
                created_at=now,
            )
        )
        await session.commit()

    provider = TemplateProvider(cache_ttl=1)
    rendered = await provider.render(key, {}, city_id=city_id, strict=True)

    assert rendered is not None
    assert rendered.text == "base-default"
    assert rendered.city_id is None


@pytest.mark.asyncio
async def test_missing_template_raises_friendly_error():
    key = "missing_city_template"
    await _cleanup_template(key)
    provider = TemplateProvider(cache_ttl=1)
    with pytest.raises(TemplateResolutionError):
        await provider.render(key, {}, city_id=None, strict=True)
