from __future__ import annotations

import os
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
    bot_token: str
    admin_chat_id: int
    timezone: str
    session_secret: str
    enable_test2_bot: bool


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

    bot_token = os.getenv("BOT_TOKEN", "")
    admin_chat_id = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
    timezone = os.getenv("TZ", "Europe/Moscow")
    session_secret = (
        os.getenv("SESSION_SECRET")
        or os.getenv("SECRET_KEY")
        or "dev-admin-session"
    )

    test2_bot_enabled = os.getenv("ENABLE_TEST2_BOT", "1")
    test2_bot_enabled = test2_bot_enabled.strip().lower()
    enable_test2_bot = test2_bot_enabled in {"1", "true", "yes", "on"}

    return Settings(
        data_dir=data_dir,
        database_url_async=async_url,
        database_url_sync=sync_url,
        sql_echo=os.getenv("SQL_ECHO", "0") in {"1", "true", "True"},
        bot_token=bot_token,
        admin_chat_id=admin_chat_id,
        timezone=timezone,
        session_secret=session_secret,
        enable_test2_bot=enable_test2_bot,
    )
