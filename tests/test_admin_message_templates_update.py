
import pytest
from backend.apps.admin_ui.services.message_templates import create_message_template, update_message_template
from backend.core.db import async_session
from backend.domain.models import MessageTemplate
from sqlalchemy import select

@pytest.mark.asyncio
async def test_update_message_template_optimistic_locking():
    # 1. Create a template
    ok, errors, tmpl = await create_message_template(
        key="test_key",
        locale="ru",
        channel="tg",
        body="Test body",
        is_active=True,
    )
    assert ok, f"Create failed: {errors}"
    template_id = tmpl.id
    initial_version = tmpl.version
    assert initial_version == 1

    # 2. Update with correct version
    ok, errors, tmpl = await update_message_template(
        template_id=template_id,
        key="test_key",
        locale="ru",
        channel="tg",
        body="Updated body",
        is_active=True,
        expected_version=1,
    )
    assert ok, f"Update failed: {errors}"
    assert tmpl.version == 2
    assert tmpl.body_md == "Updated body"

    # 3. Update with OLD version (conflict)
    ok, errors, tmpl = await update_message_template(
        template_id=template_id,
        key="test_key",
        locale="ru",
        channel="tg",
        body="Updated body 2",
        is_active=True,
        expected_version=1, # Should be 2 now
    )
    assert not ok
    assert "Конфликт редактирования" in errors[0]

    # 4. Update without version (force update)
    ok, errors, tmpl = await update_message_template(
        template_id=template_id,
        key="test_key",
        locale="ru",
        channel="tg",
        body="Force update",
        is_active=True,
        expected_version=None,
    )
    assert ok
    assert tmpl.version == 3
    assert tmpl.body_md == "Force update"
