
import pytest
from unittest.mock import AsyncMock, patch
from backend.apps.bot.template_provider import TemplateProvider, TemplateRecord, TemplateResolutionError

@pytest.mark.asyncio
async def test_get_template_no_fallback():
    provider = TemplateProvider()
    
    with patch("backend.apps.bot.template_provider.get_message_template", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        
        # Should raise exception as fallback is removed
        with pytest.raises(TemplateResolutionError):
            await provider.get("missing_key")

@pytest.mark.asyncio
async def test_render_template_jinja():
    provider = TemplateProvider()
    
    mock_tmpl = AsyncMock()
    mock_tmpl.key = "test_key"
    mock_tmpl.locale = "ru"
    mock_tmpl.channel = "tg"
    mock_tmpl.version = 1
    mock_tmpl.city_id = None
    mock_tmpl.body_md = "Hello {{ name }}!"
    
    with patch("backend.apps.bot.template_provider.get_message_template", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_tmpl
        
        rendered = await provider.render("test_key", {"name": "World"})
        assert rendered is not None
        assert rendered.text == "Hello World!"
