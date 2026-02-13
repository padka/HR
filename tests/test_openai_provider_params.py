from __future__ import annotations

from backend.core.ai.providers.openai import _supports_temperature, _token_param_name_for_model


def test_openai_provider_token_param_name_for_model_gpt5():
    assert _token_param_name_for_model("gpt-5-mini") == "max_completion_tokens"
    assert _token_param_name_for_model("gpt-5-mini-2025-08-07") == "max_completion_tokens"
    assert _token_param_name_for_model("GPT-5") == "max_completion_tokens"


def test_openai_provider_token_param_name_for_model_legacy():
    assert _token_param_name_for_model("gpt-4o-mini") == "max_tokens"
    assert _token_param_name_for_model("gpt-4.1-mini") == "max_tokens"
    assert _token_param_name_for_model("") == "max_tokens"


def test_openai_provider_supports_temperature_by_model_family():
    assert _supports_temperature("gpt-4o-mini") is True
    assert _supports_temperature("gpt-5-mini") is False
