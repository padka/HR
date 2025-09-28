"""Application factory for the Telegram bot."""

from __future__ import annotations

import asyncio
import logging
from typing import Tuple

from aiogram import Bot, Dispatcher

from .config import BOT_TOKEN, DEFAULT_BOT_PROPERTIES
from .handlers import register_routers
from .services import StateManager, configure as configure_services

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


def create_application(token: str | None = None) -> Tuple[Bot, Dispatcher, StateManager]:
    """Create and configure the bot application components."""
    bot = create_bot(token)
    dispatcher = create_dispatcher()
    state_manager = StateManager()
    configure_services(bot, state_manager)
    return bot, dispatcher, state_manager


async def main() -> None:
    bot, dispatcher, _ = create_application()
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    logging.warning("BOOT: using bot id=%s, username=@%s", me.id, me.username)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
