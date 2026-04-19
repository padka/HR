from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

MetricStatus = Literal["met", "not_met", "unknown"]
Recommendation = Literal["od_recommended", "clarify_before_od", "not_recommended"]

OBJECTIVE_WEIGHTS: dict[str, int] = {
    "experience_relevance": 20,
    "field_format_readiness": 20,
    "start_readiness": 20,
    "answer_quality": 15,
    "age_alignment": 5,
    "motivation_alignment": 10,
    "od_readiness_test_gate": 10,
}

SEMANTIC_WEIGHTS: dict[str, int] = {
    "resume_substance": 30,
    "answer_substance": 25,
    "client_communication_inference": 25,
    "interest_for_role": 20,
}

OBJECTIVE_LABELS: dict[str, str] = {
    "experience_relevance": "Релевантный опыт",
    "field_format_readiness": "Готовность к полевому формату",
    "start_readiness": "Скорость выхода",
    "answer_quality": "Качество ответов",
    "age_alignment": "Возрастной профиль",
    "motivation_alignment": "Мотивация к роли",
    "od_readiness_test_gate": "Готовность к ОД по тесту",
}

SEMANTIC_LABELS: dict[str, str] = {
    "resume_substance": "Содержательность резюме",
    "answer_substance": "Содержательность ответов",
    "client_communication_inference": "Потенциал клиентской коммуникации",
    "interest_for_role": "Интерес к роли",
}

_POSITIVE_EXPERIENCE_NEEDLES = (
    "продаж",
    "клиент",
    "переговор",
    "бариста",
    "официант",
    "волонт",
    "промоут",
    "администратор",
    "консульт",
    "кассир",
    "офис-менедж",
)
_FIELD_NEGATIVE_NEEDLES = (
    "не готов ездить",
    "не готова ездить",
    "не люблю разъезды",
    "не готов к разъезд",
    "не готова к разъезд",
    "только удаленно",
    "только удалённо",
    "только офис",
    "без выездов",
)
_FIELD_POSITIVE_NEEDLES = (
    "без проблем",
    "подходит",
    "подходит такой формат",
    "готов",
    "готова",
    "комфортно",
    "не проблема",
    "нормально отношусь",
    "готов работать в полях",
    "готова работать в полях",
)
_FIELD_AMBIGUOUS_NEEDLES = (
    "рассматриваю",
    "если условия",
    "если устро",
    "зависит",
    "надо подумать",
    "не уверен",
    "не уверена",
    "скорее да",
    "в целом да",
    "готов, если",
    "готов если",
    "готова, если",
    "готова если",
    "при условии",
    "посмотрим",
)
_COMMUNICATION_BLOCKER_NEEDLES = (
    "языковой барьер",
    "плохо говорю",
    "не понимаю русский",
    "не понимаю по-русски",
    "сильное заикание",
    "неразборчивая речь",
)
_START_BLOCKER_NEEDLES = (
    "нужна отработка",
    "надо отработать",
    "смогу выйти через месяц",
    "смогу выйти через 2 недели",
    "смогу выйти через две недели",
    "не могу выйти быстро",
    "не готов начать в ближайшие дни",
)
_START_IMMEDIATE_NEEDLES = (
    "сразу",
    "хоть завтра",
    "уже готов",
    "уже готова",
    "готов завтра",
    "готова завтра",
    "могу завтра",
    "могу выйти сразу",
    "готов приступить",
    "готова приступить",
    "сегодня",
    "завтра",
)
_START_SOON_NEEDLES = (
    "через 1 день",
    "через 2 дня",
    "через 3 дня",
    "в ближайшие 2 дня",
    "в ближайшие 3 дня",
    "в течение 2 дней",
    "в течение 3 дней",
    "пару дней",
)
_MOTIVATION_POSITIVE_NEEDLES = (
    "доход",
    "развива",
    "зарабаты",
    "общен",
    "коммуник",
    "клиент",
    "переговор",
    "рост",
)
_ROLE_INTEREST_NEEDLES = (
    "яндекс",
    "карты",
    "клиент",
    "переговор",
    "предприним",
    "бизнес",
    "продаж",
    "встреч",
)
_ANSWER_USEFUL_NEEDLES = (
    "клиент",
    "продаж",
    "переговор",
    "встреч",
    "предприним",
    "опыт",
    "готов",
    "график",
    "доход",
    "обуч",
)


