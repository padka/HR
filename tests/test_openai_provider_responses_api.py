import json

import aiohttp
import pytest
from backend.core.ai.providers.openai import OpenAIProvider


class DummySettings:
    openai_api_key = "sk-test"
    openai_base_url = "https://api.openai.com/v1"


class _DummyResponse:
    def __init__(self, *, status: int, body: dict) -> None:
        self.status = status
        self._body = body

    async def text(self) -> str:
        return json.dumps(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _install_dummy_client_session(monkeypatch, *, capture: dict, response_body: dict) -> None:
    class _DummySession:
        def __init__(self, *, timeout: aiohttp.ClientTimeout) -> None:
            self._timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, url, *, headers=None, json=None):
            capture["url"] = url
            capture["headers"] = headers
            capture["payload"] = json
            return _DummyResponse(status=200, body=response_body)

    monkeypatch.setattr(aiohttp, "ClientSession", lambda *, timeout: _DummySession(timeout=timeout))


@pytest.mark.asyncio
async def test_gpt5_uses_responses_api_and_parses_output(monkeypatch):
    capture: dict = {}
    _install_dummy_client_session(
        monkeypatch,
        capture=capture,
        response_body={
            "id": "resp_123",
            "object": "response",
            "output": [
                {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "{\"ok\": true}"}],
                }
            ],
            "usage": {"input_tokens": 11, "output_tokens": 7},
        },
    )

    provider = OpenAIProvider(DummySettings())
    payload, usage = await provider.generate_json(
        model="gpt-5-mini",
        system_prompt="Return JSON only.",
        user_prompt="{}",
        timeout_seconds=10,
        max_tokens=123,
    )

    assert capture["url"].endswith("/responses")
    assert capture["payload"]["model"] == "gpt-5-mini"
    assert capture["payload"]["max_output_tokens"] == 123
    assert capture["payload"]["text"]["format"]["type"] == "json_object"
    assert capture["payload"]["reasoning"]["effort"] == "none"
    assert str(capture["payload"]["input"]).startswith("JSON\n")
    assert payload == {"ok": True}
    assert usage.tokens_in == 11
    assert usage.tokens_out == 7


@pytest.mark.asyncio
async def test_gpt4o_uses_chat_completions(monkeypatch):
    capture: dict = {}
    _install_dummy_client_session(
        monkeypatch,
        capture=capture,
        response_body={
            "id": "chatcmpl_123",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "{\"ok\": true}"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5},
        },
    )

    provider = OpenAIProvider(DummySettings())
    payload, usage = await provider.generate_json(
        model="gpt-4o-mini",
        system_prompt="Return JSON only.",
        user_prompt="{}",
        timeout_seconds=10,
        max_tokens=321,
    )

    assert capture["url"].endswith("/chat/completions")
    assert capture["payload"]["model"] == "gpt-4o-mini"
    assert capture["payload"]["max_tokens"] == 321
    assert capture["payload"]["temperature"] == 0.2
    assert capture["payload"]["response_format"]["type"] == "json_object"
    assert payload == {"ok": True}
    assert usage.tokens_in == 3
    assert usage.tokens_out == 5
