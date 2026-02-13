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


def _install_dummy_client_session_sequence(monkeypatch, *, capture: dict, response_bodies: list[dict]) -> None:
    class _DummySession:
        def __init__(self, *, timeout: aiohttp.ClientTimeout) -> None:
            self._timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, url, *, headers=None, json=None):
            capture.setdefault("calls", 0)
            capture["calls"] += 1
            capture.setdefault("payloads", []).append(json)
            idx = min(int(capture["calls"]) - 1, len(response_bodies) - 1)
            return _DummyResponse(status=200, body=response_bodies[idx])

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
    assert capture["payload"]["reasoning"]["effort"] == "minimal"
    assert str(capture["payload"]["input"]).startswith("JSON\n")
    assert payload == {"ok": True}
    assert usage.tokens_in == 11
    assert usage.tokens_out == 7


@pytest.mark.asyncio
async def test_gpt5_repairs_malformed_json_from_json_mode(monkeypatch):
    capture: dict = {}
    _install_dummy_client_session_sequence(
        monkeypatch,
        capture=capture,
        response_bodies=[
            {
                "id": "resp_bad",
                "object": "response",
                "output": [
                    {
                        "id": "msg_1",
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            # Unescaped newline inside the JSON string breaks json.loads.
                            {"type": "output_text", "text": "{\n  \"ok\": true,\n  \"x\": 1\n"}
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
            {
                "id": "resp_fixed",
                "object": "response",
                "output": [
                    {
                        "id": "msg_2",
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "{\"ok\": true, \"x\": 1}"}],
                    }
                ],
                "usage": {"input_tokens": 3, "output_tokens": 7},
            },
        ],
    )

    provider = OpenAIProvider(DummySettings())
    payload, usage = await provider.generate_json(
        model="gpt-5-mini",
        system_prompt="Return JSON only.",
        user_prompt="{}",
        timeout_seconds=10,
        max_tokens=123,
    )

    assert payload == {"ok": True, "x": 1}
    assert int(capture.get("calls") or 0) == 2
    assert usage.tokens_in == 13
    assert usage.tokens_out == 27


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
