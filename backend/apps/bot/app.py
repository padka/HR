"""Application factory for the Telegram bot."""

from __future__ import annotations

import asyncio
import logging
from aiogram import Bot, Dispatcher

from .config import BOT_TOKEN, DEFAULT_BOT_PROPERTIES
from .handlers import register_routers
from .reminders import AsyncioReminderQueue, ReminderQueue
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


def create_application(
    token: str | None = None,
    *,
    dispatcher: Dispatcher | None = None,
    state_manager: StateManager | None = None,
    reminder_queue: ReminderQueue | None = None,
) -> BotContext:
    """Create and configure the bot application components.

    Parameters
    ----------
    token:
        Explicit bot token override. Falls back to :data:`BOT_TOKEN` when ``None``.
    dispatcher:
        Optional dispatcher instance. Supplying a pre-configured dispatcher
        allows the caller to attach custom middlewares before routers are
        registered.
    state_manager:
        Optional state storage implementation. Defaults to the in-memory
        :class:`StateManager`, but callers can inject a persistent
        alternative.
    reminder_queue:
        Optional reminder queue implementation. When omitted, an in-memory
        :class:`AsyncioReminderQueue` is created. Supplying a custom queue allows
        embedding persistent schedulers (Redis, APScheduler, etc.) without
        touching business logic.
    """
    bot = create_bot(token)
    dispatcher = dispatcher or create_dispatcher()
    state_manager = state_manager or StateManager()
    context = BotContext(
        bot=bot,
        dispatcher=dispatcher,
        state_manager=state_manager,
        reminder_queue=reminder_queue or AsyncioReminderQueue(),
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
