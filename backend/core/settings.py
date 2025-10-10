from __future__ import annotations

import os
import secrets
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Tuple

from backend.core.env import load_env


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url_async: str
    database_url_sync: str
    sql_echo: bool
    bot_enabled: bool
    bot_provider: str
    bot_token: str
    bot_api_base: str
    redis_url: str
    bot_use_webhook: bool
    bot_webhook_url: str
    test2_required: bool
    bot_failfast: bool
    bot_integration_enabled: bool
    admin_chat_id: int
    timezone: str
    session_secret: str
    session_cookie_name: str
    admin_username: str
    admin_password: str
    admin_docs_enabled: bool
    session_cookie_secure: bool
    session_cookie_samesite: str
    state_ttl_seconds: int
    admin_trusted_hosts: Tuple[str, ...]
    admin_rate_limit_attempts: int
    admin_rate_limit_window_seconds: int


load_env()


def _default_data_dir() -> Path:
    env_dir = os.getenv("DATA_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir).expanduser()
    return Path(__file__).resolve().parents[2] / "data"


def _maybe_migrate_legacy_database(data_dir: Path) -> None:
    legacy_path = Path(__file__).resolve().parents[2] / "bot.db"
    target_path = data_dir / "bot.db"
    if legacy_path.exists() and not target_path.exists():
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_path), str(target_path))
        except Exception:
            pass


def _normalize_sqlite_url(url: str, *, async_driver: bool) -> str:
    if not url:
        return url
    prefix = "sqlite+aiosqlite" if async_driver else "sqlite"
    if url.startswith("sqlite+aiosqlite") or url.startswith("sqlite"):
        path = url.split("///", maxsplit=1)[-1]
        return f"{prefix}:///{path}"
    return url


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_bool_with_fallback(*names: str, default: bool = False) -> bool:
    for name in names:
        if os.getenv(name) is not None:
            return _get_bool(name)
    return default


def _get_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None else int(default)
    except (TypeError, ValueError):
        value = int(default)
    if minimum is not None and value < minimum:
        return minimum
    return value


def _split_csv(name: str, default: Iterable[str]) -> Tuple[str, ...]:
    raw = os.getenv(name, "")
    if not raw:
        return tuple(default)
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return tuple(values or tuple(default))


_PLACEHOLDER_VALUES = {
    "change-me",
    "changeme",
    "changeme-session-secret",
    "changeme-session",
    "changeme-secret",
    "password",
    "secret",
    "admin",
    "123456",
    "example",
    "sample",
}


def _looks_like_placeholder(value: str) -> bool:
    slug = value.strip().lower()
    if not slug:
        return True
    if slug in _PLACEHOLDER_VALUES:
        return True
    return slug.startswith("change_me") or slug.startswith("changeme")


