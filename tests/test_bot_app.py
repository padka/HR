import asyncio

import pytest

from backend.apps.bot import app as bot_app


class DummySettings:
    def __init__(self, base: str) -> None:
        self.bot_api_base = base


def test_create_bot_uses_custom_api_base(monkeypatch):
    base_url = "https://example.invalid"
    monkeypatch.setattr(bot_app, "get_settings", lambda: DummySettings(base_url))

    bot = bot_app.create_bot(token="123:ABC")

    try:
        assert bot.session.api.base == base_url
    finally:
        asyncio.run(bot.session.close())


def test_create_bot_raises_for_missing_token(monkeypatch):
    monkeypatch.setattr(bot_app, "BOT_TOKEN", "")

    with pytest.raises(
        RuntimeError,
        match="BOT_TOKEN не найден или некорректен",
    ):
        bot_app.create_bot(token="")
