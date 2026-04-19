from __future__ import annotations

from types import SimpleNamespace

import pytest
from backend.apps.admin_ui.services.messenger_health import get_messenger_health
from backend.core.messenger.channel_state import (
    get_messenger_channel_health,
    get_messenger_channel_runtime,
)
from backend.core.messenger.max_adapter import MaxAdapter
from backend.core.messenger.protocol import (
    InlineButton,
    MessengerPlatform,
    MessengerProtocol,
)
from backend.core.messenger.registry import (
    MessengerRegistry,
    get_registry,
    resolve_adapter_for_candidate,
)


class _FakeAdapter(MessengerProtocol):
    def __init__(self, platform: MessengerPlatform):
        self.platform = platform

    async def configure(self, **kwargs):
        return None

    async def send_message(
        self,
        chat_id,
        text,
        *,
        buttons=None,
        parse_mode=None,
        correlation_id=None,
    ):
        del chat_id, text, buttons, parse_mode, correlation_id
        return SimpleNamespace(success=True, message_id="fake", error=None)


@pytest.fixture(autouse=True)
def _reset_registry():
    import backend.core.messenger.registry as registry_module

    previous = registry_module._registry
    registry_module._registry = MessengerRegistry()
    yield
    registry_module._registry = previous


def test_messenger_platform_supports_max_aliases():
    assert MessengerPlatform.from_str("max") == MessengerPlatform.MAX
    assert MessengerPlatform.from_str("vk_max") == MessengerPlatform.MAX
    assert MessengerPlatform.from_str("icq") == MessengerPlatform.MAX


def test_registry_resolves_explicit_max_identity():
    import backend.core.messenger.registry as registry_module

    adapter = _FakeAdapter(MessengerPlatform.MAX)
    registry_module._registry.register(adapter)

    resolved_adapter, chat_id = resolve_adapter_for_candidate(
        messenger_platform="max",
        max_user_id="max-user-42",
    )

    assert resolved_adapter is adapter
    assert chat_id == "max-user-42"


def test_registry_falls_back_to_telegram_when_max_not_registered():
    import backend.core.messenger.registry as registry_module

    adapter = _FakeAdapter(MessengerPlatform.TELEGRAM)
    registry_module._registry.register(adapter)

    resolved_adapter, chat_id = resolve_adapter_for_candidate(
        messenger_platform="max",
        max_user_id="max-user-42",
        telegram_user_id=4242,
    )

    assert resolved_adapter is adapter
    assert chat_id == 4242


@pytest.mark.asyncio
async def test_max_adapter_returns_disabled_when_not_configured():
    adapter = MaxAdapter()

    result = await adapter.send_message("max-user-1", "hello")

    assert result.success is False
    assert result.error == "bot_not_configured"


@pytest.mark.asyncio
async def test_max_adapter_sends_message_when_configured():
    adapter = MaxAdapter()
    client = SimpleNamespace()

    async def request(method, path, *, params=None, json=None):
        assert method == "POST"
        assert path == "/messages"
        assert params == {"user_id": "max-user-1"}
        assert json["text"] == "hello"
        assert json["attachments"][0]["payload"]["buttons"][0][0]["type"] == "open_app"
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"message": {"mid": "msg-1"}},
        )

    async def aclose():
        return None

    client.request = request
    client.aclose = aclose

    await adapter.configure(token="token-1", client=client)
    result = await adapter.send_message(
        "max-user-1",
        "hello",
        buttons=[
            [InlineButton(text="Open", url="https://example.com/app", kind="web_app")]
        ],
    )

    assert adapter.is_configured is True
    assert result.success is True
    assert result.message_id == "msg-1"


@pytest.mark.asyncio
async def test_channel_health_defaults_include_max():
    health = await get_messenger_channel_health()

    assert "telegram" in health
    assert "max" in health
    assert health["max"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_runtime_health_reports_max_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("MAX_ADAPTER_ENABLED", raising=False)
    monkeypatch.delenv("MAX_BOT_TOKEN", raising=False)

    payload = await get_messenger_health(channels=("max",))

    assert payload["channels"]["max"]["status"] == "disabled"
    assert payload["channels"]["max"]["configured"] is False
    assert payload["channels"]["max"]["registered"] is False


@pytest.mark.asyncio
async def test_runtime_health_reports_max_not_registered_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "token-1")

    payload = await get_messenger_health(channels=("max",))

    assert payload["channels"]["max"]["status"] == "not_registered"
    assert payload["channels"]["max"]["configured"] is True
    assert payload["channels"]["max"]["registered"] is False


@pytest.mark.asyncio
async def test_runtime_health_reports_max_configured_when_registered(
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.core.messenger.registry as registry_module

    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "token-1")
    adapter = MaxAdapter()
    await adapter.configure(
        token="token-1", client=SimpleNamespace(request=None, aclose=None)
    )
    registry_module._registry.register(adapter)

    runtime = get_messenger_channel_runtime("max")
    payload = await get_messenger_health(channels=("max",))

    assert runtime["status"] == "configured"
    assert payload["channels"]["max"]["status"] == "configured"
    assert payload["channels"]["max"]["registered"] is True
    assert payload["channels"]["max"]["adapter"] == "MaxAdapter"


@pytest.mark.asyncio
async def test_bootstrap_max_adapter_shell_registers_adapter():
    from backend.core.messenger.max_adapter import bootstrap_max_adapter_shell

    registry = get_registry()

    adapter = await bootstrap_max_adapter_shell(
        config=SimpleNamespace(
            bot_token="token-1",
            public_bot_name="rs_max_bot",
            miniapp_url="https://example.test/max",
        )
    )

    assert adapter.is_configured is True
    assert registry.get(MessengerPlatform.MAX) is adapter
    await adapter.close()
