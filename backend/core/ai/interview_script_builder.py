from __future__ import annotations

from typing import Any


def _shorten(value: str | None, limit: int = 160) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _first_name(fio: str | None) -> str:
    parts = [part for part in str(fio or "").strip().split() if part]
    return parts[0] if parts else "кандидат"


def _question_score(answer: dict[str, Any]) -> int:
    score = 0
    if not bool(answer.get("is_correct")):
        score += 3
    if bool(answer.get("overtime")):
        score += 1
    attempts_count = int(answer.get("attempts_count") or 0)
    if attempts_count > 1:
        score += 1
    user_answer = str(answer.get("user_answer") or "").strip()
    if user_answer and len(user_answer) < 20:
        score += 1
    return score


def _personalized_question_text(question_text: str, user_answer: str) -> str:
    question_lc = question_text.lower()
    answer_hint = _shorten(user_answer, 120)
    if "опыт" in question_lc or "кейс" in question_lc or "пример" in question_lc:
        return f"В тесте вы коротко описали опыт по теме «{question_text}». Расскажите на конкретном примере, как это было в реальной работе."
    if "мотив" in question_lc:
        return f"В тесте вы упомянули мотивацию: «{answer_hint}». Что для вас реально будет показателем удачного первого месяца на новой работе?"
    if "доход" in question_lc or "зарплат" in question_lc:
        return "Какой уровень дохода для вас реалистичен на старте и что должно произойти, чтобы вы считали предложение сильным?"
    if "формат" in question_lc or "выезд" in question_lc or "разъезд" in question_lc or "дня" in question_lc:
        return "Насколько вам действительно подходит выездной и полевой формат работы в течение дня? Опишите, что для вас в нём комфортно, а что нет."
    if "навык" in question_lc or "качеств" in question_lc:
        return f"Вы в тесте отметили: «{answer_hint}». Как это проявлялось в работе на практике?"
    return f"В тесте был вопрос «{question_text}». Расскажите подробнее, как вы бы действовали в похожей рабочей ситуации."


def _personalized_question_why(question_text: str) -> str:
    question_lc = question_text.lower()
    if "формат" in question_lc or "выезд" in question_lc or "разъезд" in question_lc:
        return "Проверяем, совпадает ли реальная готовность кандидата с форматом работы, который потребуется на позиции."
    if "доход" in question_lc or "зарплат" in question_lc:
        return "Снимаем риск по ожиданиям к доходу до следующего этапа и проверяем реалистичность ожиданий."
    return "Проверяем реальный опыт и глубину ответа в зоне, где тест дал слабый или неполный сигнал."


def _good_answer(question_text: str) -> str:
    question_lc = question_text.lower()
    if "формат" in question_lc or "выезд" in question_lc or "разъезд" in question_lc:
        return "Спокойно подтверждает формат, говорит о бытовой готовности и даёт конкретный пример похожего режима."
    if "доход" in question_lc or "зарплат" in question_lc:
        return "Называет реалистичный диапазон, объясняет ожидания и связывает их с объёмом работы, а не только с желанием."
    return "Даёт конкретику, приводит пример из опыта, описывает свои действия и делает вывод из ситуации."


def _red_flags(question_text: str) -> str:
    question_lc = question_text.lower()
    if "формат" in question_lc or "выезд" in question_lc or "разъезд" in question_lc:
        return "Уклоняется от прямого ответа, хочет только офисный формат или явно не готов к активному ритму дня."
    return "Отвечает общими словами, уходит от примера, обвиняет обстоятельства или не может объяснить свою роль в ситуации."


def _build_focus_areas(
    *,
    weak_answers: list[dict[str, Any]],
    scorecard: dict[str, Any] | None,
    script: dict[str, Any],
) -> list[str]:
    focus_areas: list[str] = []
    for answer in weak_answers[:3]:
        question_text = str(answer.get("question_text") or "").strip()
        user_answer = _shorten(str(answer.get("user_answer") or "").strip(), 80)
        if question_text:
            if user_answer:
                focus_areas.append(f"Вернуться к теме «{question_text}»: ответ был слишком общий ({user_answer}).")
            else:
                focus_areas.append(f"Вернуться к теме «{question_text}»: в тесте не хватило конкретики.")
    for item in list((scorecard or {}).get("missing_data") or [])[:2]:
        if isinstance(item, dict):
            evidence = _shorten(str(item.get("evidence") or item.get("label") or "").strip(), 120)
            if evidence:
                focus_areas.append(evidence)
    for item in list(script.get("risk_flags") or [])[:2]:
        if isinstance(item, dict):
            reason = _shorten(str(item.get("reason") or "").strip(), 120)
            if reason:
                focus_areas.append(reason)
    deduped: list[str] = []
    for item in focus_areas:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:3]


def _build_key_flags(
    *,
    candidate_profile: dict[str, Any],
    scorecard: dict[str, Any] | None,
    script: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    desired_income = str(candidate_profile.get("desired_income") or "").strip()
    if desired_income:
        flags.append(f"Ожидания по доходу: {_shorten(desired_income, 80)}")
    work_status = str(candidate_profile.get("work_status") or "").strip()
    if work_status:
        flags.append(f"Рабочий статус: {_shorten(work_status, 80)}")
    for item in list((scorecard or {}).get("blockers") or [])[:2]:
        if isinstance(item, dict):
            evidence = _shorten(str(item.get("evidence") or item.get("label") or "").strip(), 120)
            if evidence:
                flags.append(evidence)
    for item in list(script.get("checks") or [])[:2]:
        if isinstance(item, str) and item.strip():
            flags.append(_shorten(item, 120))
    deduped: list[str] = []
    for item in flags:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:3]


