import asyncio
from pathlib import Path
from types import SimpleNamespace

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
        api = bot.session.api
        assert getattr(api, "api_base", base_url).startswith(base_url)
    finally:
        asyncio.run(bot.session.close())


def test_create_bot_raises_for_missing_token(monkeypatch):
    monkeypatch.setattr(bot_app, "BOT_TOKEN", "")

    with pytest.raises(
        RuntimeError,
        match="BOT_TOKEN не найден или некорректен",
    ):
        bot_app.create_bot(token="")


@pytest.mark.asyncio
async def test_main_closes_bot_session_on_startup_failure(monkeypatch, tmp_path: Path):
    class DummySettings:
        redis_url = ""
        environment = "development"
        data_dir = tmp_path

    class DummySession:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    class DummyBot:
        def __init__(self) -> None:
            self.session = DummySession()

        async def delete_webhook(self, *args, **kwargs):
            raise RuntimeError("Unauthorized")

        async def get_me(self):
            raise AssertionError("get_me should not be called when delete_webhook fails")

    class DummyReminder:
        def __init__(self) -> None:
            self.stopped = False

        async def shutdown(self) -> None:
            self.stopped = True

    class DummyNotification:
        def __init__(self) -> None:
            self.started = False
            self.stopped = False

        def start(self) -> None:
            self.started = True

        async def shutdown(self) -> None:
            self.stopped = True

    bot = DummyBot()
    dispatcher = SimpleNamespace(start_polling=lambda _bot: None)
    reminder = DummyReminder()
    notification = DummyNotification()

    async def fake_create_application():
        return bot, dispatcher, None, reminder, notification

    monkeypatch.setattr(bot_app, "get_settings", lambda: DummySettings())
    monkeypatch.setattr(bot_app, "create_application", fake_create_application)
    monkeypatch.setattr(bot_app, "reset_bootstrap_notification_service", lambda: None)

    with pytest.raises(RuntimeError, match="Unauthorized"):
        await bot_app.main()

    assert notification.started is True
    assert reminder.stopped is True
    assert notification.stopped is True
    assert bot.session.closed is True
