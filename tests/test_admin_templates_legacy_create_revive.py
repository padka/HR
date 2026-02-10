import pytest

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.models import City, MessageTemplate


@pytest.mark.asyncio
async def test_legacy_templates_create_revives_inactive_template(monkeypatch):
    # Avoid touching Telegram/redis/etc during app startup.
    monkeypatch.setattr(
        "backend.apps.admin_ui.state._build_bot",
        lambda settings: (None, False),
    )

    app = create_app()

    async with async_session() as session:
        city = City(name="Екатеринбург", tz="Asia/Yekaterinburg", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

        existing = MessageTemplate(
            key="candidate_rejection",
            locale="ru",
            channel="tg",
            body_md="old body",
            version=1,
            is_active=False,
            city_id=city.id,
            updated_by="admin",
        )
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        existing_id = existing.id

    from httpx import AsyncClient, ASGITransport
    from backend.core.settings import get_settings

    settings = get_settings()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=(settings.admin_username or "admin", settings.admin_password or "admin"),
    ) as client:
        response = await client.post(
            "/api/templates",
            json={
                "key": "candidate_rejection",
                "text": "new body",
                "city_id": city.id,
                "locale": "ru",
                "channel": "tg",
                "version": 1,
                "is_active": True,
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["id"] == existing_id
    assert payload["revived"] is True

    async with async_session() as session:
        revived = await session.get(MessageTemplate, existing_id)
        assert revived is not None
        assert revived.is_active is True
        assert revived.body_md == "new body"

