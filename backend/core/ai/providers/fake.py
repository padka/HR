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
        for marker in (
            "candidate_summary_v1",
            "candidate_next_actions_v1",
            "chat_reply_drafts_v1",
            "dashboard_insight_v1",
            "city_candidate_recommendations_v1",
        ):
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
        elif "city_candidate_recommendations_v1" in kind:
            candidate_ids: list[int] = []
            try:
                start = user_prompt.find("{")
                if start != -1:
                    ctx = json.loads(user_prompt[start:])
                    items = ((ctx or {}).get("candidates") or {}).get("items") or []
                    for item in items:
                        cid = item.get("id")
                        if isinstance(cid, int):
                            candidate_ids.append(cid)
                        elif isinstance(cid, str) and cid.isdigit():
                            candidate_ids.append(int(cid))
            except Exception:
                candidate_ids = []

            c1 = candidate_ids[0] if len(candidate_ids) > 0 else 1
            c2 = candidate_ids[1] if len(candidate_ids) > 1 else (candidate_ids[0] if candidate_ids else 2)
            payload = {
                "criteria_used": True,
                "recommended": [
                    {
                        "candidate_id": c1,
                        "fit_score": 82,
                        "fit_level": "high",
                        "reason": "Сильные результаты тестов и соответствие критериям города.",
                        "suggested_next_step": "Назначить/подтвердить время собеседования.",
                    },
                    {
                        "candidate_id": c2,
                        "fit_score": 63,
                        "fit_level": "medium",
                        "reason": "В целом подходит, но есть риск застревания на этапе слота.",
                        "suggested_next_step": "Написать кандидату и предложить 2-3 слота.",
                    },
                ],
                "notes": "Сфокусируйтесь на кандидатах без подтвержденного слота.",
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
                "fit": {
                    "score": 70,
                    "level": "medium",
                    "rationale": "По тестам и текущему статусу кандидат выглядит перспективно; критерии города учтены частично.",
                    "criteria_used": True,
                },
                "strengths": [
                    {"key": "tests", "label": "Стабильные результаты тестов", "evidence": "Высокая доля правильных ответов и нормальное время прохождения."}
                ],
                "weaknesses": [
                    {"key": "no_tg", "label": "Нет подтвержденной связи в Telegram", "evidence": "Меньше каналов для быстрой коммуникации и напоминаний."}
                ],
                "test_insights": "По тестам видно, что кандидат хорошо справляется с базовыми вопросами. Рекомендуется уточнить мотивацию и доступность.",
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
