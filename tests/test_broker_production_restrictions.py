"""Tests for production environment restrictions on notification broker."""

import pytest
from unittest.mock import Mock, patch

from backend.apps.bot.broker import InMemoryNotificationBroker


@pytest.mark.asyncio
async def test_inmemory_broker_forbidden_in_production():
    """
    Test that InMemory broker cannot be used in production environment.

    This is a critical safety test to ensure distributed workers work correctly.
    """
    from backend.core.settings import Settings

    # Mock production settings
    prod_settings = Mock(spec=Settings)
    prod_settings.environment = "production"
    prod_settings.redis_url = ""  # No Redis URL provided

    # Import the setup function
    with patch("backend.apps.admin_ui.state.get_settings", return_value=prod_settings):
        with patch("backend.apps.admin_ui.state.Redis", None):
            # Should raise RuntimeError in production without Redis
            with pytest.raises(RuntimeError) as exc_info:
                from backend.apps.admin_ui.state import setup_bot_state

                app = Mock()
                await setup_bot_state(app)

            assert "REDIS_URL is required in production" in str(exc_info.value)


@pytest.mark.asyncio
async def test_inmemory_broker_allowed_in_development():
    """
    Test that InMemory broker can be used in development environment.
    """
    from backend.core.settings import Settings

    # Mock development settings
    dev_settings = Mock(spec=Settings)
    dev_settings.environment = "development"
    dev_settings.redis_url = ""  # No Redis URL
    dev_settings.bot_enabled = False
    dev_settings.bot_integration_enabled = False
    dev_settings.notification_poll_interval = 3.0
    dev_settings.notification_batch_size = 100
    dev_settings.notification_rate_limit_per_sec = 5.0
    dev_settings.notification_max_attempts = 8
    dev_settings.notification_retry_base_seconds = 30
    dev_settings.notification_retry_max_seconds = 3600
    dev_settings.test2_required = False

    with patch("backend.apps.admin_ui.state.get_settings", return_value=dev_settings):
        with patch("backend.apps.admin_ui.state.Redis", None):
            with patch("backend.apps.admin_ui.state.create_scheduler", return_value=Mock()):
                with patch("backend.apps.admin_ui.state._build_bot", return_value=(None, False)):
                    # Should NOT raise in development
                    from backend.apps.admin_ui.state import setup_bot_state

                    app = Mock()
                    app.state = Mock()

                    integration = await setup_bot_state(app)

                    # Should successfully create InMemory broker
                    assert integration is not None


@pytest.mark.asyncio
async def test_redis_required_message_in_production():
    """Test that error message clearly states Redis is required in production."""
    from backend.core.settings import Settings

    prod_settings = Mock(spec=Settings)
    prod_settings.environment = "production"
    prod_settings.redis_url = None

    with patch("backend.apps.admin_ui.state.get_settings", return_value=prod_settings):
        with patch("backend.apps.admin_ui.state.Redis", None):
            with pytest.raises(RuntimeError) as exc_info:
                from backend.apps.admin_ui.state import setup_bot_state

                app = Mock()
                await setup_bot_state(app)

            error_message = str(exc_info.value)
            assert "REDIS_URL is required" in error_message
            assert "production" in error_message
            assert "InMemory broker is not allowed" in error_message


@pytest.mark.asyncio
async def test_environment_setting_validation():
    """Test that environment setting is properly validated."""
    from backend.core.settings import get_settings
    import os

    # Test valid environments
    for env in ["development", "production", "staging"]:
        with patch.dict(os.environ, {"ENVIRONMENT": env}):
            # Clear cache
            get_settings.cache_clear()
            settings = get_settings()
            assert settings.environment == env

    # Test invalid environment defaults to development
    with patch.dict(os.environ, {"ENVIRONMENT": "invalid"}):
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.environment == "development"

    # Test empty environment defaults to development
    with patch.dict(os.environ, {}, clear=True):
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.environment == "development"
