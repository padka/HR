"""AI Copilot subsystem (LLM integration).

The AI layer is strictly opt-in via AI_ENABLED and must never send raw PII
outside the system. All prompts and contexts are designed to be anonymized.
"""

from .service import AIService, get_ai_service

__all__ = ["AIService", "get_ai_service"]

