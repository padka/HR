
import pytest
from backend.apps.admin_ui.services.message_templates import create_message_template

@pytest.mark.asyncio
async def test_create_sms_template():
    ok, errors, tmpl = await create_message_template(
        key="test_sms",
        locale="ru",
        channel="sms",
        body="Test SMS body",
        is_active=True,
    )
    assert ok, f"Create SMS template failed: {errors}"
    assert tmpl.channel == "sms"
