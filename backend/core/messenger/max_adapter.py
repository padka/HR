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

    @property
    def is_ready(self) -> bool:
        return self._client is not None and bool(self._token)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> tuple[Any, Dict[str, Any]]:
        self._ensure_ready()
        response = await self._client.request(  # type: ignore[union-attr]
            method,
            path,
            params=params,
            json=json_body,
        )
        try:
            data = response.json()
        except Exception:
            data = {"raw_text": getattr(response, "text", "")}
        if not isinstance(data, dict):
            data = {"data": data}
        return response, data

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        buttons: Optional[List[List[InlineButton]]] = None,
        parse_mode: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> SendResult:
        """Send a message via VK MAX Bot API."""
        self._ensure_ready()

        params: Dict[str, Any] = {
            "user_id": int(chat_id) if isinstance(chat_id, str) and chat_id.isdigit() else chat_id,
        }
        payload: Dict[str, Any] = {
            "text": text,
        }
        if parse_mode:
            normalized_mode = str(parse_mode).strip().lower()
            if normalized_mode in {"html", "markdown", "markdownv2"}:
                payload["format"] = "html" if normalized_mode == "html" else "markdown"

        # Max uses "inline_keyboard" attachments for buttons
        if buttons:
            keyboard_buttons: List[List[Dict[str, Any]]] = []
            for row in buttons:
                keyboard_row = []
                for btn in row:
                    if btn.url:
                        keyboard_row.append(
                            {
                                "type": "link",
                                "text": btn.text,
                                "url": btn.url,
                            }
                        )
                    else:
                        keyboard_row.append(
                            {
                                "type": "callback",
                                "text": btn.text,
                                "payload": btn.callback_data or "",
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
                resp, data = await self._request_json(
                    "POST",
                    "/messages",
                    params=params,
                    json_body=payload,
                )
                msg = data.get("message", {}) if isinstance(data, dict) else {}
                message_id = str(
                    msg.get("mid")
                    or msg.get("message_id")
                    or data.get("mid")
                    or data.get("message_id")
                    or ""
                )
                success = 200 <= resp.status_code < 300

                if success:
                    if not message_id and isinstance(data, dict):
                        if any(key in data for key in ("error", "description")) and not (
                            bool(data.get("success")) or bool(data.get("ok"))
                        ):
                            logger.warning(
                                "max_adapter.send_unexpected_success_body",
                                extra={"chat_id": chat_id, "response": data},
                            )
                    return SendResult(
                        success=True,
                        message_id=message_id or None,
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

    async def answer_callback(
        self,
        callback_id: str,
        *,
        notification: Optional[str] = None,
        message: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Acknowledge a MAX callback button click."""
        body: Dict[str, Any] = {}
        if message is not None:
            body["message"] = message
        if notification:
            body["notification"] = notification

        response, data = await self._request_json(
            "POST",
            "/answers",
            params={"callback_id": callback_id},
            json_body=body,
        )
        success = response.status_code == 200 and bool(data.get("success", True))
        if success:
            return SendResult(success=True, raw_response=data)
        error_text = data.get("message") or data.get("error") or str(data)
        return SendResult(success=False, error=f"HTTP {response.status_code}: {error_text}", raw_response=data)

    async def list_subscriptions(self) -> List[Dict[str, Any]]:
        """Return current webhook subscriptions."""
        response, data = await self._request_json("GET", "/subscriptions")
        if response.status_code != 200:
            raise RuntimeError(f"MAX list_subscriptions failed: HTTP {response.status_code}")
        subscriptions = data.get("subscriptions") or []
        return [item for item in subscriptions if isinstance(item, dict)]

    async def create_subscription(
        self,
        *,
        url: str,
        update_types: List[str],
        secret: Optional[str] = None,
    ) -> SendResult:
        body: Dict[str, Any] = {
            "url": url,
            "update_types": update_types,
        }
        if secret:
            body["secret"] = secret
        response, data = await self._request_json("POST", "/subscriptions", json_body=body)
        success = response.status_code == 200 and bool(data.get("success", True))
        if success:
            return SendResult(success=True, raw_response=data)
        error_text = data.get("message") or data.get("error") or str(data)
        return SendResult(success=False, error=f"HTTP {response.status_code}: {error_text}", raw_response=data)

    async def delete_subscription(self, *, url: str) -> SendResult:
        response, data = await self._request_json(
            "DELETE",
            "/subscriptions",
            params={"url": url},
        )
        success = response.status_code == 200 and bool(data.get("success", True))
        if success:
            return SendResult(success=True, raw_response=data)
        error_text = data.get("message") or data.get("error") or str(data)
        return SendResult(success=False, error=f"HTTP {response.status_code}: {error_text}", raw_response=data)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
