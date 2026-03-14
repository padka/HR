from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

MetricStatus = Literal["met", "not_met", "unknown"]
Recommendation = Literal["od_recommended", "clarify_before_od", "not_recommended"]

OBJECTIVE_WEIGHTS: dict[str, int] = {
    "experience_relevance": 25,
    "field_format_readiness": 20,
    "communication_clarity": 20,
    "motivation_alignment": 15,
    "od_readiness_test_gate": 20,
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
    "communication_clarity": "Понятная коммуникация",
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
_START_DELAY_NEEDLES = (
    "нужна отработка",
    "надо отработать",
    "смогу выйти через месяц",
    "смогу выйти через 2 недели",
    "смогу выйти через две недели",
    "не могу выйти быстро",
    "не готов начать в ближайшие дни",
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
) -> dict[str, Any]:
    weight = OBJECTIVE_WEIGHTS[key]
    return {
        "key": key,
        "label": OBJECTIVE_LABELS[key],
        "score": _points_for_status(status, weight),
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
    people_signal = (signals.get("people_interaction") or {}).get("level")
    communication_signal = (signals.get("communication") or {}).get("level")
    field_format_answer = candidate_profile.get("field_format_readiness")

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

    if _has_any(combined_text, _COMMUNICATION_BLOCKER_NEEDLES):
        _append_blocker(
            blockers,
            "communication_barrier",
            "Коммуникационный барьер",
            "В данных есть указание на языковой/речевой барьер, который может мешать работе с клиентом.",
        )
        communication_status: MetricStatus = "not_met"
        communication_evidence = "Есть прямой сигнал о значимом речевом или языковом барьере."
    elif communication_signal in {"high", "medium"} or people_signal in {"high", "medium"}:
        communication_status = "met"
        communication_evidence = "Ответы и опыт указывают на рабочий уровень коммуникации."
    elif answer_text:
        communication_status = "unknown"
        communication_evidence = "Нужна дополнительная проверка речи и ясности формулировок на звонке."
        _append_missing(
            missing_data,
            "communication_clarity",
            OBJECTIVE_LABELS["communication_clarity"],
            "Нужно проверить, насколько кандидат чётко формулирует мысли в живом диалоге.",
        )
    else:
        communication_status = "unknown"
        communication_evidence = "Недостаточно данных для оценки коммуникации."
        _append_missing(
            missing_data,
            "communication_clarity",
            OBJECTIVE_LABELS["communication_clarity"],
            "Нет свободных ответов для оценки ясности коммуникации.",
        )
    objective_metrics.append(
        _objective_metric(
            "communication_clarity",
            status=communication_status,
            evidence=communication_evidence,
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

    if _has_any(combined_text, _START_DELAY_NEEDLES):
        _append_blocker(
            blockers,
            "start_delay",
            "Невозможность быстро начать",
            "В данных есть подтверждение, что кандидат не сможет выйти или начать обучение в требуемый срок.",
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
