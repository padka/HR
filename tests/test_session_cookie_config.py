import pytest

from backend.apps.admin_ui.app import create_app
from backend.core import settings as settings_module


def _build_app(env: str, monkeypatch: pytest.MonkeyPatch):
    # Minimal env so get_settings does not raise
    import tempfile
    monkeypatch.setenv("ENVIRONMENT", env)
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-0123456789abcdef0123456789abcd")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "S3cureAdm1nPass!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://rs:pass@localhost:5432/rs_test")
    monkeypatch.setenv("BOT_CALLBACK_SECRET", "prod-callback-secret-0123456789abcdef0123456789abcd")

    # Production requires Redis and specific broker settings
    if env == "production":
        temp_dir = tempfile.mkdtemp(prefix="test_prod_session_")
        monkeypatch.setenv("DATA_DIR", temp_dir)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("NOTIFICATION_BROKER", "redis")
        monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    else:
        monkeypatch.setenv("REDIS_URL", "")
        monkeypatch.setenv("NOTIFICATION_BROKER", "memory")
        monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")

    settings_module.get_settings.cache_clear()
    try:
        return create_app()
    finally:
        settings_module.get_settings.cache_clear()


def _get_session_middleware(app):
    return next(m for m in app.user_middleware if m.cls.__name__ == "SessionMiddleware")


def test_session_cookie_not_secure_in_dev(monkeypatch):
    app = _build_app("development", monkeypatch)
    session_mw = _get_session_middleware(app)
    assert session_mw.kwargs["https_only"] is False


def test_session_cookie_not_secure_in_test(monkeypatch):
    app = _build_app("test", monkeypatch)
    session_mw = _get_session_middleware(app)
    assert session_mw.kwargs["https_only"] is False


def test_session_cookie_secure_in_prod(monkeypatch):
    app = _build_app("production", monkeypatch)
    session_mw = _get_session_middleware(app)
    assert session_mw.kwargs["https_only"] is True
