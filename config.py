"""Legacy config shim keeping backwards compatibility."""

from backend.core.settings import get_settings

settings = get_settings()

BOT_TOKEN = settings.bot_token
ADMIN_CHAT_ID = settings.admin_chat_id
MODE = "polling"
TZ = settings.timezone

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Put it in /opt/tg-bot/.env")
