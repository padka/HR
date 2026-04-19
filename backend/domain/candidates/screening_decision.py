from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ScreeningTestKind(str, Enum):
    TEST1 = "test1"


class ScreeningDecisionOutcome(str, Enum):
    INVITE_TO_INTERVIEW = "invite_to_interview"
    MANUAL_REVIEW = "manual_review"
    ASK_CLARIFICATION = "ask_clarification"
    HOLD = "hold"
    NOT_QUALIFIED_REQUIRES_HUMAN_REVIEW = "not_qualified_requires_human_review"


class ScreeningDecisionStrictness(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    INFORMATIONAL = "informational"


class ScreeningRequiredNextAction(str, Enum):
    OFFER_SLOTS = "offer_slots"
    RECRUITER_REVIEW = "recruiter_review"
    ASK_CANDIDATE = "ask_candidate"
    HOLD = "hold"
    HUMAN_DECLINE_REVIEW = "human_decline_review"


@dataclass(frozen=True, slots=True)
class ScreeningTestResultSnapshot:
    raw_score: int | None = None
    final_score: float | None = None
    total_questions: int = 0
    answered_questions: int = 0
    completed_at: datetime | None = None
    rating: str | None = None
    source: str | None = None

    @property
    def completion_ratio(self) -> float:
        if self.total_questions <= 0:
            return 0.0
        answered = max(self.answered_questions, 0)
        total = max(self.total_questions, 1)
        return min(answered / total, 1.0)


@dataclass(frozen=True, slots=True)
class ScreeningSignals:
    hard_blockers: tuple[str, ...] = ()
    soft_blockers: tuple[str, ...] = ()
    missing_data: tuple[str, ...] = ()
    clarification_signals: tuple[str, ...] = ()
    operational_holds: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScreeningContext:
    candidate_id: int
    application_id: int | None = None
    requisition_id: int | None = None
    vacancy_id: int | None = None
    city_id: int | None = None
    candidate_tz: str | None = None
    source: str | None = None
    channel: str | None = None
    surface: str | None = None


@dataclass(frozen=True, slots=True)
class ScreeningDecisionResult:
    outcome: ScreeningDecisionOutcome
    reason_code: str
    explanation: str
    strictness: ScreeningDecisionStrictness
    required_next_action: ScreeningRequiredNextAction
    event_payload: dict[str, Any] = field(default_factory=dict)


def evaluate_test1_screening_decision(
    *,
    candidate_id: int,
    application_id: int | None,
    result_snapshot: ScreeningTestResultSnapshot,
    signals: ScreeningSignals,
    context: ScreeningContext,
) -> ScreeningDecisionResult:
    completion_ratio = result_snapshot.completion_ratio
    payload = {
        "candidate_id": candidate_id,
        "application_id": application_id,
        "test_kind": ScreeningTestKind.TEST1.value,
        "completion_ratio": completion_ratio,
        "raw_score": result_snapshot.raw_score,
        "final_score": result_snapshot.final_score,
        "total_questions": result_snapshot.total_questions,
        "answered_questions": result_snapshot.answered_questions,
        "completed_at": result_snapshot.completed_at.isoformat()
        if result_snapshot.completed_at is not None
        else None,
        "rating": result_snapshot.rating,
        "source": result_snapshot.source,
        "channel": context.channel,
        "surface": context.surface,
        "requisition_id": context.requisition_id,
        "vacancy_id": context.vacancy_id,
        "city_id": context.city_id,
        "reason_signals": {
            "hard_blockers": list(signals.hard_blockers),
            "soft_blockers": list(signals.soft_blockers),
            "missing_data": list(signals.missing_data),
            "clarification_signals": list(signals.clarification_signals),
            "operational_holds": list(signals.operational_holds),
            "notes": list(signals.notes),
        },
    }

    if signals.operational_holds:
        return ScreeningDecisionResult(
            outcome=ScreeningDecisionOutcome.HOLD,
            reason_code="screening_operational_hold",
            explanation=(
                "Автоматическое продолжение после Теста 1 приостановлено "
                "из-за operational hold."
            ),
            strictness=ScreeningDecisionStrictness.SOFT,
            required_next_action=ScreeningRequiredNextAction.HOLD,
            event_payload=payload,
        )

    if signals.hard_blockers:
        return ScreeningDecisionResult(
            outcome=ScreeningDecisionOutcome.NOT_QUALIFIED_REQUIRES_HUMAN_REVIEW,
            reason_code="screening_hard_blocker_requires_human_review",
            explanation=(
                "По результатам Теста 1 найден явный hard-blocker, "
                "но финальное решение должен принять рекрутер."
            ),
            strictness=ScreeningDecisionStrictness.HARD,
            required_next_action=ScreeningRequiredNextAction.HUMAN_DECLINE_REVIEW,
            event_payload=payload,
        )

    if signals.clarification_signals:
        return ScreeningDecisionResult(
            outcome=ScreeningDecisionOutcome.ASK_CLARIFICATION,
            reason_code="assessment_requires_clarification",
            explanation=(
                "После Теста 1 остались детали, которые нельзя безопасно "
                "интерпретировать автоматически."
            ),
            strictness=ScreeningDecisionStrictness.SOFT,
            required_next_action=ScreeningRequiredNextAction.ASK_CANDIDATE,
            event_payload=payload,
        )

    if (
        result_snapshot.total_questions <= 0
        or result_snapshot.answered_questions <= 0
        or signals.missing_data
    ):
        return ScreeningDecisionResult(
            outcome=ScreeningDecisionOutcome.MANUAL_REVIEW,
            reason_code="assessment_missing_required_context",
            explanation=(
                "После Теста 1 не хватает данных или обязательного бизнес-контекста "
                "для безопасного автоматического решения."
            ),
            strictness=ScreeningDecisionStrictness.SOFT,
            required_next_action=ScreeningRequiredNextAction.RECRUITER_REVIEW,
            event_payload=payload,
        )

    if completion_ratio < 1.0 or signals.soft_blockers:
        return ScreeningDecisionResult(
            outcome=ScreeningDecisionOutcome.MANUAL_REVIEW,
            reason_code="assessment_borderline_manual_review",
            explanation=(
                "Результат Теста 1 неполный или содержит soft-blockers, "
                "поэтому требуется ручная проверка рекрутера."
            ),
            strictness=ScreeningDecisionStrictness.SOFT,
            required_next_action=ScreeningRequiredNextAction.RECRUITER_REVIEW,
            event_payload=payload,
        )

    return ScreeningDecisionResult(
        outcome=ScreeningDecisionOutcome.INVITE_TO_INTERVIEW,
        reason_code="assessment_complete_ready_for_interview",
        explanation=(
            "Тест 1 завершён, обязательные данные присутствуют, "
            "явных blockers для перехода к предложению слотов нет."
        ),
        strictness=ScreeningDecisionStrictness.INFORMATIONAL,
        required_next_action=ScreeningRequiredNextAction.OFFER_SLOTS,
        event_payload=payload,
    )


__all__ = [
    "ScreeningContext",
    "ScreeningDecisionOutcome",
    "ScreeningDecisionResult",
    "ScreeningDecisionStrictness",
    "ScreeningRequiredNextAction",
    "ScreeningSignals",
    "ScreeningTestKind",
    "ScreeningTestResultSnapshot",
    "evaluate_test1_screening_decision",
]
