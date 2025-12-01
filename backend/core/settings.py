from __future__ import annotations

import logging
import os
import secrets
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from backend.core.env import load_env


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_USER_DATA_DIR = Path.home() / ".recruitsmart_admin" / "data"
DEFAULT_DEV_DB_PATH = PROJECT_ROOT / "data" / "bot.db"


@dataclass(frozen=True)
class Settings:
    environment: str  # development, production, staging
    data_dir: Path
    database_url_async: str
    database_url_sync: str
    sql_echo: bool
    bot_enabled: bool
    bot_provider: str
    bot_token: str
    bot_api_base: str
    redis_url: str
    notification_broker: str
    bot_use_webhook: bool
    bot_webhook_url: str
    test2_required: bool
    bot_failfast: bool
    bot_integration_enabled: bool
    bot_autostart: bool
    log_level: str
    log_json: bool
    log_file: str
    admin_chat_id: int
    timezone: str
    session_secret: str
    admin_username: str
    admin_password: str
    admin_docs_enabled: bool
    session_cookie_secure: bool
    session_cookie_samesite: str
    state_ttl_seconds: int
    notification_poll_interval: float
    notification_batch_size: int
    notification_rate_limit_per_sec: float
    notification_worker_concurrency: int
    notification_retry_base_seconds: int
    notification_retry_max_seconds: int
    notification_max_attempts: int
    db_pool_size: int
    db_max_overflow: int
    db_pool_timeout: int
    db_pool_recycle: int


def _get_int(name: str, default: int, *, minimum: Optional[int] = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and value < minimum:
        return default
    return value


def _get_float(name: str, default: float, *, minimum: Optional[float] = None) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw.strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and value < minimum:
        return default
    return value


load_env()


def _default_data_dir() -> Path:
    env_dir = os.getenv("DATA_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir).expanduser()
    return DEFAULT_USER_DATA_DIR


def _maybe_migrate_legacy_database(data_dir: Path) -> None:
    target_path = data_dir / "bot.db"
    legacy_candidates = [
        PROJECT_ROOT / "bot.db",
        PROJECT_ROOT / "data" / "bot.db",
    ]
    for legacy in legacy_candidates:
        if legacy.exists() and not target_path.exists():
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(legacy), str(target_path))
            except Exception:
                pass

    legacy_data_dir = PROJECT_ROOT / "data"
    if legacy_data_dir.exists() and legacy_data_dir.is_dir():
        try:
            for child in legacy_data_dir.iterdir():
                destination = data_dir / child.name
                if destination.exists():
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(child), str(destination))
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


