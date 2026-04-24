"""Bounded MAX messenger adapter under explicit opt-in only."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.core.messenger.protocol import (
    InlineButton,
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)
from backend.core.messenger.registry import get_registry

logger = logging.getLogger(__name__)

MAX_API_BASE = "https://platform-api.max.ru"


class MaxAdapter(MessengerProtocol):
    """Minimal MAX adapter for the shared messenger seam.

    The adapter stays inert until configured with an explicit bot token.
    It is safe to instantiate in environments where MAX rollout is disabled.
    """

    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self._token: str | None = None
        self._base_url = MAX_API_BASE
        self._client: Any = None
        self._max_retries = 3
        self._base_delay = 1.0
        self._public_bot_name: str | None = None
        self._miniapp_url: str | None = None

    @property
    def is_configured(self) -> bool:
        return self._client is not None and bool(self._token)

    async def configure(
        self,
        *,
        token: str | None = None,
        base_url: str | None = None,
        public_bot_name: str | None = None,
        miniapp_url: str | None = None,
        client: Any = None,
        **_: Any,
    ) -> None:
        if token is not None:
            cleaned_token = token.strip()
            self._token = cleaned_token or None
        if base_url:
            self._base_url = base_url.rstrip("/")
        if public_bot_name is not None:
            cleaned_name = public_bot_name.strip()
            self._public_bot_name = cleaned_name or None
        if miniapp_url is not None:
            cleaned_url = miniapp_url.strip()
            self._miniapp_url = cleaned_url or None
        if client is not None:
            self._client = client
            return
        if not self._token:
            self._client = None
            logger.info("messenger.max_adapter.disabled")
            return

        try:
            import httpx
        except ImportError:
            self._client = None
            logger.warning("messenger.max_adapter.httpx_missing")
            return

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(15.0),
            headers={
                "Accept": "application/json",
                "Authorization": self._token,
            },
        )

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        buttons: list[list[InlineButton]] | None = None,
        parse_mode: str | None = None,
        correlation_id: str | None = None,
    ) -> SendResult:
        del correlation_id
        if not self.is_configured:
            return SendResult(success=False, error="bot_not_configured")

        params: dict[str, Any] = {
            "user_id": int(chat_id)
            if isinstance(chat_id, str) and chat_id.isdigit()
            else chat_id,
        }
        payload: dict[str, Any] = {"text": text}
        if parse_mode:
            normalized_mode = str(parse_mode).strip().lower()
            if normalized_mode in {"html", "markdown", "markdownv2"}:
                payload["format"] = "html" if normalized_mode == "html" else "markdown"
        attachments = self._build_attachments(buttons)
        if attachments:
            payload["attachments"] = attachments

        attempt = 0
        last_error: str | None = None
        while attempt < self._max_retries:
            attempt += 1
            try:
                response, data = await self._request_json(
                    "POST",
                    "/messages",
                    params=params,
                    json_body=payload,
                )
            except Exception as exc:  # pragma: no cover - defensive path
                last_error = f"{exc.__class__.__name__}: {exc}"
            else:
                message_id = self._extract_message_id(data)
                if 200 <= response.status_code < 300:
                    return SendResult(
                        success=True,
                        message_id=message_id,
                        raw_response=data,
                    )
                error_text = (
                    data.get("description")
                    or data.get("error")
                    or data.get("message")
                    or str(data)
                )
                last_error = f"HTTP {response.status_code}: {error_text}"
                if response.status_code in {400, 401, 403, 404}:
                    return SendResult(
                        success=False, error=last_error, raw_response=data
                    )

            if attempt < self._max_retries:
                await asyncio.sleep(self._base_delay * (2 ** (attempt - 1)))

        return SendResult(success=False, error=last_error or "unknown_error")

    async def get_bot_profile(self) -> dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("MAX adapter is not configured.")
        response, data = await self._request_json("GET", "/me")
        if not 200 <= response.status_code < 300:
            message = (
                data.get("description")
                or data.get("error")
                or "MAX profile unavailable"
            )
            raise RuntimeError(str(message))
        return data

    async def get_me(self) -> dict[str, Any]:
        return await self.get_bot_profile()

    async def answer_callback(
        self,
        callback_id: str,
        *,
        message: dict[str, Any] | None = None,
        notification: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("MAX adapter is not configured.")
        normalized_callback_id = str(callback_id or "").strip()
        if not normalized_callback_id:
            raise RuntimeError("MAX callback_id is required.")

        payload: dict[str, Any] = {}
        if message is not None:
            payload["message"] = message
        if notification:
            payload["notification"] = notification

        response, data = await self._request_json(
            "POST",
            "/answers",
            params={"callback_id": normalized_callback_id},
            json_body=payload or None,
        )
        if not 200 <= response.status_code < 300:
            raise RuntimeError(
                data.get("description")
                or data.get("error")
                or data.get("message")
                or "MAX callback answer failed"
            )
        return data

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        if not self.is_configured:
            raise RuntimeError("MAX adapter is not configured.")
        response, data = await self._request_json("GET", "/subscriptions")
        if not 200 <= response.status_code < 300:
            raise RuntimeError(
                data.get("description")
                or data.get("error")
                or data.get("message")
                or "MAX subscriptions unavailable"
            )
        items = data.get("subscriptions") if isinstance(data, dict) else None
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []

    async def create_subscription(
        self,
        *,
        url: str,
        update_types: list[str],
        secret: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("MAX adapter is not configured.")
        payload: dict[str, Any] = {
            "url": str(url or "").strip(),
            "update_types": [str(item).strip() for item in update_types if str(item).strip()],
        }
        if secret:
            payload["secret"] = str(secret).strip()
        response, data = await self._request_json(
            "POST",
            "/subscriptions",
            json_body=payload,
        )
        if not 200 <= response.status_code < 300:
            raise RuntimeError(
                data.get("description")
                or data.get("error")
                or data.get("message")
                or "MAX subscription create failed"
            )
        return data

    async def delete_subscription(self, *, url: str) -> dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("MAX adapter is not configured.")
        response, data = await self._request_json(
            "DELETE",
            "/subscriptions",
            params={"url": str(url or "").strip()},
        )
        if not 200 <= response.status_code < 300:
            raise RuntimeError(
                data.get("description")
                or data.get("error")
                or data.get("message")
                or "MAX subscription delete failed"
            )
        return data

    async def close(self) -> None:
        client = self._client
        self._client = None
        if client is not None and hasattr(client, "aclose"):
            await client.aclose()

    def _build_attachments(
        self,
        buttons: list[list[InlineButton]] | None,
    ) -> list[dict[str, object]] | None:
        if not buttons:
            return None

        keyboard_rows: list[list[dict[str, object]]] = []
        for row in buttons:
            keyboard_row: list[dict[str, object]] = []
            for button in row:
                kind = str(button.kind or "").strip().lower()
                if kind in {"open_app", "web_app"} and button.url:
                    keyboard_row.append(
                        {
                            "type": "open_app",
                            "text": button.text,
                            "webApp": button.url,
                        }
                    )
                    continue
                if button.url:
                    keyboard_row.append(
                        {
                            "type": "link",
                            "text": button.text,
                            "url": button.url,
                        }
                    )
                    continue
                keyboard_row.append(
                    {
                        "type": "message"
                        if kind == "message"
                        else "callback",
                        "text": button.text,
                        "payload": button.callback_data or "",
                    }
                )
            keyboard_rows.append(keyboard_row)

        return [{"type": "inline_keyboard", "payload": {"buttons": keyboard_rows}}]

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        if not self.is_configured:
            raise RuntimeError("MAX adapter is not configured.")
        response = await self._client.request(  # type: ignore[union-attr]
            method,
            path,
            params=params,
            json=json_body,
        )
        try:
            payload = response.json()
        except Exception:
            payload = {"raw_text": getattr(response, "text", "")}
        if not isinstance(payload, dict):
            payload = {"data": payload}
        return response, payload

    def _extract_message_id(self, payload: dict[str, Any]) -> str | None:
        message = payload.get("message")
        if isinstance(message, dict):
            raw = message.get("mid") or message.get("message_id")
            if raw is not None:
                return str(raw)
        for key in ("mid", "message_id"):
            raw = payload.get(key)
            if raw is not None:
                return str(raw)
        return None


async def bootstrap_max_adapter_shell(*, config: Any = None, settings: Any | None = None) -> MaxAdapter:
    del settings
    if config is None:
        raise RuntimeError("MAX shell bootstrap requires resolved config.")

    adapter = MaxAdapter()
    await adapter.configure(
        token=getattr(config, "bot_token", None),
        public_bot_name=getattr(config, "public_bot_name", None),
        miniapp_url=getattr(config, "miniapp_url", None),
    )
    get_registry().register(adapter)
    logger.info(
        "messenger.max_adapter.shell_bootstrap_ready",
        extra={
            "configured": adapter.is_configured,
            "has_miniapp_url": bool(getattr(config, "miniapp_url", "")),
        },
    )
    return adapter
