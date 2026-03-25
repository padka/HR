"""Telegram adapter — wraps aiogram Bot into MessengerProtocol."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional

from backend.core.messenger.protocol import (
    InlineButton,
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)

logger = logging.getLogger(__name__)


class TelegramAdapter(MessengerProtocol):
    """MessengerProtocol implementation backed by aiogram Bot.

    This adapter delegates to the existing ``aiogram.Bot`` instance that is
    already configured elsewhere in the application (``bot/app.py``).
    """

    platform = MessengerPlatform.TELEGRAM

    def __init__(self) -> None:
        self._bot: Any = None  # aiogram.Bot — lazy to avoid import at module level
        self._max_retries: int = 3
        self._base_delay: float = 1.0

    async def configure(self, *, bot: Any = None, **kwargs: Any) -> None:
        """Accept an existing aiogram Bot instance.

        If *bot* is ``None``, the adapter will attempt to import
        ``get_bot()`` from the bot services module at send-time (lazy).
        """
        if bot is not None:
            self._bot = bot

    def _get_bot(self) -> Any:
        """Return the aiogram Bot, resolving lazily if needed."""
        if self._bot is not None:
            return self._bot
        # Lazy import to avoid circular deps and allow usage from admin_api
        from backend.apps.bot.services import get_bot

        return get_bot()

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        buttons: Optional[List[List[InlineButton]]] = None,
        parse_mode: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> SendResult:
        """Send a message via Telegram Bot API with retry logic."""
        from aiogram.types import InlineKeyboardButton as TgButton
        from aiogram.types import InlineKeyboardMarkup
        from aiogram.types import WebAppInfo

        bot = self._get_bot()

        # Build keyboard
        reply_markup = None
        if buttons:
            keyboard_rows = []
            for row in buttons:
                keyboard_row = []
                for btn in row:
                    kind = str(getattr(btn, "kind", "") or "").strip().lower()
                    button_url = getattr(btn, "url", None)
                    callback_data = getattr(btn, "callback_data", None)

                    if kind in {"open_app", "web_app"} and button_url:
                        keyboard_row.append(
                            TgButton(text=btn.text, web_app=WebAppInfo(url=button_url))
                        )
                        continue

                    if button_url:
                        keyboard_row.append(TgButton(text=btn.text, url=button_url))
                        continue

                    if callback_data is not None:
                        keyboard_row.append(TgButton(text=btn.text, callback_data=callback_data or ""))
                        continue

                    keyboard_row.append(TgButton(text=btn.text, callback_data=""))
                keyboard_rows.append(keyboard_row)
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        attempt = 0
        last_error: Optional[str] = None
        while attempt < self._max_retries:
            attempt += 1
            try:
                result = await bot.send_message(
                    chat_id,
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                return SendResult(
                    success=True,
                    message_id=str(result.message_id),
                )
            except Exception as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
                exc_name = exc.__class__.__name__

                # Non-retryable: blocked by user, chat not found
                if "Forbidden" in exc_name or "Unauthorized" in exc_name:
                    logger.warning(
                        "telegram_adapter.send_blocked",
                        extra={"chat_id": chat_id, "error": last_error},
                    )
                    return SendResult(success=False, error=last_error)

                # Retryable
                if attempt < self._max_retries:
                    delay = self._base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "telegram_adapter.send_retry",
                        extra={
                            "chat_id": chat_id,
                            "attempt": attempt,
                            "delay": delay,
                            "error": last_error,
                        },
                    )
                    await asyncio.sleep(delay)

        logger.error(
            "telegram_adapter.send_failed",
            extra={"chat_id": chat_id, "attempts": attempt, "error": last_error},
        )
        return SendResult(success=False, error=last_error)

    async def close(self) -> None:
        """No-op: the Bot lifecycle is managed by the bot application."""
        pass