def validate_settings(settings: Settings) -> None:
    """Validate critical secrets and fail-fast when placeholders leak in."""

    errors: list[str] = []

    if _looks_like_placeholder(settings.admin_username):
        errors.append("ADMIN_USER must be defined and use a non-default value")

    if _looks_like_placeholder(settings.admin_password):
        errors.append("ADMIN_PASSWORD must be defined and use a non-default value")

    secret_source = os.getenv("SESSION_SECRET") or os.getenv("SECRET_KEY")
    if secret_source:
        if _looks_like_placeholder(secret_source) or len(secret_source) < 32:
            errors.append("SESSION_SECRET must contain at least 32 characters and avoid placeholder values")
    else:
        if len(settings.session_secret) < 32:
            errors.append("Generated SESSION_SECRET is unexpectedly short")

    raw_bot_token = os.getenv("BOT_TOKEN")
    if raw_bot_token is not None and _looks_like_placeholder(raw_bot_token):
        errors.append("BOT_TOKEN must be replaced with a real value or left unset")

    if errors:
        joined = "\n - ".join(errors)
        raise RuntimeError(f"Invalid sensitive configuration detected:\n - {joined}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = _default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    if not os.getenv("DATABASE_URL"):
        _maybe_migrate_legacy_database(data_dir)

    raw_db_url = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{data_dir / 'bot.db'}")

    async_url = raw_db_url
    sync_url = raw_db_url

    if raw_db_url.startswith("sqlite+aiosqlite"):
        sync_url = _normalize_sqlite_url(raw_db_url, async_driver=False)
    elif raw_db_url.startswith("postgresql+asyncpg"):
        sync_url = raw_db_url.replace("+asyncpg", "")
    elif raw_db_url.startswith("mysql+aiomysql"):
        sync_url = raw_db_url.replace("+aiomysql", "")

    async_url = _normalize_sqlite_url(raw_db_url, async_driver=True)

    bot_enabled = _get_bool_with_fallback("BOT_ENABLED", "ENABLE_TEST2_BOT", default=True)
    bot_provider = os.getenv("BOT_PROVIDER", "telegram").strip().lower() or "telegram"
    bot_token = os.getenv("BOT_TOKEN", "")
    bot_api_base = os.getenv("BOT_API_BASE", "").strip()
    redis_url = os.getenv("REDIS_URL", "").strip()
    bot_integration_enabled = _get_bool("BOT_INTEGRATION_ENABLED", default=True)
    bot_use_webhook = _get_bool("BOT_USE_WEBHOOK", default=False)
    bot_webhook_url = os.getenv("BOT_WEBHOOK_URL", "").strip()
    test2_required = _get_bool("TEST2_REQUIRED", default=False)
    bot_failfast = _get_bool("BOT_FAILFAST", default=False)
    admin_chat_id = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
    timezone = os.getenv("TZ", "Europe/Moscow")
    session_secret = (
        os.getenv("SESSION_SECRET")
        or os.getenv("SECRET_KEY")
        or secrets.token_urlsafe(64)
    )

    admin_username = os.getenv("ADMIN_USER", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    session_cookie_name = (
        os.getenv("SESSION_COOKIE_NAME", "hr_admin_session").strip() or "hr_admin_session"
    )
    admin_docs_enabled = _get_bool("ADMIN_DOCS_ENABLED", default=False)
    session_cookie_secure = _get_bool("SESSION_COOKIE_SECURE", default=True)
    session_cookie_samesite = os.getenv("SESSION_COOKIE_SAMESITE", "strict").strip().lower() or "strict"
    if session_cookie_samesite not in {"strict", "lax", "none"}:
        session_cookie_samesite = "strict"

    ttl_raw = os.getenv("STATE_TTL_SECONDS", "604800").strip()
    try:
        state_ttl_seconds = int(ttl_raw)
    except ValueError:
        state_ttl_seconds = 604800
    if state_ttl_seconds <= 0:
        state_ttl_seconds = 604800

    admin_trusted_hosts = _split_csv(
        "ADMIN_TRUSTED_HOSTS", ("localhost", "127.0.0.1", "testserver")
    )
    admin_rate_limit_attempts = _get_int("ADMIN_RATE_LIMIT_ATTEMPTS", 5, minimum=1)
    admin_rate_limit_window_seconds = _get_int(
        "ADMIN_RATE_LIMIT_WINDOW_SECONDS", 300, minimum=10
    )

    return Settings(
        data_dir=data_dir,
        database_url_async=async_url,
        database_url_sync=sync_url,
        sql_echo=os.getenv("SQL_ECHO", "0") in {"1", "true", "True"},
        bot_enabled=bot_enabled,
        bot_provider=bot_provider,
        bot_token=bot_token,
        bot_api_base=bot_api_base,
        redis_url=redis_url,
        bot_integration_enabled=bot_integration_enabled,
        bot_use_webhook=bot_use_webhook,
        bot_webhook_url=bot_webhook_url,
        test2_required=test2_required,
        bot_failfast=bot_failfast,
        admin_chat_id=admin_chat_id,
        timezone=timezone,
        session_secret=session_secret,
        session_cookie_name=session_cookie_name,
        admin_username=admin_username,
        admin_password=admin_password,
        admin_docs_enabled=admin_docs_enabled,
        session_cookie_secure=session_cookie_secure,
        session_cookie_samesite=session_cookie_samesite,
        state_ttl_seconds=state_ttl_seconds,
        admin_trusted_hosts=admin_trusted_hosts,
        admin_rate_limit_attempts=admin_rate_limit_attempts,
        admin_rate_limit_window_seconds=admin_rate_limit_window_seconds,
    )


__all__ = ["Settings", "get_settings", "validate_settings"]
