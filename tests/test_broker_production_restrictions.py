"""Tests for production environment restrictions on notification broker."""

import pytest
from unittest.mock import Mock, patch

from backend.apps.bot.broker import InMemoryNotificationBroker


@pytest.mark.asyncio
async def test_inmemory_broker_forbidden_in_production():
    """
    Production should stay alive but report degraded status when Redis is missing.
    """
    from backend.core.settings import Settings

    # Mock production settings with all required attributes
    prod_settings = Mock(spec=Settings)
    prod_settings.environment = "production"
    prod_settings.redis_url = ""  # No Redis URL provided
    prod_settings.bot_enabled = False
    prod_settings.bot_integration_enabled = False
    prod_settings.notification_poll_interval = 3.0
    prod_settings.notification_batch_size = 100
    prod_settings.notification_rate_limit_per_sec = 5.0
    prod_settings.notification_worker_concurrency = 1
    prod_settings.notification_max_attempts = 8
    prod_settings.notification_retry_base_seconds = 30
    prod_settings.notification_retry_max_seconds = 3600
    prod_settings.bot_provider = "telegram"
    prod_settings.bot_token = ""
    prod_settings.bot_use_webhook = False
    prod_settings.bot_webhook_url = ""
    prod_settings.bot_failfast = False
    prod_settings.bot_autostart = False
    prod_settings.bot_enabled = False
    prod_settings.test2_required = False
    prod_settings.session_secret = "secret"
    prod_settings.session_cookie_samesite = "lax"
    prod_settings.session_cookie_secure = False
    prod_settings.notification_broker = "redis"
    prod_settings.state_ttl_seconds = 60

    with patch("backend.apps.admin_ui.state.get_settings", return_value=prod_settings):
        with patch("backend.apps.admin_ui.state.Redis", None):
            from backend.apps.admin_ui.state import setup_bot_state

            app = Mock()
            app.state = Mock()
            integration = await setup_bot_state(app)

            assert integration.notification_broker is None
            assert app.state.notification_broker_status == "degraded"
            assert integration.notification_watch_task is None


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
    dev_settings.bot_provider = "telegram"
    dev_settings.notification_poll_interval = 3.0
    dev_settings.notification_batch_size = 100
    dev_settings.notification_rate_limit_per_sec = 5.0
    dev_settings.notification_worker_concurrency = 1
    dev_settings.notification_max_attempts = 8
    dev_settings.notification_retry_base_seconds = 30
    dev_settings.notification_retry_max_seconds = 3600
    dev_settings.test2_required = False
    dev_settings.session_secret = "secret"
    dev_settings.session_cookie_samesite = "lax"
    dev_settings.session_cookie_secure = False
    dev_settings.notification_broker = "memory"
    dev_settings.state_ttl_seconds = 60

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
    """Production readiness probe should report degraded status when Redis URL missing."""
    from backend.core.settings import Settings

    prod_settings = Mock(spec=Settings)
    prod_settings.environment = "production"
    prod_settings.redis_url = None
    prod_settings.bot_enabled = False
    prod_settings.bot_integration_enabled = False
    prod_settings.notification_poll_interval = 3.0
    prod_settings.notification_batch_size = 100
    prod_settings.notification_rate_limit_per_sec = 5.0
    prod_settings.notification_worker_concurrency = 1
    prod_settings.notification_max_attempts = 8
    prod_settings.notification_retry_base_seconds = 30
    prod_settings.notification_retry_max_seconds = 3600
    prod_settings.bot_provider = "telegram"
    prod_settings.bot_token = ""
    prod_settings.bot_use_webhook = False
    prod_settings.bot_webhook_url = ""
    prod_settings.bot_failfast = False
    prod_settings.bot_autostart = False
    prod_settings.bot_enabled = False
    prod_settings.test2_required = False
    prod_settings.session_secret = "secret"
    prod_settings.session_cookie_samesite = "lax"
    prod_settings.session_cookie_secure = False
    prod_settings.notification_broker = "redis"
    prod_settings.state_ttl_seconds = 60

    with patch("backend.apps.admin_ui.state.get_settings", return_value=prod_settings):
        with patch("backend.apps.admin_ui.state.Redis", None):
            from backend.apps.admin_ui.state import setup_bot_state

            app = Mock()
            app.state = Mock()
            integration = await setup_bot_state(app)

            assert integration.notification_broker is None
            assert app.state.notification_broker_status == "degraded"


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
