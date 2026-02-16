"""AI provider implementations (pluggable LLM backends).

- ``OpenAIProvider`` — production provider using OpenAI Chat Completions / Responses API.
- ``FakeProvider`` — deterministic stub for tests (returns hardcoded JSON).
- ``AIProvider`` — Protocol interface that both implement.
"""

from .base import AIProvider, AIProviderError, Usage
from .fake import FakeProvider
from .openai import OpenAIProvider

__all__ = ["AIProvider", "AIProviderError", "FakeProvider", "OpenAIProvider", "Usage"]

