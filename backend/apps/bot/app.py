"""Application factory for the Telegram bot."""

from __future__ import annotations

import asyncio
import logging
from typing import Tuple

from aiogram import Bot, Dispatcher

from backend.core.db import init_models
from backend.core.settings import get_settings

from .config import BOT_TOKEN, DEFAULT_BOT_PROPERTIES
from .handlers import register_routers
from .services import StateManager, configure as configure_services
from .reminders import (
    ReminderService,
    configure_reminder_service,
    create_scheduler,
)
from .state_store import build_state_manager

__all__ = ["create_application", "create_bot", "create_dispatcher", "main"]


def create_bot(token: str | None = None) -> Bot:
    actual_token = token or BOT_TOKEN
    if not actual_token or ":" not in actual_token:
        raise RuntimeError(
            "BOT_TOKEN не найден или некорректен. Задай BOT_TOKEN=... (или используй .env)"
        )
    return Bot(token=actual_token, default=DEFAULT_BOT_PROPERTIES)


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    register_routers(dispatcher)
    return dispatcher


async def create_application(
    token: str | None = None,
) -> Tuple[Bot, Dispatcher, StateManager, ReminderService]:
    """Create and configure the bot application components."""
    bot = create_bot(token)
    dispatcher = create_dispatcher()
    settings = get_settings()
    state_manager = build_state_manager(
        redis_url=getattr(settings, "redis_url", None),
        ttl_seconds=getattr(settings, "state_ttl_seconds", 604800),
    )
    scheduler = create_scheduler(getattr(settings, "redis_url", None))
    reminder_service = ReminderService(scheduler=scheduler)
    configure_reminder_service(reminder_service)
    await reminder_service.sync_jobs()
    configure_services(bot, state_manager)
    return bot, dispatcher, state_manager, reminder_service


async def main() -> None:
    bot, dispatcher, _, reminder_service = await create_application()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        me = await bot.get_me()
        logging.warning("BOOT: using bot id=%s, username=@%s", me.id, me.username)
        await init_models()
        await dispatcher.start_polling(bot)
    finally:
        await reminder_service.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
