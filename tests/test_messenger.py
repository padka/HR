"""Tests for the messenger abstraction layer (Phase 2).

Covers:
- MessengerPlatform enum and parsing
- Protocol / SendResult dataclasses
- MessengerRegistry operations
- resolve_adapter_for_candidate logic
- TelegramAdapter send_message
- MaxAdapter send_message
- Bootstrap function
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.messenger.protocol import (
    InlineButton,
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)
from backend.core.messenger.registry import (
    MessengerRegistry,
    resolve_adapter_for_candidate,
)


# ── MessengerPlatform ────────────────────────────────────────────────────


class TestMessengerPlatform:
    def test_telegram_value(self):
        assert MessengerPlatform.TELEGRAM.value == "telegram"

    def test_max_value(self):
        assert MessengerPlatform.MAX.value == "max"

    def test_from_str_telegram(self):
        assert MessengerPlatform.from_str("telegram") == MessengerPlatform.TELEGRAM
        assert MessengerPlatform.from_str("tg") == MessengerPlatform.TELEGRAM
        assert MessengerPlatform.from_str("TELEGRAM") == MessengerPlatform.TELEGRAM

    def test_from_str_max(self):
        assert MessengerPlatform.from_str("max") == MessengerPlatform.MAX
        assert MessengerPlatform.from_str("vk_max") == MessengerPlatform.MAX
        assert MessengerPlatform.from_str("vkmax") == MessengerPlatform.MAX
        assert MessengerPlatform.from_str("icq") == MessengerPlatform.MAX

    def test_from_str_unknown(self):
        with pytest.raises(ValueError, match="Unknown messenger platform"):
            MessengerPlatform.from_str("whatsapp")

    def test_from_str_with_whitespace(self):
        assert MessengerPlatform.from_str("  telegram  ") == MessengerPlatform.TELEGRAM


# ── SendResult ────────────────────────────────────────────────────────────


class TestSendResult:
    def test_success_result(self):
        r = SendResult(success=True, message_id="123")
        assert r.success is True
        assert r.message_id == "123"
        assert r.error is None

    def test_failure_result(self):
        r = SendResult(success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"

    def test_frozen(self):
        r = SendResult(success=True)
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore


# ── InlineButton ──────────────────────────────────────────────────────────


class TestInlineButton:
    def test_creation(self):
        btn = InlineButton(text="OK", callback_data="confirm:1")
        assert btn.text == "OK"
        assert btn.callback_data == "confirm:1"

    def test_creation_with_url(self):
        btn = InlineButton(text="Open", url="https://example.com")
        assert btn.text == "Open"
        assert btn.url == "https://example.com"

    def test_creation_with_kind(self):
        btn = InlineButton(text="Open app", url="https://example.com/app", kind="web_app")
        assert btn.kind == "web_app"


# ── MessengerRegistry ────────────────────────────────────────────────────


class _FakeAdapter(MessengerProtocol):
    """Minimal adapter for testing."""

    def __init__(self, platform: MessengerPlatform):
        self.platform = platform
        self.sent: list = []

    async def configure(self, **kwargs: Any) -> None:
        pass

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        buttons=None,
        parse_mode=None,
        correlation_id=None,
    ) -> SendResult:
        self.sent.append((chat_id, text))
        return SendResult(success=True, message_id="fake_1")


class TestMessengerRegistry:
    def test_register_and_get(self):
        reg = MessengerRegistry()
        adapter = _FakeAdapter(MessengerPlatform.TELEGRAM)
        reg.register(adapter)
        assert reg.get(MessengerPlatform.TELEGRAM) is adapter

    def test_get_missing(self):
        reg = MessengerRegistry()
        assert reg.get(MessengerPlatform.MAX) is None

    def test_get_or_raise(self):
        reg = MessengerRegistry()
        with pytest.raises(RuntimeError, match="No messenger adapter"):
            reg.get_or_raise(MessengerPlatform.MAX)

    def test_contains(self):
        reg = MessengerRegistry()
        adapter = _FakeAdapter(MessengerPlatform.TELEGRAM)
        reg.register(adapter)
        assert MessengerPlatform.TELEGRAM in reg
        assert MessengerPlatform.MAX not in reg

    def test_platforms(self):
        reg = MessengerRegistry()
        reg.register(_FakeAdapter(MessengerPlatform.TELEGRAM))
        reg.register(_FakeAdapter(MessengerPlatform.MAX))
        assert set(reg.platforms) == {MessengerPlatform.TELEGRAM, MessengerPlatform.MAX}

    def test_overwrite(self):
        reg = MessengerRegistry()
        a1 = _FakeAdapter(MessengerPlatform.TELEGRAM)
        a2 = _FakeAdapter(MessengerPlatform.TELEGRAM)
        reg.register(a1)
        reg.register(a2)
        assert reg.get(MessengerPlatform.TELEGRAM) is a2


# ── resolve_adapter_for_candidate ─────────────────────────────────────────


class TestResolveAdapterForCandidate:
    def setup_method(self):
        # Reset global registry for each test
        import backend.core.messenger.registry as reg_mod
        self._old = reg_mod._registry
        reg_mod._registry = MessengerRegistry()
        self.tg = _FakeAdapter(MessengerPlatform.TELEGRAM)
        self.mx = _FakeAdapter(MessengerPlatform.MAX)

    def teardown_method(self):
        import backend.core.messenger.registry as reg_mod
        reg_mod._registry = self._old

    def _reg(self):
        import backend.core.messenger.registry as reg_mod
        return reg_mod._registry

    def test_explicit_telegram(self):
        self._reg().register(self.tg)
        adapter, chat = resolve_adapter_for_candidate(
            messenger_platform="telegram",
            telegram_user_id=12345,
        )
        assert adapter is self.tg
        assert chat == 12345

    def test_explicit_max(self):
        self._reg().register(self.mx)
        adapter, chat = resolve_adapter_for_candidate(
            messenger_platform="max",
            max_user_id="max_user_abc",
        )
        assert adapter is self.mx
        assert chat == "max_user_abc"

    def test_auto_prefer_max(self):
        self._reg().register(self.tg)
        self._reg().register(self.mx)
        adapter, chat = resolve_adapter_for_candidate(
            telegram_user_id=12345,
            max_user_id="max_user_abc",
        )
        assert adapter is self.mx
        assert chat == "max_user_abc"

    def test_auto_fallback_telegram(self):
        self._reg().register(self.tg)
        adapter, chat = resolve_adapter_for_candidate(
            telegram_user_id=12345,
        )
        assert adapter is self.tg
        assert chat == 12345

    def test_no_ids_raises(self):
        self._reg().register(self.tg)
        with pytest.raises(ValueError, match="Cannot resolve messenger adapter"):
            resolve_adapter_for_candidate()

    def test_max_id_but_no_max_adapter_falls_to_tg(self):
        self._reg().register(self.tg)
        adapter, chat = resolve_adapter_for_candidate(
            telegram_user_id=12345,
            max_user_id="max_user_abc",
        )
        assert adapter is self.tg
        assert chat == 12345


# ── TelegramAdapter ──────────────────────────────────────────────────────


class TestTelegramAdapter:
    @pytest.mark.asyncio
    async def test_send_success(self):
        from backend.core.messenger.telegram_adapter import TelegramAdapter

        mock_bot = AsyncMock()
        mock_result = MagicMock()
        mock_result.message_id = 42
        mock_bot.send_message.return_value = mock_result

        adapter = TelegramAdapter()
        await adapter.configure(bot=mock_bot)

        result = await adapter.send_message(12345, "Hello!")
        assert result.success is True
        assert result.message_id == "42"
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_with_buttons(self):
        from backend.core.messenger.telegram_adapter import TelegramAdapter

        mock_bot = AsyncMock()
        mock_result = MagicMock()
        mock_result.message_id = 43
        mock_bot.send_message.return_value = mock_result

        adapter = TelegramAdapter()
        await adapter.configure(bot=mock_bot)

        buttons = [[InlineButton(text="OK", callback_data="ok:1")]]
        result = await adapter.send_message(12345, "Choose:", buttons=buttons)
        assert result.success is True

        call_kwargs = mock_bot.send_message.call_args
        assert call_kwargs[1]["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_send_with_web_app_button(self):
        from backend.core.messenger.telegram_adapter import TelegramAdapter

        mock_bot = AsyncMock()
        mock_result = MagicMock()
        mock_result.message_id = 45
        mock_bot.send_message.return_value = mock_result

        adapter = TelegramAdapter()
        await adapter.configure(bot=mock_bot)

        buttons = [[InlineButton(text="Open portal", url="https://example.com/portal", kind="web_app")]]
        result = await adapter.send_message(12345, "Choose:", buttons=buttons)
        assert result.success is True

        call_kwargs = mock_bot.send_message.call_args
        reply_markup = call_kwargs[1]["reply_markup"]
        assert reply_markup is not None
        assert reply_markup.inline_keyboard[0][0].web_app is not None
        assert reply_markup.inline_keyboard[0][0].web_app.url == "https://example.com/portal"

    @pytest.mark.asyncio
    async def test_send_blocked_no_retry(self):
        from backend.core.messenger.telegram_adapter import TelegramAdapter

        mock_bot = AsyncMock()

        class ForbiddenError(Exception):
            pass

        ForbiddenError.__name__ = "Forbidden"

        mock_bot.send_message.side_effect = ForbiddenError("bot blocked")

        adapter = TelegramAdapter()
        adapter._max_retries = 1
        await adapter.configure(bot=mock_bot)

        result = await adapter.send_message(12345, "Hi")
        assert result.success is False
        assert "Forbidden" in result.error
        # Should NOT retry for forbidden
        assert mock_bot.send_message.call_count == 1

    @pytest.mark.asyncio
    async def test_send_retries_on_server_error(self):
        from backend.core.messenger.telegram_adapter import TelegramAdapter

        mock_bot = AsyncMock()
        mock_result = MagicMock()
        mock_result.message_id = 44
        mock_bot.send_message.side_effect = [
            RuntimeError("server error"),
            mock_result,
        ]

        adapter = TelegramAdapter()
        adapter._max_retries = 3
        adapter._base_delay = 0.01  # fast for tests
        await adapter.configure(bot=mock_bot)

        result = await adapter.send_message(12345, "Retry test")
        assert result.success is True
        assert mock_bot.send_message.call_count == 2


# ── MaxAdapter ────────────────────────────────────────────────────────────


class TestMaxAdapter:
    @pytest.mark.asyncio
    async def test_send_success(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "message": {"mid": "msg_1"}}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        result = await adapter.send_message("user_123", "Hello from Max!")
        assert result.success is True
        assert result.message_id == "msg_1"
        mock_client.request.assert_awaited_once_with(
            "POST",
            "/messages",
            params={"user_id": "user_123"},
            json={"text": "Hello from Max!"},
        )

    @pytest.mark.asyncio
    async def test_send_2xx_without_message_id_is_success(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"description": "accepted"}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        result = await adapter.send_message("user_123", "Hello from Max!")
        assert result.success is True
        assert result.message_id is None
        mock_client.request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_with_buttons(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "message": {"mid": "msg_2"}}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        buttons = [[InlineButton(text="OK", callback_data="ok:1")]]
        result = await adapter.send_message("user_123", "Choose:", buttons=buttons)
        assert result.success is True

        call_args = mock_client.request.call_args
        payload = call_args[1]["json"]
        params = call_args[1]["params"]
        assert params == {"user_id": "user_123"}
        assert "attachments" in payload
        assert payload["attachments"][0]["type"] == "inline_keyboard"

    @pytest.mark.asyncio
    async def test_send_with_link_button(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"mid": "msg_link"}}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        buttons = [[InlineButton(text="Open portal", url="https://example.com/portal")]]
        result = await adapter.send_message("user_123", "Open:", buttons=buttons, parse_mode="HTML")
        assert result.success is True

        payload = mock_client.request.call_args[1]["json"]
        assert payload["format"] == "html"
        button = payload["attachments"][0]["payload"]["buttons"][0][0]
        assert button["type"] == "link"
        assert button["url"] == "https://example.com/portal"

    @pytest.mark.asyncio
    async def test_send_with_open_app_button(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"mid": "msg_app"}}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        buttons = [[InlineButton(text="Open portal", url="https://example.com/portal", kind="web_app")]]
        result = await adapter.send_message("user_123", "Open:", buttons=buttons)
        assert result.success is True

        payload = mock_client.request.call_args[1]["json"]
        button = payload["attachments"][0]["payload"]["buttons"][0][0]
        assert button["type"] == "open_app"
        assert button["web_app"] == "https://example.com/portal"

    @pytest.mark.asyncio
    async def test_send_api_error_400(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "bad_request", "description": "Invalid chat_id"}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        result = await adapter.send_message("bad_user", "Test")
        assert result.success is False
        assert "400" in result.error

    @pytest.mark.asyncio
    async def test_send_api_error_with_string_message_does_not_raise(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"message": "recipient not found"}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        result = await adapter.send_message("missing_user", "Test")
        assert result.success is False
        assert "404" in (result.error or "")

    @pytest.mark.asyncio
    async def test_send_retries_on_500(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"
        adapter._max_retries = 2
        adapter._base_delay = 0.01

        mock_client = AsyncMock()
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.json.return_value = {"error": "internal_error"}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"success": True, "message": {"mid": "msg_3"}}

        mock_client.request.side_effect = [fail_resp, ok_resp]
        adapter._client = mock_client

        result = await adapter.send_message("user_123", "Retry test")
        assert result.success is True
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_bot_profile_success(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"user": {"id": 42, "name": "Attila MAX Bot"}}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        profile = await adapter.get_bot_profile()
        assert profile["user"]["id"] == 42
        mock_client.request.assert_awaited_once_with(
            "GET",
            "/me",
            params=None,
            json=None,
        )

    @pytest.mark.asyncio
    async def test_get_bot_profile_invalid_token_raises(self):
        from backend.core.messenger.max_adapter import MaxAdapter, MaxAdapterAuthError

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": "unauthorized"}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        with pytest.raises(MaxAdapterAuthError, match="token rejected"):
            await adapter.get_bot_profile()

    @pytest.mark.asyncio
    async def test_answer_callback_sends_notification(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        adapter._token = "test_token"

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True}
        mock_client.request.return_value = mock_resp
        adapter._client = mock_client

        result = await adapter.answer_callback("cb_1", notification="Принято")
        assert result.success is True
        mock_client.request.assert_awaited_once_with(
            "POST",
            "/answers",
            params={"callback_id": "cb_1"},
            json={"notification": "Принято"},
        )

    @pytest.mark.asyncio
    async def test_not_configured_raises(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        with pytest.raises(RuntimeError, match="not configured"):
            await adapter.send_message("user", "text")

    @pytest.mark.asyncio
    async def test_close(self):
        from backend.core.messenger.max_adapter import MaxAdapter

        adapter = MaxAdapter()
        mock_client = AsyncMock()
        adapter._client = mock_client
        await adapter.close()
        mock_client.aclose.assert_called_once()
        assert adapter._client is None


# ── Bootstrap ─────────────────────────────────────────────────────────────


class TestBootstrap:
    @pytest.mark.asyncio
    async def test_bootstrap_telegram_only(self):
        import backend.core.messenger.registry as reg_mod
        old = reg_mod._registry
        reg_mod._registry = MessengerRegistry()
        try:
            from backend.core.messenger.bootstrap import bootstrap_messenger_adapters

            mock_bot = MagicMock()
            await bootstrap_messenger_adapters(bot=mock_bot)

            reg = reg_mod._registry
            assert MessengerPlatform.TELEGRAM in reg
            assert MessengerPlatform.MAX not in reg
        finally:
            reg_mod._registry = old

    @pytest.mark.asyncio
    async def test_bootstrap_with_max(self):
        import backend.core.messenger.registry as reg_mod
        old = reg_mod._registry
        reg_mod._registry = MessengerRegistry()
        try:
            from backend.core.messenger.bootstrap import bootstrap_messenger_adapters

            mock_bot = MagicMock()
            # Mock httpx import inside MaxAdapter.configure
            with patch("backend.core.messenger.max_adapter.httpx", create=True) as mock_httpx:
                mock_httpx.AsyncClient.return_value = AsyncMock()
                mock_httpx.Timeout.return_value = MagicMock()
                await bootstrap_messenger_adapters(
                    bot=mock_bot,
                    max_bot_enabled=True,
                    max_bot_token="test_max_token",
                )

            reg = reg_mod._registry
            assert MessengerPlatform.TELEGRAM in reg
            assert MessengerPlatform.MAX in reg
        finally:
            reg_mod._registry = old

    @pytest.mark.asyncio
    async def test_bootstrap_max_no_token_skipped(self):
        import backend.core.messenger.registry as reg_mod
        old = reg_mod._registry
        reg_mod._registry = MessengerRegistry()
        try:
            from backend.core.messenger.bootstrap import bootstrap_messenger_adapters

            mock_bot = MagicMock()
            await bootstrap_messenger_adapters(
                bot=mock_bot,
                max_bot_enabled=True,
                max_bot_token="",
            )

            reg = reg_mod._registry
            assert MessengerPlatform.TELEGRAM in reg
            assert MessengerPlatform.MAX not in reg
        finally:
            reg_mod._registry = old