def build_structured_interview_script(
    *,
    script_payload: dict[str, Any],
    candidate_fio: str | None,
    candidate_profile: dict[str, Any],
    tests_context: dict[str, Any],
    scorecard: dict[str, Any] | None,
) -> dict[str, Any]:
    script = dict(script_payload or {})
    test1_latest = (((tests_context or {}).get("latest") or {}).get("TEST1") or {})
    test1_answers = list(test1_latest.get("answers") or [])
    weak_answers = sorted(
        [answer for answer in test1_answers if _question_score(answer) > 0],
        key=_question_score,
        reverse=True,
    )

    questions: list[dict[str, Any]] = []
    for index, answer in enumerate(weak_answers[:4], start=1):
        question_text = str(answer.get("question_text") or "").strip()
        if not question_text:
            continue
        user_answer = str(answer.get("user_answer") or "").strip()
        questions.append(
            {
                "id": f"personalized-{index}",
                "text": _personalized_question_text(question_text, user_answer),
                "type": "personalized",
                "source": f"test1_q_{int(answer.get('question_index') or index)}",
                "why": _personalized_question_why(question_text),
                "good_answer": _good_answer(question_text),
                "red_flags": _red_flags(question_text),
                "estimated_minutes": 3,
            }
        )

    risk_flags = [item for item in list(script.get("risk_flags") or []) if isinstance(item, dict)]
    for item in risk_flags[: max(0, 3 - len(questions))]:
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        questions.append(
            {
                "id": f"risk-{str(item.get('code') or len(questions) + 1).lower()}",
                "text": question,
                "type": "personalized",
                "source": str(item.get("code") or "risk"),
                "why": _shorten(str(item.get("reason") or "Проверяем потенциальный риск, который надо снять до следующего этапа."), 220),
                "good_answer": "Отвечает спокойно и конкретно, снимает риск фактами и понятной логикой.",
                "red_flags": "Уходит от прямого ответа, противоречит собственным данным или оставляет риск без конкретики.",
                "estimated_minutes": 3,
            }
        )

    standard_questions = [
        {
            "id": "standard-motivation",
            "text": "Почему вам сейчас интересна именно эта вакансия и что для вас будет главным критерием выбора работы?",
            "type": "standard",
            "source": None,
            "why": "Понимаем реальную мотивацию кандидата и не идём дальше на поверхностном интересе.",
            "good_answer": "Чётко формулирует мотив, связывает его с ролью и говорит о критериях выбора без противоречий.",
            "red_flags": "Говорит слишком общо, не понимает вакансию или фокусируется только на абстрактном «нужна любая работа».",
            "estimated_minutes": 3,
        },
        {
            "id": "standard-conditions",
            "text": "Какие условия для вас критичны: доход, график, локация, формат работы, обучение?",
            "type": "standard",
            "source": None,
            "why": "Снимаем риск расхождения ожиданий до назначения следующего этапа.",
            "good_answer": "Расставляет приоритеты и объясняет, где возможен компромисс, а где нет.",
            "red_flags": "Не может назвать критерии или озвучивает взаимоисключающие ожидания.",
            "estimated_minutes": 2,
        },
        {
            "id": "standard-availability",
            "text": "Когда вы готовы выйти на следующий этап и есть ли сейчас другие активные предложения?",
            "type": "standard",
            "source": None,
            "why": "Понимаем срочность кандидата и риск потери на следующих шагах.",
            "good_answer": "Называет конкретные сроки и открыто говорит о других процессах без уклонения.",
            "red_flags": "Избегает конкретики по срокам или скрывает наличие других офферов, хотя это влияет на решение.",
            "estimated_minutes": 2,
        },
    ]
    for item in standard_questions:
        if len(questions) >= 7:
            break
        questions.append(item)

    first_name = _first_name(candidate_fio)
    score_value = test1_latest.get("final_score")
    goal = str(script.get("call_goal") or "").strip() or "Понять реальную релевантность кандидата и принять решение по следующему шагу."
    opening = {
        "greeting": (
            f"{first_name}, здравствуйте. Спасибо, что нашли время. "
            "Я коротко проведу вас по разговору: сначала уточню пару моментов по опыту и формату работы, "
            "потом отвечу на ваши вопросы и зафиксирую следующий шаг."
        ),
        "icebreakers": [
            "Как вам удобнее: сначала коротко рассказать про вакансию или сначала сверить ваши ожидания?",
            "Какой у вас сейчас контекст поиска: активно выбираете или только присматриваетесь?",
            "Если этот разговор будет полезным, какой результат для вас будет хорошим к его концу?",
        ],
    }

    script["briefing"] = {
        "goal": goal,
        "focus_areas": _build_focus_areas(weak_answers=weak_answers, scorecard=scorecard, script=script),
        "key_flags": _build_key_flags(candidate_profile=candidate_profile, scorecard=scorecard, script=script),
    }
    script["opening"] = opening
    script["questions"] = questions[:8]
    script["closing_checklist"] = [
        "Ожидания по доходу и формату работы",
        "Готовность к следующему этапу и возможная дата выхода",
        "Другие активные предложения или ограничения по времени",
    ]
    script["closing_phrase"] = (
        "Спасибо за ответы. Я зафиксирую всё в карточке кандидата, сверю следующий шаг и обязательно вернусь к вам с точным решением и деталями."
    )
    if score_value is not None:
        script["briefing"]["goal"] = f"{goal} Тест 1: {float(score_value):.1f}%."
    return script
