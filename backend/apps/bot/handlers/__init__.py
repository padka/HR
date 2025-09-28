"""Router registrations for bot handlers."""

from __future__ import annotations

from typing import Any

from aiogram import Dispatcher
from aiogram import Router
from aiogram.types import TelegramObject
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from ..services import BotContext
from . import attendance, common, recruiter, slots, test1, test2

__all__ = ["register_routers"]


class ContextMiddleware(BaseMiddleware):
    """Inject the bot context into handler data."""

    def __init__(self, context: BotContext) -> None:
        super().__init__()
        self._context = context

    async def __call__(
        self,
        handler,
        event: TelegramObject,
        data: dict,
    ) -> Any:
        data.setdefault("context", self._context)
        return await handler(event, data)


def _register_with_context(dp: Dispatcher, router: Router, context: BotContext) -> None:
    router.message.middleware.register(ContextMiddleware(context))
    router.callback_query.middleware.register(ContextMiddleware(context))
    dp.include_router(router)


def register_routers(dp: Dispatcher, context: BotContext) -> None:
    """Include all bot routers into the dispatcher."""

    for router in (
        common.router,
        test1.router,
        test2.router,
        slots.router,
        recruiter.router,
        attendance.router,
    ):
        _register_with_context(dp, router, context)
