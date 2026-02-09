
import pytest
from backend.apps.admin_ui.routers.api import api_template_presets
# We need to mock known_template_presets
from unittest.mock import patch

@pytest.mark.asyncio
async def test_api_presets_format():
    mock_data = [
        {"key": "k1", "text": "t1", "label": "l1"},
        {"key": "k2", "text": "t2", "label": "l2"},
    ]
    with patch("backend.apps.admin_ui.routers.api.known_template_presets", return_value=mock_data):
        response = await api_template_presets()
        import json
        body = json.loads(response.body)
        assert isinstance(body, dict)
        assert body["k1"] == "t1"
        assert body["k2"] == "t2"
        assert "label" not in body
