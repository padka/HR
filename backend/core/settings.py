from __future__ import annotations

import logging
import os
import secrets
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from backend.core.env import load_env


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_USER_DATA_DIR = Path.home() / ".recruitsmart_admin" / "data"


@dataclass(frozen=True)
class Settings:
    environment: str  # development, production, staging, test
    data_dir: Path
    database_url_async: str
    database_url_sync: str
    sql_echo: bool
    bot_enabled: bool
    bot_provider: str
    bot_token: str
    bot_api_base: str
    bot_callback_secret: str
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
    rate_limit_enabled: bool
    rate_limit_redis_url: str
    trust_proxy_headers: bool
    enable_legacy_status_api: bool


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




def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_bool_default_by_env(name: str, *, environment: str, default_non_prod: bool, default_prod: bool) -> bool:
    raw = os.getenv(name)
    if raw is not None:
        return _get_bool(name)
    return default_prod if environment == "production" else default_non_prod


def _get_bool_with_fallback(*names: str, default: bool = False) -> bool:
    for name in names:
        if os.getenv(name) is not None:
            return _get_bool(name)
    return default




def _get_repo_root() -> Path:
    """
    Determine repository root robustly.
    Tries git rev-parse first, falls back to PROJECT_ROOT heuristic.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except Exception:
        pass
    # Fallback to PROJECT_ROOT
    return PROJECT_ROOT.resolve()


def _validate_production_settings(settings: Settings) -> None:
    """
    Validate production configuration to prevent common deployment errors.

    Only applies strict validation when ENVIRONMENT=production.
    Raises RuntimeError with actionable messages if configuration is invalid.
    """
    if settings.environment.lower() != "production":
        return

    errors = []
    warnings = []

    # 1. SESSION_SECRET must be explicitly set in production
    session_secret_env = os.getenv("SESSION_SECRET") or os.getenv("SECRET_KEY")
    if not session_secret_env:
        errors.append(
            "Production requires SESSION_SECRET to be explicitly set. "
            "Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    elif len(settings.session_secret) < 32:
        errors.append(
            f"SESSION_SECRET too short (got {len(settings.session_secret)} chars, need 32+). "
            "Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    elif any(token in settings.session_secret.lower() for token in {"changeme", "change_me", "session_secret", "changemesecret"}):
        errors.append(
            "SESSION_SECRET contains placeholder/default text. "
            "Generate a fresh secret with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )

    callback_secret_env = os.getenv("BOT_CALLBACK_SECRET") or ""
    if not callback_secret_env:
        errors.append(
            "Production requires BOT_CALLBACK_SECRET to be explicitly set (32+ chars). "
            "Generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    elif len(callback_secret_env.strip()) < 32:
        errors.append(
            "BOT_CALLBACK_SECRET too short (min 32 characters). "
            "Generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    elif callback_secret_env.strip() == settings.session_secret:
        errors.append("BOT_CALLBACK_SECRET must differ from SESSION_SECRET.")

    admin_password_env = os.getenv("ADMIN_PASSWORD", "")
    if not admin_password_env:
        errors.append(
            "Production requires ADMIN_PASSWORD to be set. "
            "Generate a strong password (16+ chars, mixed case, numbers, symbols)."
        )
    else:
        normalized_pwd = settings.admin_password.strip()
        weak_tokens = {"admin", "password", "changeme", "change_me", "qwerty", "123456", "123456789"}
        if len(normalized_pwd) < 12:
            errors.append(
                "ADMIN_PASSWORD too short for production (must be at least 12 characters). "
                "Generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(24))\""
            )
        if any(token in normalized_pwd.lower() for token in weak_tokens):
            errors.append(
                "ADMIN_PASSWORD contains a common/placeholder value. "
                "Use a unique, random password instead."
            )

    # 2. DATABASE_URL must be PostgreSQL with asyncpg
    db_url = settings.database_url_async

    if not db_url or not db_url.startswith("postgresql+asyncpg://"):
        errors.append(
            "Production requires DATABASE_URL with postgresql+asyncpg driver. "
            "Example: DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname"
        )

    # 3. REDIS_URL must be set
    if not settings.redis_url:
        errors.append(
            "Production requires REDIS_URL to be set. "
            "Example: REDIS_URL=redis://localhost:6379/0"
        )

    # 4. NOTIFICATION_BROKER must be redis
    if settings.notification_broker != "redis":
        errors.append(
            f"Production requires NOTIFICATION_BROKER=redis (got: {settings.notification_broker}). "
            "Set: NOTIFICATION_BROKER=redis"
        )

    # 5. DATA_DIR must exist, be outside repo, and be writable
    data_dir = settings.data_dir.resolve()
    repo_root = _get_repo_root()

    # Check if DATA_DIR is inside repo
    try:
        if data_dir == repo_root or repo_root in data_dir.parents or data_dir in repo_root.parents:
            # data_dir is inside or equal to repo_root
            if data_dir.is_relative_to(repo_root):
                errors.append(
                    f"Production requires DATA_DIR outside repo. "
                    f"Current DATA_DIR ({data_dir}) is inside repo ({repo_root}). "
                    f"Example: DATA_DIR=/var/lib/recruitsmart_admin"
                )
    except (ValueError, AttributeError):
        # Fallback for Python < 3.9 without is_relative_to
        try:
            data_dir.relative_to(repo_root)
            errors.append(
                f"Production requires DATA_DIR outside repo. "
                f"Current DATA_DIR ({data_dir}) is inside repo ({repo_root}). "
                f"Example: DATA_DIR=/var/lib/recruitsmart_admin"
            )
        except ValueError:
            # data_dir is not relative to repo_root, which is good
            pass

    # Check DATA_DIR is writable
    if data_dir.exists():
        if not os.access(data_dir, os.W_OK):
            errors.append(
                f"DATA_DIR exists but is not writable: {data_dir}. "
                f"Fix with: sudo chown $USER:$USER {data_dir}"
            )
        else:
            # Try actually creating a file to verify write permissions
            test_file = data_dir / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                errors.append(
                    f"DATA_DIR permissions check failed: {e}. "
                    f"Ensure {data_dir} is writable."
                )

    # 6. Redis connectivity check (warning only - may not be available during config phase)
    if settings.redis_url:
        try:
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(settings.redis_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379

            # Quick socket connectivity test (2 second timeout)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                sock.connect((host, port))
                sock.close()
            except (socket.timeout, socket.error, OSError) as e:
                warnings.append(
                    f"Could not verify Redis connectivity at {host}:{port}: {e}. "
                    f"Redis may not be running or may not be accessible."
                )
        except Exception:
            # Don't fail on import or parsing errors
            pass

    # 7. Rate limiting Redis validation
    if settings.rate_limit_enabled:
        if not settings.rate_limit_redis_url:
            errors.append(
                "Production rate limiting requires RATE_LIMIT_REDIS_URL or REDIS_URL to be set. "
                "Example: RATE_LIMIT_REDIS_URL=redis://localhost:6379/1"
            )
        else:
            # Test connectivity to rate limiting Redis (similar to existing Redis check)
            try:
                import socket
                from urllib.parse import urlparse
                parsed = urlparse(settings.rate_limit_redis_url)
                host = parsed.hostname or "localhost"
                port = parsed.port or 6379

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                try:
                    sock.connect((host, port))
                    sock.close()
                except (socket.timeout, socket.error, OSError) as e:
                    warnings.append(
                        f"Could not verify rate limiting Redis connectivity at {host}:{port}: {e}. "
                        f"Rate limiting may not work correctly."
                    )
            except Exception:
                pass

    if settings.session_cookie_secure is False:
        errors.append("SESSION_COOKIE_SECURE must be enabled in production.")

    # Print warnings to stderr
    if warnings:
        import sys
        for warning in warnings:
            print(f"\n⚠ WARNING: {warning}", file=sys.stderr)

    if errors:
        error_msg = "\n\n".join([f"  ✗ {err}" for err in errors])
        raise RuntimeError(
            f"\n\n{'=' * 70}\n"
            f"PRODUCTION CONFIGURATION ERRORS\n"
            f"{'=' * 70}\n\n"
            f"{error_msg}\n\n"
            f"{'=' * 70}\n"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Determine environment (default to development for safety)
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    if environment not in {"development", "production", "staging", "test"}:
        environment = "development"

    data_dir = _default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    # DATABASE_URL is required in all environments
    db_url_env = os.getenv("DATABASE_URL")
    if not db_url_env or not db_url_env.strip():
        raise RuntimeError(
            "DATABASE_URL environment variable is required. "
            "This project requires PostgreSQL in all environments (dev/test/prod). "
            "Example: DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname"
        )

    raw_db_url = db_url_env.strip()

    # Ensure it's PostgreSQL (prod), но позволяем SQLite в dev/test
    if not raw_db_url.startswith(("postgresql+asyncpg://", "postgresql://")):
        if environment in {"development", "test"} and raw_db_url.startswith("sqlite"):
            pass
        else:
            raise RuntimeError(
                f"DATABASE_URL must use PostgreSQL with asyncpg driver. Got: {raw_db_url[:30]}... "
                f"Example: DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname"
            )

    # Normalize to postgresql+asyncpg if just postgresql://
    if raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+asyncpg://"):
        raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # In dev, allow replacing docker-style hostnames with localhost to avoid DNS errors
    if environment == "development":
        try:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(raw_db_url)
            if parsed.hostname == "postgres":
                # Preserve userinfo/port, replace host with localhost
                userinfo = ""
                if parsed.username:
                    userinfo = parsed.username
                    if parsed.password:
                        userinfo += f":{parsed.password}"
                    userinfo += "@"
                hostport = "localhost"
                if parsed.port:
                    hostport += f":{parsed.port}"
                new_netloc = f"{userinfo}{hostport}"
                rebuilt = urlunparse(
                    (
                        parsed.scheme,
                        new_netloc,
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment,
                    )
                )
                if rebuilt:
                    raw_db_url = rebuilt
        except Exception:
            pass

    async_url = raw_db_url
    # Sync URL: remove async driver suffix; adjust sqlite driver name
    if raw_db_url.startswith("sqlite+aiosqlite"):
        sync_url = raw_db_url.replace("+aiosqlite", "")
    else:
        sync_url = raw_db_url.replace("+asyncpg", "")

    bot_enabled = _get_bool_with_fallback("BOT_ENABLED", "ENABLE_TEST2_BOT", default=True)
    bot_provider = os.getenv("BOT_PROVIDER", "telegram").strip().lower() or "telegram"
    bot_token = os.getenv("BOT_TOKEN", "")
    bot_api_base = os.getenv("BOT_API_BASE", "").strip()
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url.startswith("redis://redis_notifications") and environment != "production":
        redis_url = redis_url.replace("redis_notifications", "localhost", 1)
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
    bot_callback_secret_env = os.getenv("BOT_CALLBACK_SECRET", "").strip()
    bot_callback_secret = bot_callback_secret_env or secrets.token_urlsafe(32)

    # Validate SESSION_SECRET strength (for all environments)
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
    # Length validation moved to _validate_production_settings() for production only

    admin_username = os.getenv("ADMIN_USER", "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
    admin_docs_enabled = _get_bool("ADMIN_DOCS_ENABLED", default=False)
    # Keep secure cookies in production, but allow HTTP cookies in dev/test so CSRF/session work locally
    session_cookie_secure = _get_bool("SESSION_COOKIE_SECURE", default=environment == "production")
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
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = str(log_dir / "app.log")
        except (PermissionError, OSError):
            # If we can't create log dir, defer to production validation
            # Use a fallback path for now
            log_file = str(data_dir / "app.log")

    # Database connection pool settings
    db_pool_size = _get_int("DB_POOL_SIZE", 20, minimum=1)
    db_max_overflow = _get_int("DB_MAX_OVERFLOW", 10, minimum=0)
    db_pool_timeout = _get_int("DB_POOL_TIMEOUT", 30, minimum=1)
    db_pool_recycle = _get_int("DB_POOL_RECYCLE", 3600, minimum=60)

    # Rate limiting configuration
    rate_limit_enabled = _get_bool("RATE_LIMIT_ENABLED", default=environment == "production")
    rate_limit_redis_url_env = os.getenv("RATE_LIMIT_REDIS_URL", "").strip()

    # Default to REDIS_URL with /1 database if not explicitly set
    if not rate_limit_redis_url_env and redis_url:
        # Parse existing redis_url and change DB to 1
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(redis_url)
            # Replace path (database) with /1
            new_parsed = parsed._replace(path="/1")
            rate_limit_redis_url = urlunparse(new_parsed)
        except Exception:
            rate_limit_redis_url = redis_url  # fallback to same URL
    else:
        rate_limit_redis_url = rate_limit_redis_url_env

    # Apply same localhost substitution for dev environment
    if rate_limit_redis_url and rate_limit_redis_url.startswith("redis://redis_notifications") and environment != "production":
        rate_limit_redis_url = rate_limit_redis_url.replace("redis_notifications", "localhost", 1)

    trust_proxy_headers = _get_bool("TRUST_PROXY_HEADERS", default=False)
    enable_legacy_status_api = _get_bool_default_by_env(
        "ENABLE_LEGACY_STATUS_API",
        environment=environment,
        default_non_prod=False,
        default_prod=False,
    )

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
        bot_callback_secret=bot_callback_secret,
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
        rate_limit_enabled=rate_limit_enabled,
        rate_limit_redis_url=rate_limit_redis_url,
        trust_proxy_headers=trust_proxy_headers,
        enable_legacy_status_api=enable_legacy_status_api,
    )

    # Validate production configuration (fails fast with clear error messages)
    _validate_production_settings(settings)

    return settings
