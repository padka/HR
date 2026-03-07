"""VK Max adapter — MessengerProtocol implementation.

Uses the VK Max Bot API (https://dev.max.ru/docs-api) which is a simple
HTTP JSON API. No heavy SDK dependency required.

Bot API docs: https://platform-api.max.ru
Auth: Authorization header with bot token.
Rate limit: 30 rps.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.core.messenger.protocol import (
    InlineButton,
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)

logger = logging.getLogger(__name__)

MAX_API_BASE = "https://platform-api.max.ru"


class MaxAdapter(MessengerProtocol):
    """MessengerProtocol implementation for VK Max messenger.

    Configuration requires a bot token obtained from @MaxMasterBot.
    """

    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._base_url: str = MAX_API_BASE
        self._client: Any = None  # httpx.AsyncClient
        self._max_retries: int = 3
        self._base_delay: float = 1.0

    async def configure(
        self,
        *,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with bot token.

        Args:
            token: VK Max bot token from @MaxMasterBot.
            base_url: Override API base URL (for testing).
        """
        if token:
            self._token = token
        if base_url:
            self._base_url = base_url.rstrip("/")

        if not self._token:
            raise ValueError("MaxAdapter requires a bot token (MAX_BOT_TOKEN).")

        try:
            import httpx

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(15.0),
                headers={
                    "Accept": "application/json",
                    "Authorization": self._token,
                },
            )
        except ImportError:
            logger.warning("httpx not installed; MaxAdapter will not function.")

    def _ensure_ready(self) -> None:
        if self._client is None or self._token is None:
            raise RuntimeError(
                "MaxAdapter is not configured. Call configure(token=...) first."
            )

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        buttons: Optional[List[List[InlineButton]]] = None,
        parse_mode: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> SendResult:
        """Send a message via VK Max Bot API.

        Max Bot API endpoint: POST /messages
        Auth: Authorization header with bot token.
        Body: {"chat_id": ..., "text": ..., "attachments": [...]}
        """
        self._ensure_ready()

        payload: Dict[str, Any] = {
            "chat_id": int(chat_id) if isinstance(chat_id, str) and chat_id.isdigit() else chat_id,
            "text": text,
        }

        # Max uses "inline_keyboard" attachments for buttons
        if buttons:
            keyboard_buttons: List[List[Dict[str, Any]]] = []
            for row in buttons:
                keyboard_row = []
                for btn in row:
                    keyboard_row.append(
                        {
                            "type": "callback",
                            "text": btn.text,
                            "payload": btn.callback_data,
                        }
                    )
                keyboard_buttons.append(keyboard_row)

            payload["attachments"] = [
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": keyboard_buttons},
                }
            ]

        attempt = 0
        last_error: Optional[str] = None

        while attempt < self._max_retries:
            attempt += 1
            try:
                resp = await self._client.post(  # type: ignore[union-attr]
                    "/messages",
                    json=payload,
                )
                data = resp.json()

                if resp.status_code == 200 and data.get("success", data.get("ok", False)):
                    msg = data.get("message", {})
                    return SendResult(
                        success=True,
                        message_id=str(msg.get("mid", msg.get("message_id", ""))),
                        raw_response=data,
                    )

                # API error
                error_text = data.get("description") or data.get("error", str(data))
                last_error = f"HTTP {resp.status_code}: {error_text}"

                # Non-retryable errors
                if resp.status_code in (400, 403, 404):
                    logger.warning(
                        "max_adapter.send_rejected",
                        extra={"chat_id": chat_id, "error": last_error},
                    )
                    return SendResult(success=False, error=last_error, raw_response=data)

            except Exception as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"

            # Retry with backoff
            if attempt < self._max_retries:
                delay = self._base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "max_adapter.send_retry",
                    extra={
                        "chat_id": chat_id,
                        "attempt": attempt,
                        "delay": delay,
                        "error": last_error,
                    },
                )
                await asyncio.sleep(delay)

        logger.error(
            "max_adapter.send_failed",
            extra={"chat_id": chat_id, "attempts": attempt, "error": last_error},
        )
        return SendResult(success=False, error=last_error)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
