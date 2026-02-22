import pytest

from backend.core.content_updates import (
    KIND_QUESTIONS_CHANGED,
    KIND_TEMPLATES_CHANGED,
    build_content_update,
    parse_content_update,
)


def test_content_update_parse_roundtrip():
    raw = build_content_update(KIND_QUESTIONS_CHANGED, {"test_id": "test1"})
    event = parse_content_update(raw)
    assert event is not None
    assert event.kind == KIND_QUESTIONS_CHANGED
    assert event.payload["test_id"] == "test1"
    assert event.at >= 0.0


def test_content_update_parse_invalid_returns_none():
    assert parse_content_update("") is None
    assert parse_content_update("not json") is None
    assert parse_content_update('{"payload":{}}') is None


@pytest.mark.asyncio
async def test_notification_service_invalidate_template_cache_calls_provider():
    from backend.apps.bot.services import NotificationService

    class FakeProvider:
        def __init__(self) -> None:
            self.calls = []

        async def invalidate(self, *, key=None, locale="ru", channel="tg", city_id=None):
            self.calls.append(
                {
                    "key": key,
                    "locale": locale,
                    "channel": channel,
                    "city_id": city_id,
                }
            )

    provider = FakeProvider()
    svc = NotificationService(template_provider=provider, scheduler=None, broker=None)
    await svc.invalidate_template_cache(
        key="confirm_2h",
        locale="ru",
        channel="tg",
        city_id=123,
    )
    assert provider.calls == [
        {
            "key": "confirm_2h",
            "locale": "ru",
            "channel": "tg",
            "city_id": 123,
        }
    ]

