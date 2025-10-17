import asyncio

import pytest

from backend.apps.bot import templates

@pytest.fixture(scope="session", autouse=True)
def configure_backend():
    """Override heavy database setup from global test configuration."""


def test_tpl_uses_cache(monkeypatch):
    templates.clear_cache()

    calls = 0

    async def fake_get_template(city_id, key):
        nonlocal calls
        calls += 1
        return "cached-from-db"

    monkeypatch.setattr(templates, "get_template", fake_get_template)

    async def run() -> None:
        first = await templates.tpl(42, "greeting")
        second = await templates.tpl(42, "greeting")

        assert first == "cached-from-db"
        assert second == "cached-from-db"
        assert calls == 1

        templates.clear_cache()

        third = await templates.tpl(42, "greeting")
        assert third == "cached-from-db"
        assert calls == 2

    asyncio.run(run())


def test_tpl_uses_default_when_no_template(monkeypatch):
    templates.clear_cache()

    calls = 0

    async def fake_get_template(city_id, key):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(templates, "get_template", fake_get_template)

    async def run() -> None:
        first = await templates.tpl(7, "slot_taken")
        second = await templates.tpl(7, "slot_taken")

        assert first == templates.DEFAULT_TEMPLATES["slot_taken"]
        assert second == templates.DEFAULT_TEMPLATES["slot_taken"]
        assert calls == 1

    asyncio.run(run())
