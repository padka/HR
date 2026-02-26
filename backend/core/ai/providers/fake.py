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
            "candidate_coach_v1",
            "candidate_coach_drafts_v1",
            "candidate_next_actions_v1",
            "chat_reply_drafts_v1",
            "dashboard_insight_v1",
            "city_candidate_recommendations_v1",
            "agent_chat_reply_v1",
            "interview_script_v1",
        ):
            if marker in system_prompt or marker in user_prompt:
                kind = marker
                break

        payload: dict[str, Any]
        if "interview_script_v1" in kind:
            payload = {
                "risk_flags": [
                    {
                        "code": "LOGISTICS_UNCLEAR",
                        "severity": "medium",
                        "reason": "Кандидату нужно заранее объяснить адрес и ориентиры.",
                        "question": "Насколько вам удобно добираться в указанный район в рабочие часы?",
                        "recommended_phrase": "Сейчас пришлю адрес, ориентир и точный временной слот, чтобы вы могли спланировать дорогу.",
                    }
                ],
                "highlights": [
                    "Кандидат в активном процессе, важно быстро закрыть логистику.",
                    "Сфокусироваться на опыте общения с клиентами.",
                ],
                "checks": [
                    "Проверить доступность кандидата на ближайшие 3 дня.",
                    "Подтвердить готовность к полевому формату работы.",
                ],
                "objections": [
                    {
                        "topic": "Доход",
                        "candidate_says": "Мне важно понимать реальный доход на старте.",
                        "recruiter_answer": "Обсудим прозрачную вилку на старте и от чего зависит рост дохода по этапам.",
                    }
                ],
                "script_blocks": [
                    {
                        "id": "intro",
                        "title": "Разогрев и контакт",
                        "goal": "Быстро установить контакт и рамку звонка.",
                        "recruiter_text": "Здравствуйте! Я из RecruitSmart. Уделите 5-7 минут: коротко пройдём по вакансии и договоримся о следующем шаге.",
                        "candidate_questions": [
                            "Удобно ли сейчас говорить?",
                            "Подскажите, рассматриваете работу в ближайшее время?",
                        ],
                        "if_answers": [
                            {"pattern": "сейчас неудобно", "hint": "Сразу предложить 2 альтернативных слота."}
                        ],
                    },
                    {
                        "id": "experience",
                        "title": "Опыт и мотивация",
                        "goal": "Понять релевантный опыт и драйвер кандидата.",
                        "recruiter_text": "Расскажите коротко о вашем последнем опыте: где были сильнее всего в коммуникации с клиентами?",
                        "candidate_questions": [
                            "Какой формат задач вам ближе?",
                            "Что для вас критично при выборе места работы?",
                        ],
                        "if_answers": [
                            {"pattern": "нет опыта", "hint": "Сместить акцент на обучение и soft-skills."}
                        ],
                    },
                    {
                        "id": "logistics",
                        "title": "Логистика и следующий шаг",
                        "goal": "Снять риски по доезду и зафиксировать действие.",
                        "recruiter_text": "Подтвердим адрес, ориентир и удобный слот. После этого я зафиксирую вас в CRM и отправлю детали.",
                        "candidate_questions": [
                            "Какой слот удобнее: сегодня вечером или завтра утром?",
                            "Нужны ли дополнительные ориентиры по адресу?",
                        ],
                        "if_answers": [
                            {"pattern": "далеко ехать", "hint": "Уточнить маршрут и предложить другой слот."}
                        ],
                    },
                ],
                "cta_templates": [
                    {"type": "slot_confirm", "text": "Подтверждаю ваш слот на {дата/время}, адрес и ориентир сейчас отправлю сообщением."},
                    {"type": "reschedule", "text": "Если это время неудобно, предложу 2 альтернативы без потери этапа."},
                ],
            }
        elif "candidate_coach_drafts_v1" in kind or "chat_reply_drafts_v1" in kind:
            payload = {
                "drafts": [
                    {"text": "Здравствуйте! Подскажите, пожалуйста, когда вам удобно?", "reason": "neutral"},
                    {"text": "Добрый день. Уточните, пожалуйста, удобное время, и я предложу слот.", "reason": "short"},
                ],
                "used_context": {"safe_text_used": False},
            }
        elif "candidate_coach_v1" in kind:
            payload = {
                "relevance_score": 78,
                "relevance_level": "high",
                "rationale": "Кандидат показывает релевантный опыт и адекватную мотивацию для текущего этапа.",
                "criteria_used": True,
                "strengths": [
                    {
                        "key": "customer_experience",
                        "label": "Опыт клиентской коммуникации",
                        "evidence": "Из ответов теста: работа в клиентских ролях более 3 месяцев.",
                    }
                ],
                "risks": [
                    {
                        "key": "timing_alignment",
                        "severity": "medium",
                        "label": "Риск затягивания по времени слота",
                        "explanation": "Нужно быстро закрепить конкретный слот, чтобы не потерять контакт.",
                    }
                ],
                "interview_questions": [
                    "Какой формат выездной работы для вас комфортен?",
                    "Когда готовы выйти на ознакомительный день?",
                    "Какие задачи в продажах вам даются лучше всего?",
                    "Какие условия важны для принятия оффера?",
                ],
                "next_best_action": "Предложить 2-3 конкретных слота и зафиксировать подтверждение кандидата.",
                "message_drafts": [
                    {
                        "text": "Добрый день! Предлагаю выбрать удобное время: сегодня 16:00 или завтра 10:30. Какой вариант вам подходит?",
                        "reason": "Сужает выбор и ускоряет подтверждение слота.",
                    },
                    {
                        "text": "Подтверждаю встречу и отправляю детали. Если время изменится — напишите, согласуем перенос без потери этапа.",
                        "reason": "Снижает риск срыва и показывает управляемость процесса.",
                    },
                ],
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
        elif "agent_chat_reply_v1" in kind:
            payload = {
                "answer": "По регламенту используйте только объективные критерии и фиксируйте подтверждения в CRM. Если критерии города не заданы, уточните их у ответственного лица и зафиксируйте в системе.",
                "confidence": "medium",
                "kb_sources": [],
                "follow_ups": ["Уточните город/вакансию и какие критерии сейчас установлены офисом."],
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
