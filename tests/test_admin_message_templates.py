import pytest

from backend.apps.admin_ui.services.message_templates import (
    create_message_template,
    delete_message_template,
)


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
