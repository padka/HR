"""
Test that production environment requires Redis configuration.

This test validates the production fail-fast behavior when Redis is not properly configured.
"""

import pytest

pytestmark = pytest.mark.no_db_cleanup


def test_prod_without_redis_url_fails_at_settings_level(monkeypatch):
    """Production should fail immediately when loading settings if REDIS_URL is missing."""
    from backend.core import settings as settings_module

    env = {
        "ENVIRONMENT": "production",
        "NOTIFICATION_BROKER": "redis",
        "REDIS_URL": "",
        "BOT_ENABLED": "0",
        "BOT_INTEGRATION_ENABLED": "0",
        "BOT_AUTOSTART": "0",
        # Need valid Postgres URL since we're now validating that too
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb",
        "DATA_DIR": "/tmp/recruitsmart_test_data",
        "ADMIN_USER": "admin",
        "ADMIN_PASSWORD": "admin",
        "SESSION_SECRET": "test-session-secret-0123456789abcdef0123456789abcd",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings_module.get_settings.cache_clear()
    try:
        # Should fail when get_settings() validates production config
        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()

        error_msg = str(exc_info.value)
        assert "REDIS_URL to be set" in error_msg
        assert "PRODUCTION CONFIGURATION ERRORS" in error_msg
    finally:
        settings_module.get_settings.cache_clear()