@dataclass(frozen=True)
class ScorecardState:
    metrics: list[dict[str, Any]]
    blockers: list[dict[str, str]]
    missing_data: list[dict[str, str]]
    objective_score: int
    semantic_score: int
    final_score: int
    recommendation: Recommendation


def fit_level_from_score(score: int | None) -> str:
    if score is None:
        return "unknown"
    value = max(0, min(100, int(score)))
    if value >= 75:
        return "high"
    if value >= 50:
        return "medium"
    if value > 0:
        return "low"
    return "unknown"


def _points_for_status(status: MetricStatus, weight: int) -> int:
    if status == "met":
        return int(weight)
    if status == "unknown":
        return int(round(weight * 0.4))
    return 0


def _normalize_text(*parts: Any) -> str:
    text = " ".join(str(part or "") for part in parts if part)
    return re.sub(r"\s+", " ", text).strip().lower()


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _classify_field_format_answer(raw: Any) -> tuple[MetricStatus | None, str | None]:
    text = _normalize_text(raw)
    if not text:
        return None, None
    if _has_any(text, _FIELD_NEGATIVE_NEEDLES):
        return "not_met", "Есть явный отказ от выездного или полевого формата."
    if _has_any(text, _FIELD_AMBIGUOUS_NEEDLES):
        return "unknown", "Ответ про полевой формат звучит условно и требует уточнения."
    if text in {"да", "ага", "конечно", "без проблем", "подходит"} or _has_any(text, _FIELD_POSITIVE_NEEDLES):
        return "met", "Кандидат прямо подтвердил готовность к полевому формату."
    return None, None


def _extract_delay_days(text: str) -> int | None:
    if not text:
        return None
    if _has_any(text, _START_IMMEDIATE_NEEDLES):
        return 0
    if _has_any(text, _START_SOON_NEEDLES):
        return 2
    range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(дн|дня|дней)", text)
    if range_match:
        return max(int(range_match.group(1)), int(range_match.group(2)))
    day_match = re.search(r"(\d+)\s*(дн|дня|дней|сут)", text)
    if day_match:
        return int(day_match.group(1))
    week_match = re.search(r"(\d+)\s*(недел|недели|неделю)", text)
    if week_match:
        return int(week_match.group(1)) * 7
    month_match = re.search(r"(\d+)\s*(месяц|месяца|месяцев)", text)
    if month_match:
        return int(month_match.group(1)) * 30
    if "пару дней" in text:
        return 2
    if "несколько дней" in text:
        return 3
    return None


def _classify_start_readiness_answer(raw: Any) -> tuple[MetricStatus | None, int | None, str | None, bool]:
    text = _normalize_text(raw)
    if not text:
        return None, None, None, False
    delay_days = _extract_delay_days(text)
    weight = OBJECTIVE_WEIGHTS["start_readiness"]
    if _has_any(text, _START_BLOCKER_NEEDLES) or (delay_days is not None and delay_days >= 14):
        return "not_met", 0, "Кандидат не сможет быстро выйти или пройти обучение в ближайшем цикле.", True
    if delay_days == 0:
        return "met", weight, "Кандидат готов выйти сразу или на следующий день.", False
    if delay_days is not None and delay_days <= 2:
        return "met", weight - 3, "Кандидат готов выйти в течение 1–2 дней.", False
    if delay_days is not None and delay_days <= 5:
        return "unknown", int(round(weight * 0.5)), "Кандидат сможет выйти, но не сразу; срок старта чуть растянут.", False
    if delay_days is not None:
        return "unknown", int(round(weight * 0.2)), "Старт возможен, но с заметной задержкой относительно приоритетного окна.", False
    return "unknown", int(round(weight * 0.4)), "Срок выхода описан нечетко, нужен короткий follow-up.", False


