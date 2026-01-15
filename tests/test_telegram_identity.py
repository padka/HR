import pytest
from types import SimpleNamespace
from sqlalchemy import select

from backend.apps.bot.middleware import TelegramIdentityMiddleware
from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import User


@pytest.mark.asyncio
async def test_middleware_creates_candidate_with_telegram_identity():
    middleware = TelegramIdentityMiddleware()
    event = SimpleNamespace(from_user=SimpleNamespace(id=99887766, username="test_candidate"))

    async def handler(event_obj, data):
        return True

    await middleware(handler, event, {})

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == 99887766))
        assert user is not None
        assert user.telegram_user_id == 99887766
        assert user.telegram_username == "test_candidate"
        assert user.username == "test_candidate"
        assert user.fio == "TG 99887766"
        assert user.telegram_linked_at is not None


@pytest.mark.asyncio
async def test_identity_update_preserves_link_timestamp():
    tg_id = 1234512345
    user = await candidate_services.create_or_update_user(
        telegram_id=tg_id,
        fio="Test User",
        city="Москва",
        username=None,
    )
    linked_at = user.telegram_linked_at

    await candidate_services.link_telegram_identity(tg_id, username="updated_name")

    async with async_session() as session:
        refreshed = await session.scalar(select(User).where(User.telegram_id == tg_id))
        assert refreshed.telegram_username == "updated_name"
        assert refreshed.username == "updated_name"
        assert refreshed.telegram_linked_at == linked_at
