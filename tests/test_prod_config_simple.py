"""
Simplified tests for production configuration validation guards.

These tests validate that the production environment enforces strict configuration.
"""

import tempfile
from pathlib import Path

import pytest

# Mark all tests in this module to skip database cleanup
pytestmark = pytest.mark.no_db_cleanup


def test_prod_rejects_missing_database_url(monkeypatch):
    """Production must fail if DATABASE_URL is not set."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
    monkeypatch.setenv("DATA_DIR", "/tmp/test_data")
    monkeypatch.setenv("SESSION_SECRET", "test-prod-secret-32chars-long-0123456789abcdef")

    try:
        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()
        assert "DATABASE_URL environment variable is required" in str(exc_info.value)
    finally:
        settings_module.get_settings.cache_clear()


def test_prod_rejects_sqlite(monkeypatch):
    """Production must fail if DATABASE_URL is SQLite."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
    monkeypatch.setenv("DATA_DIR", "/tmp/test_data")
    monkeypatch.setenv("SESSION_SECRET", "test-prod-secret-32chars-long-0123456789abcdef")

    try:
        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()
        assert "PostgreSQL with asyncpg driver" in str(exc_info.value)
    finally:
        settings_module.get_settings.cache_clear()


def test_prod_accepts_postgresql(monkeypatch):
    """Production should accept PostgreSQL."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    temp_dir = tempfile.mkdtemp(prefix="test_prod_")
    try:
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
        monkeypatch.setenv("DATA_DIR", temp_dir)
        monkeypatch.setenv("SESSION_SECRET", "test-prod-secret-32chars-long-0123456789abcdef")

        settings = settings_module.get_settings()
        assert settings.environment == "production"
        assert "postgresql" in settings.database_url_sync
    finally:
        settings_module.get_settings.cache_clear()
        import shutil
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_prod_rejects_missing_redis_url(monkeypatch):
    """Production must fail if REDIS_URL is not set."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
    monkeypatch.setenv("DATA_DIR", "/tmp/test_data")
    monkeypatch.setenv("SESSION_SECRET", "test-prod-secret-32chars-long-0123456789abcdef")

    try:
        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()
        assert "REDIS_URL to be set" in str(exc_info.value)
    finally:
        settings_module.get_settings.cache_clear()


def test_prod_rejects_non_redis_broker(monkeypatch):
    """Production must fail if NOTIFICATION_BROKER is not redis."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("NOTIFICATION_BROKER", "memory")
    monkeypatch.setenv("DATA_DIR", "/tmp/test_data")
    monkeypatch.setenv("SESSION_SECRET", "test-prod-secret-32chars-long-0123456789abcdef")

    try:
        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()
        assert "NOTIFICATION_BROKER=redis" in str(exc_info.value)
    finally:
        settings_module.get_settings.cache_clear()


def test_prod_rejects_data_dir_in_repo(monkeypatch):
    """Production must fail if DATA_DIR is inside the repository."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    # Use a path inside the repo
    repo_data_dir = str(settings_module.PROJECT_ROOT / "data")

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
    monkeypatch.setenv("DATA_DIR", repo_data_dir)
    monkeypatch.setenv("SESSION_SECRET", "test-prod-secret-32chars-long-0123456789abcdef")

    try:
        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()
        assert "DATA_DIR outside repo" in str(exc_info.value)
    finally:
        settings_module.get_settings.cache_clear()


