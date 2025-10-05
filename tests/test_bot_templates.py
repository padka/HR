import pytest

from backend.apps.admin_ui.services import templates as admin_templates
from backend.apps.bot import templates
from backend.domain.template_stages import STAGE_DEFAULTS


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


@pytest.mark.asyncio
async def test_bot_template_updates_follow_admin_changes():
    templates.clear_cache()
    stage_key = admin_templates.STAGE_KEYS[0]

    # Initial request primes the cache with default value
    initial = await templates.tpl(None, stage_key)
    assert initial == STAGE_DEFAULTS.get(stage_key, "")

    base_payload = {key: "" for key in admin_templates.STAGE_KEYS}
    base_payload[stage_key] = "Глобальный текст из админки"
    await admin_templates.update_templates_for_city(None, base_payload)

    updated_global = await templates.tpl(None, stage_key)
    assert updated_global == "Глобальный текст из админки"

    city_payload = {key: "" for key in admin_templates.STAGE_KEYS}
    city_payload[stage_key] = "Городской текст"
    await admin_templates.update_templates_for_city(77, city_payload)

    city_text = await templates.tpl(77, stage_key)
    assert city_text == "Городской текст"

    fallback = await templates.tpl(12, stage_key)
    assert fallback == "Глобальный текст из админки"
