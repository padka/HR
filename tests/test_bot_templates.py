import pytest

from backend.apps.bot import templates


@pytest.mark.asyncio
async def test_tpl_uses_cache(monkeypatch):
    templates.clear_cache()

    calls = 0

    async def fake_get_template(city_id, key):
        nonlocal calls
        calls += 1
        return "cached-from-db"

    monkeypatch.setattr(templates, "get_template", fake_get_template)

    first = await templates.tpl(42, "greeting")
    second = await templates.tpl(42, "greeting")

    assert first == "cached-from-db"
    assert second == "cached-from-db"
    assert calls == 1

    templates.clear_cache()

    third = await templates.tpl(42, "greeting")
    assert third == "cached-from-db"
    assert calls == 2
