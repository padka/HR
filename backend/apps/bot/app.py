"""Application factory for the Telegram bot."""

from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher

from .config import BOT_TOKEN, DEFAULT_BOT_PROPERTIES
from .handlers import register_routers
from .reminders import AsyncioReminderQueue
from .services import BotContext, StateManager

__all__ = [
    "BotContext",
    "create_application",
    "create_bot",
    "create_dispatcher",
    "main",
]


def create_bot(token: str | None = None) -> Bot:
    actual_token = token or BOT_TOKEN
    if not actual_token or ":" not in actual_token:
        raise RuntimeError(
            "BOT_TOKEN не найден или некорректен. Задай BOT_TOKEN=... (или используй .env)"
        )
    return Bot(token=actual_token, default=DEFAULT_BOT_PROPERTIES)


def create_dispatcher() -> Dispatcher:
    return Dispatcher()


def create_application(token: str | None = None) -> BotContext:
    """Create and configure the bot application components."""
    bot = create_bot(token)
    dispatcher = create_dispatcher()
    state_manager = StateManager()
    context = BotContext(
        bot=bot,
        dispatcher=dispatcher,
        state_manager=state_manager,
        reminder_queue=AsyncioReminderQueue(),
    )
    register_routers(dispatcher, context)
    return context


async def main() -> None:
    context = create_application()
    await context.bot.delete_webhook(drop_pending_updates=True)
    me = await context.bot.get_me()
    logging.warning("BOOT: using bot id=%s, username=@%s", me.id, me.username)
    await context.dispatcher.start_polling(context.bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
