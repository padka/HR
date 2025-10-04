from __future__ import annotations

import os
import secrets
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

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
    admin_username: str
    admin_password: str
    admin_docs_enabled: bool
    session_cookie_secure: bool
    session_cookie_samesite: str
    state_ttl_seconds: int


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
        or secrets.token_urlsafe(32)
    )

    admin_username = os.getenv("ADMIN_USER", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
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
        admin_username=admin_username,
        admin_password=admin_password,
        admin_docs_enabled=admin_docs_enabled,
        session_cookie_secure=session_cookie_secure,
        session_cookie_samesite=session_cookie_samesite,
        state_ttl_seconds=state_ttl_seconds,
    )
