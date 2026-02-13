from __future__ import annotations

import json
from typing import Any

from .base import Usage


class FakeProvider:
    """Deterministic provider for tests/e2e.

    It ignores prompts and returns a stable JSON structure.
    """

    name = "fake"

    async def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int,
        max_tokens: int,
    ) -> tuple[dict, Usage]:
        # Derive "kind" if present in prompt for nicer assertions
        kind = "unknown"
        for marker in ("candidate_summary_v1", "candidate_next_actions_v1", "chat_reply_drafts_v1", "dashboard_insight_v1"):
            if marker in system_prompt or marker in user_prompt:
                kind = marker
                break

        payload: dict[str, Any]
        if "chat_reply_drafts_v1" in kind:
            payload = {
                "drafts": [
                    {"text": "Здравствуйте! Подскажите, пожалуйста, когда вам удобно?", "reason": "neutral"},
                    {"text": "Добрый день. Уточните, пожалуйста, удобное время, и я предложу слот.", "reason": "short"},
                ],
                "used_context": {"safe_text_used": False},
            }
        elif "dashboard_insight_v1" in kind:
            payload = {
                "tldr": "Ключевые метрики стабильны. Узкое место: подтверждение слота.",
                "anomalies": [],
                "recommendations": ["Увеличить число слотов в пиковые часы."],
            }
        else:
            payload = {
                "tldr": "Кандидат в процессе. Следующий шаг: назначить/подтвердить время.",
                "risks": [
                    {"key": "no_telegram", "severity": "medium", "label": "Нет Telegram-связки", "explanation": "Нельзя писать кандидату из системы."}
                ],
                "next_actions": [
                    {"key": "schedule", "label": "Предложить время", "rationale": "Ускорит прохождение до слота."},
                    {"key": "message", "label": "Написать кандидату", "rationale": "Снизит риск no-show."},
                ],
            }

        # Ensure JSON-serializable
        json.loads(json.dumps(payload))
        return payload, Usage(tokens_in=10, tokens_out=20)
