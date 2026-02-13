from __future__ import annotations

import json
import logging
import re
from typing import Any

import aiohttp

from backend.core.settings import Settings

from .base import AIProviderError, Usage

logger = logging.getLogger(__name__)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        match = _JSON_RE.search(text or "")
        if not match:
            raise
        return json.loads(match.group(0))


def _should_use_responses_api(model: str) -> bool:
    """
    Prefer the Responses API for GPT-5 family.

    In practice, GPT-5 models can return empty `message.content` on Chat Completions
    for some accounts/providers. Responses API is the recommended, current endpoint.
    """

    m = (model or "").strip().lower()
    return m.startswith("gpt-5")


def _token_param_name_for_model(model: str) -> str:
    """
    OpenAI has multiple token limit parameters depending on the model generation.

    - Older chat-completions models: max_tokens
    - Newer GPT-5 family: max_completion_tokens
    """

    m = (model or "").strip().lower()
    if m.startswith("gpt-5"):
        return "max_completion_tokens"
    return "max_tokens"


def _supports_temperature(model: str) -> bool:
    # GPT-5 chat-completions currently rejects custom temperature values.
    m = (model or "").strip().lower()
    if m.startswith("gpt-5"):
        return False
    return True


def _extract_text_from_responses(data: dict[str, Any]) -> str:
    # Some SDKs provide a convenience `output_text`, but raw HTTP responses may not.
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    parts: list[str] = []
    output = data.get("output") or []
    if not isinstance(output, list):
        return ""

    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        if item.get("role") != "assistant":
            continue
        content = item.get("content") or []
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") != "output_text":
                continue
            text = c.get("text")
            if isinstance(text, str) and text:
                parts.append(text)

    return "\n".join(parts)


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openai_api_key
        self._base_url = settings.openai_base_url.rstrip("/")

    async def _request(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int,
        max_tokens: int,
        with_response_format: bool,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise AIProviderError("OPENAI_API_KEY is missing")

        if _should_use_responses_api(model):
            # Responses API: https://api.openai.com/v1/responses
            url = f"{self._base_url}/responses"
            payload = {
                "model": model,
                "instructions": system_prompt,
                "input": user_prompt,
                "max_output_tokens": int(max_tokens),
            }
            if with_response_format:
                payload["text"] = {"format": {"type": "json_object"}}
        else:
            # Chat Completions API: https://api.openai.com/v1/chat/completions
            url = f"{self._base_url}/chat/completions"
            token_param = _token_param_name_for_model(model)
            payload = {
                "model": model,
                token_param: int(max_tokens),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if _supports_temperature(model):
                payload["temperature"] = 0.2
            if with_response_format:
                payload["response_format"] = {"type": "json_object"}

        timeout = aiohttp.ClientTimeout(total=float(timeout_seconds))
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                raw = await resp.text()
                if resp.status >= 400:
                    raise AIProviderError(f"OpenAI HTTP {resp.status}: {raw[:4000]}")
                try:
                    return json.loads(raw)
                except Exception as exc:
                    raise AIProviderError(f"Invalid JSON from OpenAI: {exc}") from exc

    async def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int,
        max_tokens: int,
    ) -> tuple[dict, Usage]:
        # Try strict JSON mode first; fall back for OpenAI-compatible providers.
        last_error: Exception | None = None
        for with_format in (True, False):
            try:
                data = await self._request(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    timeout_seconds=timeout_seconds,
                    max_tokens=max_tokens,
                    with_response_format=with_format,
                )
                if isinstance(data.get("choices"), list):
                    # Chat Completions
                    content = (
                        (((data.get("choices") or [{}])[0] or {}).get("message") or {}).get("content")
                        or ""
                    )
                    usage_raw = data.get("usage") or {}
                    usage = Usage(
                        tokens_in=int(usage_raw.get("prompt_tokens") or 0),
                        tokens_out=int(usage_raw.get("completion_tokens") or 0),
                    )
                else:
                    # Responses API
                    content = _extract_text_from_responses(data) or ""
                    usage_raw = data.get("usage") or {}
                    usage = Usage(
                        tokens_in=int(usage_raw.get("input_tokens") or 0),
                        tokens_out=int(usage_raw.get("output_tokens") or 0),
                    )

                payload = _extract_json(str(content))
                return payload, usage
            except Exception as exc:
                last_error = exc
                continue
        logger.warning("openai.provider.failed", exc_info=True)
        raise AIProviderError(str(last_error) if last_error else "OpenAI provider failed")
