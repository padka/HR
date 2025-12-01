"""Aiogram middleware helpers."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from backend.domain.candidates import link_telegram_identity, log_inbound_chat_message

logger = logging.getLogger(__name__)


def _extract_from_user(event: TelegramObject) -> Optional[Any]:
    direct = getattr(event, "from_user", None)
    if direct:
        return direct

    nested_attrs = (
        "message",
        "edited_message",
        "callback_query",
        "inline_query",
        "chosen_inline_result",
        "shipping_query",
        "pre_checkout_query",
        "my_chat_member",
        "chat_member",
        "chat_join_request",
    )

    for attr in nested_attrs:
        nested = getattr(event, attr, None)
        if not nested:
            continue
        user = getattr(nested, "from_user", None)
        if user:
            return user
        inner_message = getattr(nested, "message", None)
        if inner_message and getattr(inner_message, "from_user", None):
            return inner_message.from_user
    return None


class TelegramIdentityMiddleware(BaseMiddleware):
    """Persist Telegram identifiers for every incoming update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from_user = _extract_from_user(event)
        if from_user is not None:
            user_id = getattr(from_user, "id", None)
            if user_id:
                username = getattr(from_user, "username", None)
                try:
                    await link_telegram_identity(
                        telegram_user_id=user_id,
                        username=username,
                    )
                except Exception:  # pragma: no cover - guard rails
                    logger.exception(
                        "Failed to persist Telegram identity",
                        extra={"telegram_user_id": user_id},
                    )
        return await handler(event, data)


class InboundChatLoggingMiddleware(BaseMiddleware):
    """Store inbound Telegram messages in chat history."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            await _log_inbound_message(event)
        return await handler(event, data)


async def _log_inbound_message(message: Message) -> None:
    try:
        from_user = message.from_user
        chat = message.chat
        if not from_user or from_user.is_bot:
            return
        if chat and getattr(chat, "type", None) not in {"private"}:
            return
        text = message.text or message.caption or ""
        payload = None
        if message.sticker:
            payload = {"sticker": message.sticker.file_id}
            if not text:
                text = "[стикер]"
        elif message.photo:
            payload = {"photo": True}
            if not text:
                text = "[фото]"
        await log_inbound_chat_message(
            telegram_user_id=from_user.id,
            text=text,
            telegram_message_id=message.message_id,
            payload=payload,
            username=getattr(from_user, "username", None),
        )
    except Exception:  # pragma: no cover - logging guard
        logger.exception(
            "Failed to record inbound chat message",
            extra={"telegram_message_id": getattr(message, "message_id", None)},
        )
