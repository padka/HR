import pytest

from backend.apps.bot import app as bot_app


class DummySettings:
    def __init__(self, base: str) -> None:
        self.bot_api_base = base


@pytest.mark.asyncio
async def test_create_bot_uses_custom_api_base(monkeypatch):
    base_url = "https://example.invalid"
    monkeypatch.setattr(bot_app, "get_settings", lambda: DummySettings(base_url))

    bot = bot_app.create_bot(token="123:ABC")

    try:
        api = bot.session.api
        assert getattr(api, "api_base", base_url).startswith(base_url)
    finally:
        await bot.session.close()