def _score_answer_quality(
    *,
    answer_text: str,
    candidate_profile: dict[str, Any],
    signals: dict[str, Any],
) -> tuple[MetricStatus, int | None, str]:
    if _has_any(answer_text, _COMMUNICATION_BLOCKER_NEEDLES):
        return "not_met", 0, "В ответах есть прямой сигнал о речевом или языковом барьере."

    sections = [
        str(candidate_profile.get("work_experience") or "").strip(),
        str(candidate_profile.get("motivation") or "").strip(),
        str(candidate_profile.get("skills") or "").strip(),
        str(candidate_profile.get("expectations") or "").strip(),
    ]
    filled_sections = [item for item in sections if item]
    word_count = len(re.findall(r"\w+", answer_text, flags=re.UNICODE))
    useful_hits = sum(1 for needle in _ANSWER_USEFUL_NEEDLES if needle in answer_text)
    written_expression = bool(((signals.get("communication") or {}).get("written_expression")))
    weight = OBJECTIVE_WEIGHTS["answer_quality"]

    if not answer_text:
        return "unknown", None, "Нет развернутых ответов для оценки качества рассуждения."
    if word_count >= 35 and len(filled_sections) >= 2 and (useful_hits >= 2 or written_expression):
        return "met", weight, "Свободные ответы развернутые и содержат полезные детали для оценки кандидата."
    if word_count >= 16 and len(filled_sections) >= 2:
        return "unknown", int(round(weight * 0.6)), "Ответы содержательные, но не везде хватает конкретики."
    return "unknown", int(round(weight * 0.3)), "Ответы короткие; по рассуждению и конкретике нужен follow-up."


def _append_missing(target: list[dict[str, str]], key: str, label: str, evidence: str) -> None:
    if any(item.get("key") == key for item in target):
        return
    target.append({"key": key, "label": label, "evidence": evidence})


def _append_blocker(target: list[dict[str, str]], key: str, label: str, evidence: str) -> None:
    if any(item.get("key") == key for item in target):
        return
    target.append({"key": key, "label": label, "evidence": evidence})


def _objective_metric(
    key: str,
    *,
    status: MetricStatus,
    evidence: str,
    score: int | None = None,
) -> dict[str, Any]:
    weight = OBJECTIVE_WEIGHTS[key]
    safe_score = _points_for_status(status, weight) if score is None else max(0, min(weight, int(score)))
    return {
        "key": key,
        "label": OBJECTIVE_LABELS[key],
        "score": safe_score,
        "weight": weight,
        "status": status,
        "evidence": evidence,
    }


def _semantic_metric(
    key: str,
    *,
    score: int | None,
    status: MetricStatus,
    evidence: str,
) -> dict[str, Any]:
    weight = SEMANTIC_WEIGHTS[key]
    safe_score = 0 if score is None else max(0, min(weight, int(score)))
    return {
        "key": key,
        "label": SEMANTIC_LABELS[key],
        "score": safe_score,
        "weight": weight,
        "status": status,
        "evidence": evidence,
    }