def _warn_sqlite_inside_repo(database_url_sync: str, environment: str) -> None:
    if environment != "development":
        return
    if not database_url_sync.startswith("sqlite"):
        return
    path_part = database_url_sync.split("///", 1)[-1]
    try:
        db_path = Path(path_part).resolve()
        default_dev_path = DEFAULT_DEV_DB_PATH.resolve()
    except Exception:
        return
    try:
        if db_path == default_dev_path:
            return
        if PROJECT_ROOT in db_path.parents or db_path == PROJECT_ROOT:
            logging.warning(
                "SQLite database %s is located inside the project tree. "
                "When using --reload every write will restart the server. "
                "Move the database outside the repo (default: %s) or set DATA_DIR.",
                db_path,
                DEFAULT_USER_DATA_DIR,
            )
    except Exception:
        pass


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Determine environment (default to development for safety)
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    if environment not in {"development", "production", "staging"}:
        environment = "development"

    data_dir = _default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    db_url_env = os.getenv("DATABASE_URL")
    db_url_env = db_url_env.strip() if db_url_env is not None else ""
    if not db_url_env and environment != "development":
        _maybe_migrate_legacy_database(data_dir)

    if db_url_env:
        raw_db_url = db_url_env
    else:
        if environment == "development":
            DEFAULT_DEV_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            raw_db_url = f"sqlite+aiosqlite:///{DEFAULT_DEV_DB_PATH}"
        else:
            raw_db_url = f"sqlite+aiosqlite:///{data_dir / 'bot.db'}"

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
    notification_broker = os.getenv("NOTIFICATION_BROKER", "memory").strip().lower() or "memory"
    if notification_broker not in {"memory", "redis"}:
        notification_broker = "memory"
    bot_integration_enabled = _get_bool("BOT_INTEGRATION_ENABLED", default=True)
    bot_use_webhook = _get_bool("BOT_USE_WEBHOOK", default=False)
    bot_webhook_url = os.getenv("BOT_WEBHOOK_URL", "").strip()
    test2_required = _get_bool("TEST2_REQUIRED", default=False)
    bot_failfast = _get_bool("BOT_FAILFAST", default=False)
    bot_autostart = _get_bool("BOT_AUTOSTART", default=environment != "production")
    admin_chat_id = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
    timezone = os.getenv("TZ", "Europe/Moscow")
    session_secret = (
        os.getenv("SESSION_SECRET")
        or os.getenv("SECRET_KEY")
        or secrets.token_urlsafe(32)
    )

    # Validate SESSION_SECRET strength
    weak_secrets = {
        "change-me",
        "change-me-session-secret",
        "secret",
        "session-secret",
        "my-secret-key",
        "CHANGE_ME_SESSION_SECRET"
    }
    if session_secret.lower() in weak_secrets:
        raise ValueError(
            f"SESSION_SECRET must be changed from default value '{session_secret}'. "
            "Generate a strong secret with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if len(session_secret) < 32:
        raise ValueError(
            f"SESSION_SECRET must be at least 32 characters (current: {len(session_secret)}). "
            "Generate a strong secret with: python -c \"import secrets; print(secrets.token_hex(32))\""
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

    notification_poll_interval = _get_float("NOTIFICATION_POLL_INTERVAL", 3.0, minimum=0.1)
    notification_batch_size = _get_int("NOTIFICATION_BATCH_SIZE", 100, minimum=1)
    notification_rate_limit_per_sec = _get_float("NOTIFICATION_RATE_LIMIT_PER_SEC", 10.0, minimum=0.0)
    notification_worker_concurrency = _get_int("NOTIFICATION_WORKER_CONCURRENCY", 1, minimum=1)
    notification_retry_base_seconds = _get_int("NOTIFICATION_RETRY_BASE_SECONDS", 30, minimum=1)
    notification_retry_max_seconds = _get_int("NOTIFICATION_RETRY_MAX_SECONDS", 3600, minimum=1)
    if notification_retry_max_seconds < notification_retry_base_seconds:
        notification_retry_max_seconds = notification_retry_base_seconds
    notification_max_attempts = _get_int("NOTIFICATION_MAX_ATTEMPTS", 8, minimum=1)
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    log_json = _get_bool("LOG_JSON", default=False)
    log_file = os.getenv("LOG_FILE", "").strip()
    if not log_file:
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "app.log")

    # Database connection pool settings
    db_pool_size = _get_int("DB_POOL_SIZE", 20, minimum=1)
    db_max_overflow = _get_int("DB_MAX_OVERFLOW", 10, minimum=0)
    db_pool_timeout = _get_int("DB_POOL_TIMEOUT", 30, minimum=1)
    db_pool_recycle = _get_int("DB_POOL_RECYCLE", 3600, minimum=60)

    settings = Settings(
        environment=environment,
        data_dir=data_dir,
        database_url_async=async_url,
        database_url_sync=sync_url,
        sql_echo=os.getenv("SQL_ECHO", "0") in {"1", "true", "True"},
        bot_enabled=bot_enabled,
        bot_provider=bot_provider,
        bot_token=bot_token,
        bot_api_base=bot_api_base,
        redis_url=redis_url,
        notification_broker=notification_broker,
        bot_integration_enabled=bot_integration_enabled,
        bot_use_webhook=bot_use_webhook,
        bot_webhook_url=bot_webhook_url,
        test2_required=test2_required,
        bot_failfast=bot_failfast,
        bot_autostart=bot_autostart,
        log_level=log_level,
        log_json=log_json,
        log_file=log_file,
        admin_chat_id=admin_chat_id,
        timezone=timezone,
        session_secret=session_secret,
        admin_username=admin_username,
        admin_password=admin_password,
        admin_docs_enabled=admin_docs_enabled,
        session_cookie_secure=session_cookie_secure,
        session_cookie_samesite=session_cookie_samesite,
        state_ttl_seconds=state_ttl_seconds,
        notification_poll_interval=notification_poll_interval,
        notification_batch_size=notification_batch_size,
        notification_rate_limit_per_sec=notification_rate_limit_per_sec,
        notification_worker_concurrency=notification_worker_concurrency,
        notification_retry_base_seconds=notification_retry_base_seconds,
        notification_retry_max_seconds=notification_retry_max_seconds,
        notification_max_attempts=notification_max_attempts,
        db_pool_size=db_pool_size,
        db_max_overflow=db_max_overflow,
        db_pool_timeout=db_pool_timeout,
        db_pool_recycle=db_pool_recycle,
    )

    _warn_sqlite_inside_repo(sync_url, environment)

    return settings
