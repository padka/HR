import pytest

from backend.apps.admin_ui.services.message_templates import (
    build_preview_context,
    create_message_template,
    delete_message_template,
)
from backend.core.db import async_session
from backend.domain.models import City


@pytest.mark.asyncio
async def test_template_validation_rejects_unclosed_tag():
    ok, errors, template = await create_message_template(
        key="test_invalid",
        locale="ru",
        channel="tg",
        body="<b>Привет",
        is_active=True,
        version=1,
    )
    assert not ok
    assert any("не закрыт" in err.lower() for err in errors)
    assert template is None


@pytest.mark.asyncio
async def test_template_validation_accepts_valid_html():
    ok, errors, template = await create_message_template(
        key="test_valid",
        locale="ru",
        channel="tg",
        body="<b>Привет</b> <i>Мир</i><br>",
        is_active=True,
        version=1,
    )
    assert ok, errors
    assert template is not None

    # cleanup
    await delete_message_template(template.id)


@pytest.mark.asyncio
async def test_preview_context_uses_city_intro_details_for_intro_templates():
    async with async_session() as session:
        city = City(
            name="Алматы",
            active=True,
            intro_address="пр. Достык, 12",
            contact_name="Муса",
            contact_phone="+7 777 000 11 22",
        )
        session.add(city)
        await session.commit()
        await session.refresh(city)
        city_id = city.id

    try:
        ctx = await build_preview_context(key="intro_day_invitation", city_id=city_id)
        assert ctx["city_name"] == "Алматы"
        assert ctx["intro_address"] == "пр. Достык, 12"
        assert ctx["address"] == "пр. Достык, 12"
        assert ctx["recruiter_name"] == "Муса"
        assert ctx["recruiter_phone"] == "+7 777 000 11 22"
        assert ctx["intro_contact"] == "Муса, +7 777 000 11 22"
    finally:
        async with async_session() as session:
            city = await session.get(City, city_id)
            if city is not None:
                await session.delete(city)
                await session.commit()
