from __future__ import annotations

from datetime import UTC, datetime

from backend.domain.candidates.screening_decision import (
    ScreeningContext,
    ScreeningDecisionOutcome,
    ScreeningRequiredNextAction,
    ScreeningSignals,
    ScreeningTestResultSnapshot,
    evaluate_test1_screening_decision,
)


def _snapshot(
    *,
    total_questions: int = 5,
    answered_questions: int = 5,
) -> ScreeningTestResultSnapshot:
    return ScreeningTestResultSnapshot(
        raw_score=5,
        final_score=5.0,
        total_questions=total_questions,
        answered_questions=answered_questions,
        completed_at=datetime.now(UTC),
        rating="TEST1",
        source="bot",
    )


def _context(*, city_id: int | None = 1) -> ScreeningContext:
    return ScreeningContext(
        candidate_id=101,
        application_id=None,
        requisition_id=None,
        vacancy_id=None,
        city_id=city_id,
        candidate_tz="Europe/Moscow",
        source="bot",
        channel="telegram",
        surface="telegram_bot",
    )


def test_complete_snapshot_without_blockers_invites_to_interview() -> None:
    decision = evaluate_test1_screening_decision(
        candidate_id=101,
        application_id=None,
        result_snapshot=_snapshot(),
        signals=ScreeningSignals(),
        context=_context(),
    )

    assert decision.outcome == ScreeningDecisionOutcome.INVITE_TO_INTERVIEW
    assert decision.required_next_action == ScreeningRequiredNextAction.OFFER_SLOTS


def test_borderline_completion_routes_to_manual_review() -> None:
    decision = evaluate_test1_screening_decision(
        candidate_id=101,
        application_id=None,
        result_snapshot=_snapshot(total_questions=8, answered_questions=6),
        signals=ScreeningSignals(),
        context=_context(),
    )

    assert decision.outcome == ScreeningDecisionOutcome.MANUAL_REVIEW


def test_missing_context_routes_to_manual_review() -> None:
    decision = evaluate_test1_screening_decision(
        candidate_id=101,
        application_id=None,
        result_snapshot=_snapshot(),
        signals=ScreeningSignals(missing_data=("city_id",)),
        context=_context(city_id=None),
    )

    assert decision.outcome == ScreeningDecisionOutcome.MANUAL_REVIEW
    assert decision.reason_code == "assessment_missing_required_context"


def test_clarification_signal_routes_to_ask_clarification() -> None:
    decision = evaluate_test1_screening_decision(
        candidate_id=101,
        application_id=None,
        result_snapshot=_snapshot(),
        signals=ScreeningSignals(clarification_signals=("format_requires_clarification",)),
        context=_context(),
    )

    assert decision.outcome == ScreeningDecisionOutcome.ASK_CLARIFICATION


def test_hard_blocker_never_auto_rejects() -> None:
    decision = evaluate_test1_screening_decision(
        candidate_id=101,
        application_id=None,
        result_snapshot=_snapshot(),
        signals=ScreeningSignals(hard_blockers=("age_policy_conflict",)),
        context=_context(),
    )

    assert decision.outcome == ScreeningDecisionOutcome.NOT_QUALIFIED_REQUIRES_HUMAN_REVIEW
    assert decision.required_next_action == ScreeningRequiredNextAction.HUMAN_DECLINE_REVIEW


def test_operational_hold_routes_to_hold() -> None:
    decision = evaluate_test1_screening_decision(
        candidate_id=101,
        application_id=None,
        result_snapshot=_snapshot(),
        signals=ScreeningSignals(operational_holds=("paused_requisition",)),
        context=_context(),
    )

    assert decision.outcome == ScreeningDecisionOutcome.HOLD