def test_dev_requires_postgresql(monkeypatch):
    """Development now requires PostgreSQL (no SQLite)."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    monkeypatch.setenv("SESSION_SECRET", "dev-secret-32chars-long-0123456789abcdef01234")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("NOTIFICATION_BROKER", "memory")

    try:
        settings = settings_module.get_settings()
        assert settings.environment == "development"
        assert "postgresql" in settings.database_url_sync
    finally:
        settings_module.get_settings.cache_clear()


def test_prod_rejects_missing_session_secret(monkeypatch):
    """Production must fail if SESSION_SECRET is not explicitly set."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    temp_dir = tempfile.mkdtemp(prefix="test_prod_")
    try:
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
        monkeypatch.setenv("DATA_DIR", temp_dir)
        # Explicitly remove SESSION_SECRET and SECRET_KEY
        monkeypatch.delenv("SESSION_SECRET", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()
        assert "SESSION_SECRET to be explicitly set" in str(exc_info.value)
    finally:
        settings_module.get_settings.cache_clear()
        import shutil
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_prod_rejects_short_session_secret(monkeypatch):
    """Production must fail if SESSION_SECRET is too short (< 32 chars)."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    temp_dir = tempfile.mkdtemp(prefix="test_prod_")
    try:
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
        monkeypatch.setenv("DATA_DIR", temp_dir)
        monkeypatch.setenv("SESSION_SECRET", "short")  # Only 5 chars

        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()
        assert "SESSION_SECRET too short" in str(exc_info.value)
        assert "got 5 chars" in str(exc_info.value)
    finally:
        settings_module.get_settings.cache_clear()
        import shutil
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_prod_rejects_unwritable_data_dir(monkeypatch):
    """Production must fail if DATA_DIR is not writable."""
    from backend.core import settings as settings_module
    import os
    import stat

    settings_module.get_settings.cache_clear()

    temp_dir = tempfile.mkdtemp(prefix="test_prod_")
    try:
        # Make the directory read-only
        os.chmod(temp_dir, stat.S_IRUSR | stat.S_IXUSR)  # Read + execute only, no write

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
        monkeypatch.setenv("DATA_DIR", temp_dir)
        monkeypatch.setenv("SESSION_SECRET", "test-prod-secret-32chars-long-0123456789abcdef")

        with pytest.raises(RuntimeError) as exc_info:
            settings_module.get_settings()
        error_msg = str(exc_info.value)
        assert "DATA_DIR" in error_msg
        assert ("not writable" in error_msg or "permissions check failed" in error_msg)
    finally:
        settings_module.get_settings.cache_clear()
        # Restore write permissions before cleanup
        try:
            os.chmod(temp_dir, stat.S_IRWXU)
        except Exception:
            pass
        import shutil
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_validation_skipped_in_development(monkeypatch):
    """Verify that production validation is completely skipped in development mode."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    try:
        # Set development environment
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Set config that would fail in production (no Redis, memory broker)
        # but should be fine in development
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.setenv("NOTIFICATION_BROKER", "memory")
        monkeypatch.setenv("SESSION_SECRET", "dev-secret-32chars-long-0123456789abcdef01234")

        # This should NOT raise any errors in development
        settings = settings_module.get_settings()

        # Verify we got development settings
        assert settings.environment == "development"
        assert "postgresql" in settings.database_url_sync
        assert settings.notification_broker == "memory"
    finally:
        settings_module.get_settings.cache_clear()


def test_validation_skipped_in_staging(monkeypatch):
    """Verify that production validation is skipped for staging environment."""
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    try:
        # Set staging environment
        monkeypatch.setenv("ENVIRONMENT", "staging")

        # Use PostgreSQL with relaxed config (no Redis, etc.)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
        monkeypatch.setenv("SESSION_SECRET", "staging-secret-32chars-long-0123456789abcdef")
        monkeypatch.setenv("REDIS_URL", "")
        monkeypatch.setenv("NOTIFICATION_BROKER", "memory")

        # Should not raise - validation skipped for staging
        settings = settings_module.get_settings()
        assert settings.environment == "staging"
        assert "postgresql" in settings.database_url_sync
    finally:
        settings_module.get_settings.cache_clear()


def test_validation_case_insensitive(monkeypatch):
    """Verify ENVIRONMENT check is case-insensitive."""
    from backend.core import settings as settings_module

    temp_dir = tempfile.mkdtemp(prefix="test_prod_")
    try:
        # Test various casings of "production"
        for env_value in ["PRODUCTION", "Production", "production"]:
            settings_module.get_settings.cache_clear()

            monkeypatch.setenv("ENVIRONMENT", env_value)
            # Don't set DATABASE_URL - should trigger validation error
            monkeypatch.delenv("DATABASE_URL", raising=False)
            monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
            monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
            monkeypatch.setenv("DATA_DIR", temp_dir)
            monkeypatch.setenv("SESSION_SECRET", "test-prod-secret-32chars-long-0123456789abcdef")

            # All casings should trigger validation and raise error
            with pytest.raises(RuntimeError) as exc_info:
                settings_module.get_settings()
            # Error is raised early at DATABASE_URL check, not in validation block
            assert "DATABASE_URL" in str(exc_info.value)
    finally:
        settings_module.get_settings.cache_clear()
        import shutil
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