def _parse_semantic_metric(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    key = str(item.get("key") or "").strip()
    if key not in SEMANTIC_WEIGHTS:
        return None
    status = str(item.get("status") or "unknown").strip().lower()
    if status not in {"met", "not_met", "unknown"}:
        status = "unknown"
    weight = SEMANTIC_WEIGHTS[key]
    raw_score = item.get("score")
    score = None
    if isinstance(raw_score, (int, float)):
        score = max(0, min(weight, int(round(float(raw_score)))))
    elif status == "met":
        score = weight
    elif status == "unknown":
        score = int(round(weight * 0.4))
    else:
        score = 0
    evidence = str(item.get("evidence") or "").strip()
    if not evidence:
        evidence = "Нужна дополнительная проверка на интервью."
    return _semantic_metric(key, score=score, status=status, evidence=evidence)


def _normalize_flag_items(items: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        label = str(item.get("label") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if not key and not label and not evidence:
            continue
        normalized.append(
            {
                "key": key or label or "unknown",
                "label": label or key or "Неуточнённый фактор",
                "evidence": evidence or "Требуется уточнение.",
            }
        )
    return normalized


def _dedupe_flag_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        key = str(item.get("key") or "").strip()
        if not key:
            key = str(item.get("label") or "").strip()
        if not key:
            key = str(item.get("evidence") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def build_candidate_scorecard(
    *,
    context: dict[str, Any],
    resume_context: dict[str, Any],
    llm_scorecard: dict[str, Any] | None,
) -> ScorecardState:
    candidate_profile = context.get("candidate_profile") or {}
    tests = context.get("tests") or {}
    interview_notes = (context.get("interview_notes") or {}).get("fields") or {}
    resume_text = _normalize_text(
        resume_context.get("headline"),
        resume_context.get("summary"),
        " ".join(str(x or "") for x in (resume_context.get("skills") or [])),
        " ".join(
            " ".join(str(v or "") for v in item.values())
            for item in (resume_context.get("employment_items") or [])
            if isinstance(item, dict)
        ),
    )
    answer_text = _normalize_text(
        candidate_profile.get("work_status"),
        candidate_profile.get("work_experience"),
        candidate_profile.get("motivation"),
        candidate_profile.get("skills"),
        candidate_profile.get("expectations"),
        " ".join(str(v or "") for v in interview_notes.values()),
    )
    combined_text = _normalize_text(resume_text, answer_text)
    signals = candidate_profile.get("signals") or {}
    field_format_answer = candidate_profile.get("field_format_readiness")
    start_readiness_answer = candidate_profile.get("start_readiness")
    age_years_raw = candidate_profile.get("age_years")
    age_years = int(age_years_raw) if isinstance(age_years_raw, int) else None

    objective_metrics: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    missing_data: list[dict[str, str]] = []

    has_relevant_experience = bool(resume_context.get("relevant_experience")) or _has_any(
        combined_text, _POSITIVE_EXPERIENCE_NEEDLES
    )
    if has_relevant_experience:
        objective_metrics.append(
            _objective_metric(
                "experience_relevance",
                status="met",
                evidence="Есть подтверждения опыта работы с клиентами/в продажах или смежных ролях.",
            )
        )
    elif combined_text:
        objective_metrics.append(
            _objective_metric(
                "experience_relevance",
                status="not_met",
                evidence="В данных не найден релевантный опыт по продажам или работе с людьми.",
            )
        )
    else:
        _append_missing(
            missing_data,
            "experience_relevance",
            OBJECTIVE_LABELS["experience_relevance"],
            "Нет резюме или описания опыта, нужно уточнить 2-3 последние роли.",
        )
        objective_metrics.append(
            _objective_metric(
                "experience_relevance",
                status="unknown",
                evidence="Опыта в данных недостаточно для вывода.",
            )
        )

    field_format_status, field_format_reason = _classify_field_format_answer(field_format_answer)
    if field_format_status == "not_met" or _has_any(combined_text, _FIELD_NEGATIVE_NEEDLES):
        _append_blocker(
            blockers,
            "field_format_refusal",
            "Отказ от полевого формата",
            (
                f"Ответ кандидата: {str(field_format_answer).strip()}"
                if field_format_status == "not_met" and str(field_format_answer or "").strip()
                else "Кандидат явно не готов к выездному/разъездному формату."
            ),
        )
        objective_metrics.append(
            _objective_metric(
                "field_format_readiness",
                status="not_met",
                evidence=(
                    f"{field_format_reason} Ответ: {str(field_format_answer).strip()}"
                    if field_format_status == "not_met" and str(field_format_answer or "").strip()
                    else "Есть явный отказ от выездного формата или предпочтение только удалённой/стационарной работе."
                ),
            )
        )
    elif field_format_status == "met":
        objective_metrics.append(
            _objective_metric(
                "field_format_readiness",
                status="met",
                evidence=f"{field_format_reason} Ответ: {str(field_format_answer).strip()}",
            )
        )
    elif field_format_status == "unknown":
        _append_missing(
            missing_data,
            "field_format_readiness",
            OBJECTIVE_LABELS["field_format_readiness"],
            f"Нужно уточнить, что кандидат имеет в виду: {str(field_format_answer).strip()}",
        )
        objective_metrics.append(
            _objective_metric(
                "field_format_readiness",
                status="unknown",
                evidence=f"{field_format_reason} Ответ: {str(field_format_answer).strip()}",
            )
        )
    elif combined_text:
        status: MetricStatus = "met" if any(
            token in combined_text for token in ("встреч", "разъезд", "выезд", "территор", "в движении")
        ) else "unknown"
        if status == "unknown":
            _append_missing(
                missing_data,
                "field_format_readiness",
                OBJECTIVE_LABELS["field_format_readiness"],
                "Нужно явно подтвердить готовность к выездной работе и перемещению по городу.",
            )
        objective_metrics.append(
            _objective_metric(
                "field_format_readiness",
                status=status,
                evidence=(
                    "Есть подтверждение готовности к активному полевому формату."
                    if status == "met"
                    else "Нет прямого подтверждения готовности к полевому формату."
                ),
            )
        )
    else:
        _append_missing(
            missing_data,
            "field_format_readiness",
            OBJECTIVE_LABELS["field_format_readiness"],
            "Нет данных о готовности к выездному формату.",
        )
        objective_metrics.append(
            _objective_metric(
                "field_format_readiness",
                status="unknown",
                evidence="Нужна верификация готовности к полевому формату.",
            )
        )

    start_status, start_score, start_evidence, start_blocker = _classify_start_readiness_answer(start_readiness_answer)
    if start_blocker:
        _append_blocker(
            blockers,
            "start_delay",
            "Невозможность быстро начать",
            start_evidence or "Кандидат не готов выйти в нужное окно старта.",
        )
    if start_status is None:
        _append_missing(
            missing_data,
            "start_readiness",
            OBJECTIVE_LABELS["start_readiness"],
            "Нужно уточнить, когда кандидат реально сможет выйти на обучение.",
        )
        objective_metrics.append(
            _objective_metric(
                "start_readiness",
                status="unknown",
                score=int(round(OBJECTIVE_WEIGHTS["start_readiness"] * 0.4)),
                evidence="Нет явного ответа о готовности начать в ближайшие дни.",
            )
        )
    else:
        objective_metrics.append(
            _objective_metric(
                "start_readiness",
                status=start_status,
                score=start_score,
                evidence=f"{start_evidence} Ответ: {str(start_readiness_answer).strip()}",
            )
        )

    answer_quality_status, answer_quality_score, answer_quality_evidence = _score_answer_quality(
        answer_text=answer_text,
        candidate_profile=candidate_profile,
        signals=signals,
    )
    if answer_quality_score is None:
        _append_missing(
            missing_data,
            "answer_quality",
            OBJECTIVE_LABELS["answer_quality"],
            "Нет свободных ответов, по которым можно понять ход мысли кандидата.",
        )
        objective_metrics.append(
            _objective_metric(
                "answer_quality",
                status="unknown",
                score=int(round(OBJECTIVE_WEIGHTS["answer_quality"] * 0.4)),
                evidence=answer_quality_evidence,
            )
        )
    else:
        if answer_quality_status == "not_met":
            _append_blocker(
                blockers,
                "communication_barrier",
                "Коммуникационный барьер",
                answer_quality_evidence,
            )
        elif answer_quality_status == "unknown" and answer_text:
            _append_missing(
                missing_data,
                "answer_quality",
                OBJECTIVE_LABELS["answer_quality"],
                "Нужно добрать 1-2 развернутых ответа, чтобы понять глубину рассуждения кандидата.",
            )
        objective_metrics.append(
            _objective_metric(
                "answer_quality",
                status=answer_quality_status,
                score=answer_quality_score,
                evidence=answer_quality_evidence,
            )
        )

    if age_years is None:
        _append_missing(
            missing_data,
            "age_alignment",
            OBJECTIVE_LABELS["age_alignment"],
            "Возраст не указан, поэтому возрастной сигнал нейтральный.",
        )
        objective_metrics.append(
            _objective_metric(
                "age_alignment",
                status="unknown",
                score=2,
                evidence="Возраст не указан, возрастной сигнал не подтвержден.",
            )
        )
    else:
        if 23 <= age_years <= 35:
            age_status: MetricStatus = "met"
            age_score = OBJECTIVE_WEIGHTS["age_alignment"]
            age_evidence = f"Возраст {age_years} попадает в приоритетный диапазон."
        elif 21 <= age_years <= 37:
            age_status = "unknown"
            age_score = 3
            age_evidence = f"Возраст {age_years} близок к приоритетному диапазону, сигнал умеренно положительный."
        else:
            age_status = "unknown"
            age_score = 1
            age_evidence = f"Возраст {age_years} вне приоритетного диапазона, но это не стоп-фактор."
        objective_metrics.append(
            _objective_metric(
                "age_alignment",
                status=age_status,
                score=age_score,
                evidence=age_evidence,
            )
        )

    if _has_any(combined_text, _MOTIVATION_POSITIVE_NEEDLES):
        motivation_status: MetricStatus = "met"
        motivation_evidence = "В ответах есть мотиваторы, релевантные роли: доход, развитие, общение или работа с клиентами."
    elif answer_text:
        motivation_status = "unknown"
        motivation_evidence = "Мотивация описана недостаточно конкретно."
        _append_missing(
            missing_data,
            "motivation_alignment",
            OBJECTIVE_LABELS["motivation_alignment"],
            "Нужно уточнить, почему кандидату интересна роль и что для него важно в работе.",
        )
    else:
        motivation_status = "unknown"
        motivation_evidence = "Нет данных о мотивации."
        _append_missing(
            missing_data,
            "motivation_alignment",
            OBJECTIVE_LABELS["motivation_alignment"],
            "Нет ответов по мотивации и ожиданиям.",
        )
    objective_metrics.append(
        _objective_metric(
            "motivation_alignment",
            status=motivation_status,
            evidence=motivation_evidence,
        )
    )

    test1_latest = ((tests.get("latest") or {}).get("TEST1") or {}) if isinstance(tests, dict) else {}
    test1_score_raw = test1_latest.get("final_score")
    test1_score = float(test1_score_raw) if isinstance(test1_score_raw, (int, float)) else None
    if test1_score is None:
        od_status: MetricStatus = "unknown"
        od_evidence = "Тест ещё не пройден или недоступен."
        _append_missing(
            missing_data,
            "od_readiness_test_gate",
            OBJECTIVE_LABELS["od_readiness_test_gate"],
            "Нет результата теста для допуска к ОД.",
        )
    elif test1_score >= 4:
        od_status = "met"
        od_evidence = f"Результат теста {test1_score:g}, порог допуска к ОД выполнен."
    else:
        od_status = "not_met"
        od_evidence = f"Результат теста {test1_score:g}, ниже порога 4 для допуска к ОД."
        _append_blocker(
            blockers,
            "test_gate_failed",
            "Тест ниже порога допуска",
            od_evidence,
        )
    objective_metrics.append(
        _objective_metric(
            "od_readiness_test_gate",
            status=od_status,
            evidence=od_evidence,
        )
    )

    llm_metrics_raw = ((llm_scorecard or {}).get("metrics") or []) if isinstance(llm_scorecard, dict) else []
    semantic_metrics_by_key = {
        metric["key"]: metric
        for metric in (_parse_semantic_metric(item) for item in llm_metrics_raw)
        if metric is not None
    }

    for key, weight in SEMANTIC_WEIGHTS.items():
        if key not in semantic_metrics_by_key:
            semantic_metrics_by_key[key] = _semantic_metric(
                key,
                score=int(round(weight * 0.4)),
                status="unknown",
                evidence="LLM-оценка не дала уверенного вывода, нужно уточнение на интервью.",
            )

    blockers.extend(_normalize_flag_items((llm_scorecard or {}).get("blockers") if isinstance(llm_scorecard, dict) else None))
    missing_data.extend(_normalize_flag_items((llm_scorecard or {}).get("missing_data") if isinstance(llm_scorecard, dict) else None))
    blockers = _dedupe_flag_items(blockers)
    missing_data = _dedupe_flag_items(missing_data)

    objective_score = sum(int(item.get("score") or 0) for item in objective_metrics)
    semantic_metrics = [semantic_metrics_by_key[key] for key in SEMANTIC_WEIGHTS]
    semantic_score = sum(int(item.get("score") or 0) for item in semantic_metrics)
    final_score = int(round(objective_score * 0.6 + semantic_score * 0.4))
    if blockers:
        final_score = min(final_score, 49)

    if blockers:
        recommendation: Recommendation = "not_recommended"
    elif final_score >= 75:
        recommendation = "od_recommended"
    else:
        recommendation = "clarify_before_od"

    return ScorecardState(
        metrics=[*objective_metrics, *semantic_metrics],
        blockers=blockers,
        missing_data=missing_data,
        objective_score=max(0, min(100, objective_score)),
        semantic_score=max(0, min(100, semantic_score)),
        final_score=max(0, min(100, final_score)),
        recommendation=recommendation,
    )
