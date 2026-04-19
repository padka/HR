from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.apps.bot.city_registry import (
    CityInfo,
    find_candidate_city_by_id,
    find_candidate_city_by_name,
    list_candidate_cities,
)
from backend.apps.bot.config import (
    DEFAULT_TZ,
    FOLLOWUP_NOTICE_PERIOD,
    FOLLOWUP_STUDY_FLEX,
    FOLLOWUP_STUDY_MODE,
    FOLLOWUP_STUDY_SCHEDULE,
    TEST1_QUESTIONS,
)
from backend.apps.bot.test1_validation import (
    Test1Payload,
    apply_partial_validation,
    convert_age,
)
from backend.core.settings import get_settings
from backend.domain.applications import (
    ApplicationEventCommand,
    ApplicationEventPublisher,
    ApplicationEventType,
    PrimaryApplicationResolver,
    ResolutionStatus,
    ResolverContext,
    SqlAlchemyApplicationEventRepository,
    SqlAlchemyApplicationResolverRepository,
    SqlAlchemyApplicationUnitOfWork,
)
from backend.domain.candidates.models import (
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    CandidateJourneyStepState,
    CandidateJourneyStepStatus,
    QuestionAnswer,
    TestResult,
    User,
)
from backend.domain.candidates.screening_decision import (
    ScreeningContext,
    ScreeningDecisionOutcome,
    ScreeningDecisionResult,
    ScreeningRequiredNextAction,
    ScreeningSignals,
    ScreeningTestResultSnapshot,
    evaluate_test1_screening_decision,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import apply_candidate_status
from backend.domain.slot_offer_policy import build_interview_offer_plan
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

TEST1_STEP_KEY = "test1"
TEST1_COMPLETED_STEP_KEY = "test1_completed"
BOOKING_STEP_KEY = "booking"

NEXT_ACTION_SELECT_INTERVIEW_SLOT = "select_interview_slot"
NEXT_ACTION_RECRUITER_REVIEW = "recruiter_review"
NEXT_ACTION_ASK_CANDIDATE = "ask_candidate"
NEXT_ACTION_HOLD = "hold"
NEXT_ACTION_HUMAN_DECLINE_REVIEW = "human_decline_review"


@dataclass(frozen=True, slots=True)
class Test1DraftState:
    answers: dict[str, str]
    payload: dict[str, Any]
    question_ids: list[str]
    city_id: int | None
    city_name: str | None
    candidate_tz: str


@dataclass(frozen=True, slots=True)
class Test1SharedCompletionResult:
    test_result_id: int
    screening_decision: dict[str, Any] | None
    interview_offer: dict[str, Any] | None
    required_next_action: str
    current_step_key: str
    is_completed: bool = True


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_question_id(question: dict[str, Any], idx: int) -> str:
    qid = question.get("id")
    if not qid:
        qid = question.get("question_id") or f"q{idx + 1}"
        question["id"] = qid
    return str(qid)


def _validation_feedback(qid: str, exc: ValidationError) -> tuple[str, list[str]]:
    hints: list[str] = []
    if qid == "fio":
        return (
            "Укажите полные фамилию, имя и отчество кириллицей.",
            ["Иванов Иван Иванович", "Петрова Мария Сергеевна"],
        )
    if qid == "age":
        return (
            "Возраст должен быть от 18 до 60 лет. Укажите возраст цифрами.",
            ["Например: 23"],
        )
    if qid in {
        "status",
        "format",
        FOLLOWUP_STUDY_MODE["id"],
        FOLLOWUP_STUDY_SCHEDULE["id"],
        FOLLOWUP_STUDY_FLEX["id"],
    }:
        return ("Выберите один из вариантов в списке.", hints)

    errors = exc.errors()
    if errors:
        return (errors[0].get("msg", "Проверьте ответ."), hints)
    return ("Проверьте ответ.", hints)


def _should_insert_study_flex(validated: Test1Payload, schedule_answer: str) -> bool:
    study_mode = (validated.study_mode or "").lower()
    if "очно" not in study_mode:
        return False
    normalized = schedule_answer.strip()
    if normalized == "Нет, не смогу":
        return False
    return normalized in {
        "Да, смогу",
        "Смогу, но нужен запас по времени",
        "Будет сложно",
    }


async def _resolve_candidate_city(answer: str, metadata: Mapping[str, Any]) -> CityInfo | None:
    meta_city_id = metadata.get("city_id") or metadata.get("value")
    if meta_city_id is not None:
        try:
            city = await find_candidate_city_by_id(int(meta_city_id))
            if city is not None:
                return city
        except (TypeError, ValueError):
            pass

    meta_label = metadata.get("name") or metadata.get("label")
    if isinstance(meta_label, str):
        city = await find_candidate_city_by_name(meta_label)
        if city is not None:
            return city

    if answer:
        city = await find_candidate_city_by_name(answer)
        if city is not None:
            return city

    return None


def build_test1_sequence(
    answers: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    sequence = deepcopy(list(TEST1_QUESTIONS))
    working_answers = {str(key): str(value) for key, value in dict(answers or {}).items()}
    for idx, question in enumerate(sequence):
        _ensure_question_id(question, idx)

    status_answer = working_answers.get("status", "")
    insert_pos = next(
        (idx for idx, question in enumerate(sequence) if _ensure_question_id(question, idx) == "status"),
        None,
    )
    if insert_pos is not None:
        lowered = status_answer.lower()
        sequence_insert_pos = insert_pos + 1
        existing_ids = {_ensure_question_id(question, idx) for idx, question in enumerate(sequence)}
        if "работ" in lowered and FOLLOWUP_NOTICE_PERIOD["id"] not in existing_ids:
            sequence.insert(sequence_insert_pos, deepcopy(FOLLOWUP_NOTICE_PERIOD))
            sequence_insert_pos += 1
            existing_ids.add(FOLLOWUP_NOTICE_PERIOD["id"])
        elif "уч" in lowered:
            if FOLLOWUP_STUDY_MODE["id"] not in existing_ids:
                sequence.insert(sequence_insert_pos, deepcopy(FOLLOWUP_STUDY_MODE))
                sequence_insert_pos += 1
                existing_ids.add(FOLLOWUP_STUDY_MODE["id"])
            if FOLLOWUP_STUDY_SCHEDULE["id"] not in existing_ids:
                sequence.insert(sequence_insert_pos, deepcopy(FOLLOWUP_STUDY_SCHEDULE))

    study_schedule_answer = working_answers.get(FOLLOWUP_STUDY_SCHEDULE["id"], "")
    study_mode_answer = working_answers.get(FOLLOWUP_STUDY_MODE["id"], "")
    if study_schedule_answer and study_mode_answer:
        try:
            validated = apply_partial_validation(
                {
                    "study_mode": study_mode_answer,
                    "study_schedule": study_schedule_answer,
                }
            )
        except ValidationError:
            validated = Test1Payload.model_construct(
                study_mode=study_mode_answer,
                study_schedule=study_schedule_answer,
            )
        if _should_insert_study_flex(validated, study_schedule_answer):
            existing_ids = {_ensure_question_id(question, idx) for idx, question in enumerate(sequence)}
            if FOLLOWUP_STUDY_FLEX["id"] not in existing_ids:
                schedule_idx = next(
                    (
                        idx
                        for idx, question in enumerate(sequence)
                        if _ensure_question_id(question, idx) == FOLLOWUP_STUDY_SCHEDULE["id"]
                    ),
                    len(sequence) - 1,
                )
                sequence.insert(schedule_idx + 1, deepcopy(FOLLOWUP_STUDY_FLEX))

    for idx, question in enumerate(sequence):
        _ensure_question_id(question, idx)
    return sequence


async def materialize_test1_questions(
    answers: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    sequence = build_test1_sequence(answers)
    candidate_cities: list[CityInfo] | None = None
    result: list[dict[str, Any]] = []

    for idx, question in enumerate(sequence):
        qid = _ensure_question_id(question, idx)
        payload = {
            "id": qid,
            "prompt": str(question.get("prompt") or question.get("text") or ""),
            "placeholder": question.get("placeholder"),
            "helper": question.get("helper"),
            "question_index": idx + 1,
        }
        options = question.get("options")
        if qid == "city":
            candidate_cities = candidate_cities or await list_candidate_cities()
            payload["options"] = [
                {
                    "label": city.display_name or city.name_plain,
                    "value": city.name_plain,
                    "city_id": city.id,
                    "tz": city.tz,
                }
                for city in candidate_cities
            ]
        elif isinstance(options, list) and options:
            payload["options"] = [
                {
                    "label": str(option.get("label") or option.get("text") or option.get("value"))
                    if isinstance(option, dict)
                    else str(option),
                    "value": str(option.get("value") or option.get("label") or option.get("text"))
                    if isinstance(option, dict)
                    else str(option),
                }
                for option in options
            ]
        else:
            payload["options"] = []
        result.append(payload)
    return result


def _question_map(sequence: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for idx, question in enumerate(sequence):
        mapping[_ensure_question_id(question, idx)] = question
    return mapping


def _match_question_option_value(
    question: Mapping[str, Any],
    answer: str,
) -> tuple[str | None, list[str]]:
    raw_options = question.get("options")
    if not isinstance(raw_options, list) or not raw_options:
        return answer, []

    normalized_answer = answer.strip().casefold()
    hints: list[str] = []
    seen_hints: set[str] = set()

    for option in raw_options:
        if isinstance(option, dict):
            label = str(option.get("label") or option.get("text") or option.get("value") or "").strip()
            value = str(option.get("value") or option.get("label") or option.get("text") or "").strip()
        else:
            label = str(option).strip()
            value = label
        visible = label or value
        if visible and visible not in seen_hints:
            hints.append(visible)
            seen_hints.add(visible)

        candidates = {item.casefold() for item in (label, value) if item}
        if normalized_answer and normalized_answer in candidates:
            return (value or label), hints

    return None, hints


async def merge_test1_answers(
    *,
    existing_answers: Mapping[str, Any] | None,
    existing_payload: Mapping[str, Any] | None,
    existing_city_id: int | None,
    existing_city_name: str | None,
    existing_candidate_tz: str | None,
    submitted_answers: Mapping[str, Any],
) -> Test1DraftState:
    answers = {str(key): str(value) for key, value in dict(existing_answers or {}).items()}
    payload_data: dict[str, Any] = dict(existing_payload or {})
    city_id = existing_city_id
    city_name = existing_city_name
    candidate_tz = str(existing_candidate_tz or DEFAULT_TZ)

    for raw_qid, raw_value in submitted_answers.items():
        qid = str(raw_qid)
        answer_clean = str(raw_value or "").strip()
        if not answer_clean:
            continue

        current_sequence = build_test1_sequence(answers)
        question = _question_map(current_sequence).get(qid)
        if question is None:
            raise ValueError(f"Unknown Test1 question id: {qid}")

        metadata: Mapping[str, Any] = {}
        if qid == "city":
            city_info = await _resolve_candidate_city(answer_clean, metadata)
            if city_info is None:
                city_names = [city.name for city in await list_candidate_cities()][:5]
                hints = ", ".join(city_names) if city_names else "Доступные города не найдены"
                raise ValueError(
                    "Пока работаем в указанных городах. Выберите подходящий вариант из списка."
                    if not hints
                    else f"Пока работаем в указанных городах. Например: {hints}"
                )
            payload_data["city_id"] = city_info.id
            payload_data["city_name"] = city_info.name
            city_id = city_info.id
            city_name = city_info.name
            candidate_tz = city_info.tz or DEFAULT_TZ
            answers[qid] = city_info.name
        else:
            matched_option, option_hints = _match_question_option_value(question, answer_clean)
            if matched_option is None:
                joined_hints = ", ".join(option_hints)
                raise ValueError(
                    "Выберите один из вариантов в списке."
                    if not joined_hints
                    else f"Выберите один из вариантов в списке: {joined_hints}"
                )
            answer_clean = matched_option
            if qid == "fio":
                payload_data["fio"] = answer_clean
                answers[qid] = answer_clean
            elif qid == "age":
                try:
                    payload_data["age"] = convert_age(answer_clean)
                except ValueError as exc:
                    raise ValueError(str(exc)) from exc
                answers[qid] = str(payload_data["age"])
            elif qid == "status":
                payload_data["status"] = answer_clean
                answers[qid] = answer_clean
            elif qid == "format":
                payload_data["format_choice"] = answer_clean
                answers[qid] = answer_clean
            elif qid == FOLLOWUP_STUDY_MODE["id"]:
                payload_data["study_mode"] = answer_clean
                answers[qid] = answer_clean
            elif qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
                payload_data["study_schedule"] = answer_clean
                answers[qid] = answer_clean
            elif qid == FOLLOWUP_STUDY_FLEX["id"]:
                payload_data["study_flex"] = answer_clean
                answers[qid] = answer_clean
            else:
                answers[qid] = answer_clean

        try:
            validated_model = apply_partial_validation(payload_data)
        except ValidationError as exc:
            message, hints = _validation_feedback(qid, exc)
            suffix = f" Примеры: {', '.join(hints)}" if hints else ""
            raise ValueError(f"{message}{suffix}") from exc

        payload_data = validated_model.model_dump(exclude_none=True)
        if city_id is not None:
            payload_data["city_id"] = city_id
        if city_name:
            payload_data["city_name"] = city_name
        if candidate_tz:
            payload_data["candidate_tz"] = candidate_tz

    sequence = build_test1_sequence(answers)
    question_ids = [_ensure_question_id(question, idx) for idx, question in enumerate(sequence)]
    return Test1DraftState(
        answers=answers,
        payload=payload_data,
        question_ids=question_ids,
        city_id=city_id,
        city_name=city_name,
        candidate_tz=candidate_tz,
    )


def build_test1_result_question_data(
    *,
    sequence: list[dict[str, Any]],
    answers: Mapping[str, Any],
) -> list[dict[str, Any]]:
    question_data: list[dict[str, Any]] = []
    for idx, question in enumerate(sequence, start=1):
        question_id = _ensure_question_id(question, idx - 1)
        prompt = str(question.get("prompt") or question.get("text") or "")
        answer = str(answers.get(question_id, "") or "")
        question_data.append(
            {
                "question_index": idx,
                "question_text": prompt,
                "correct_answer": None,
                "user_answer": answer,
                "attempts_count": 1 if answer else 0,
                "time_spent": 0,
                "is_correct": True,
                "overtime": False,
            }
        )
    return question_data


def build_test1_result_snapshot(
    *,
    test_result: TestResult,
    sequence: list[dict[str, Any]],
    answers: Mapping[str, Any],
) -> ScreeningTestResultSnapshot:
    answered_questions = 0
    for idx, question in enumerate(sequence):
        qid = _ensure_question_id(question, idx)
        if str(answers.get(qid, "")).strip():
            answered_questions += 1
    return ScreeningTestResultSnapshot(
        raw_score=test_result.raw_score,
        final_score=test_result.final_score,
        total_questions=len(sequence),
        answered_questions=answered_questions,
        completed_at=test_result.created_at,
        rating=test_result.rating,
        source=test_result.source,
    )


def build_test1_screening_signals(
    *,
    payload: Mapping[str, Any],
    candidate: User | None,
) -> ScreeningSignals:
    missing_data: list[str] = []
    if not str(payload.get("fio") or "").strip():
        missing_data.append("fio")
    if payload.get("city_id") is None:
        missing_data.append("city_id")
    if not str(payload.get("candidate_tz") or "").strip():
        missing_data.append("candidate_tz")
    if candidate is None or not str(candidate.candidate_id or "").strip():
        missing_data.append("candidate_anchor")

    clarification_signals: list[str] = []
    if str(payload.get("format_choice") or "").strip() == "Нужен гибкий график":
        clarification_signals.append("format_requires_clarification")

    soft_blockers: list[str] = []
    if str(payload.get("study_schedule") or "").strip() == "Смогу, но нужен запас по времени":
        soft_blockers.append("study_schedule_needs_buffer")

    hard_blockers: list[str] = []
    if str(payload.get("format_choice") or "").strip() == "Пока не готов":
        hard_blockers.append("format_not_ready")
    if str(payload.get("study_schedule") or "").strip() in {"Будет сложно", "Нет, не смогу"}:
        hard_blockers.append("study_schedule_conflict")
    if str(payload.get("study_flex") or "").strip().lower().startswith("нет"):
        hard_blockers.append("study_flex_declined")

    return ScreeningSignals(
        hard_blockers=tuple(hard_blockers),
        soft_blockers=tuple(soft_blockers),
        missing_data=tuple(missing_data),
        clarification_signals=tuple(clarification_signals),
        operational_holds=(),
        notes=(),
    )


def to_public_required_next_action(
    required_next_action: ScreeningRequiredNextAction | str | None,
) -> str:
    value = (
        required_next_action.value
        if isinstance(required_next_action, ScreeningRequiredNextAction)
        else str(required_next_action or "").strip()
    )
    mapping = {
        ScreeningRequiredNextAction.OFFER_SLOTS.value: NEXT_ACTION_SELECT_INTERVIEW_SLOT,
        ScreeningRequiredNextAction.RECRUITER_REVIEW.value: NEXT_ACTION_RECRUITER_REVIEW,
        ScreeningRequiredNextAction.ASK_CANDIDATE.value: NEXT_ACTION_ASK_CANDIDATE,
        ScreeningRequiredNextAction.HOLD.value: NEXT_ACTION_HOLD,
        ScreeningRequiredNextAction.HUMAN_DECLINE_REVIEW.value: NEXT_ACTION_HUMAN_DECLINE_REVIEW,
    }
    return mapping.get(value, value or NEXT_ACTION_RECRUITER_REVIEW)


def build_screening_decision_payload(
    decision: ScreeningDecisionResult | None,
) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "outcome": decision.outcome.value,
        "reason_code": decision.reason_code,
        "explanation": decision.explanation,
        "strictness": decision.strictness.value,
        "required_next_action": to_public_required_next_action(decision.required_next_action),
    }


def _build_completion_payload(
    *,
    test_result_id: int,
    screening_decision: dict[str, Any] | None,
    interview_offer: dict[str, Any] | None,
    required_next_action: str,
    current_step_key: str,
) -> dict[str, Any]:
    return {
        "completed": True,
        "completed_at": _utcnow().isoformat(),
        "test_result_id": test_result_id,
        "screening_decision": screening_decision,
        "interview_offer": interview_offer,
        "required_next_action": required_next_action,
        "current_step_key": current_step_key,
    }


def _build_status_request(
    *,
    candidate_id: int,
    status_from: str | None,
    status_to: CandidateStatus,
    source_ref: str,
    correlation_id: str,
    base_idempotency_key: str,
    source_system: str,
    actor_type: str | None,
    actor_id: str | int | None,
) -> Any:
    from backend.apps.admin_ui.services.candidates.application_dual_write import (
        CandidateStatusDualWriteRequest,
        build_candidate_status_payload_fingerprint,
    )

    principal_type = actor_type or "system"
    return CandidateStatusDualWriteRequest(
        idempotency_key=f"{base_idempotency_key}:{status_to.value}",
        correlation_id=correlation_id,
        payload_fingerprint=build_candidate_status_payload_fingerprint(
            candidate_id=candidate_id,
            status_to=status_to,
            reason=None,
            comment=None,
            principal_type=principal_type,
            principal_id=actor_id,
            source_ref=source_ref,
        ),
        principal_type=principal_type,
        principal_id=actor_id,
        source_system=source_system,
        source_ref=source_ref,
    )


def _resolve_application_anchor_sync(
    sync_session,
    *,
    candidate_id: int,
    correlation_id: str,
    source_system: str,
    source_ref: str,
    actor_type: str | None,
    actor_id: str | int | None,
) -> tuple[int, int | None]:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    resolver = PrimaryApplicationResolver(
        SqlAlchemyApplicationResolverRepository(sync_session, uow=uow)
    )
    with uow.begin():
        resolution = resolver.ensure_application_for_candidate(
            candidate_id,
            ResolverContext(
                producer_family="candidate_test1_screening",
                source_system=source_system,
                source_ref=source_ref,
                candidate_id=candidate_id,
                actor_type=actor_type or "system",
                actor_id=actor_id,
                correlation_id=correlation_id,
                allow_create=True,
                require_application_anchor=True,
            ),
        )
        if resolution.status not in {ResolutionStatus.RESOLVED, ResolutionStatus.CREATED}:
            raise RuntimeError("test1 screening could not resolve a primary application")
        if resolution.application_id is None:
            raise RuntimeError("test1 screening returned no application id")
        return resolution.application_id, resolution.requisition_id


def _publish_screening_events_sync(
    sync_session,
    *,
    candidate_id: int,
    application_id: int,
    requisition_id: int | None,
    test_result: TestResult,
    screening_decision: dict[str, Any],
    correlation_id: str,
    base_idempotency_key: str,
    source_system: str,
    source_ref_prefix: str,
    channel: str,
    actor_type: str | None,
    actor_id: str | int | None,
) -> None:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    publisher = ApplicationEventPublisher(
        SqlAlchemyApplicationEventRepository(sync_session, uow=uow)
    )
    base_metadata = {
        "test_kind": "test1",
        "test_result_id": int(test_result.id),
        "decision_outcome": screening_decision["outcome"],
        "reason_code": screening_decision["reason_code"],
        "required_next_action": screening_decision["required_next_action"],
        "strictness": screening_decision["strictness"],
    }
    with uow.begin():
        publisher.publish_application_event(
            ApplicationEventCommand(
                producer_family="candidate_test1_screening",
                idempotency_key=f"{base_idempotency_key}:assessment.completed",
                event_type=ApplicationEventType.ASSESSMENT_COMPLETED.value,
                candidate_id=candidate_id,
                source_system=source_system,
                source_ref=f"{source_ref_prefix}:assessment_completed",
                correlation_id=correlation_id,
                actor_type=actor_type or "system",
                actor_id=actor_id,
                application_id=application_id,
                requisition_id=requisition_id,
                channel=channel,
                metadata_json=base_metadata,
            )
        )
        publisher.publish_application_event(
            ApplicationEventCommand(
                producer_family="candidate_test1_screening",
                idempotency_key=f"{base_idempotency_key}:screening.decision_made",
                event_type=ApplicationEventType.SCREENING_DECISION_MADE.value,
                candidate_id=candidate_id,
                source_system=source_system,
                source_ref=f"{source_ref_prefix}:screening_decision",
                correlation_id=correlation_id,
                actor_type=actor_type or "system",
                actor_id=actor_id,
                application_id=application_id,
                requisition_id=requisition_id,
                channel=channel,
                metadata_json=base_metadata,
            )
        )


async def _apply_test1_statuses(
    *,
    session: AsyncSession,
    candidate: User,
    decision: ScreeningDecisionResult | None,
    test_result: TestResult,
    source_system: str,
    source_ref_prefix: str,
    actor_type: str | None,
    actor_id: str | int | None,
    channel: str,
) -> tuple[int | None, int | None]:
    from backend.apps.admin_ui.services.candidates.application_dual_write import (
        claim_candidate_status_transition,
        finalize_candidate_status_dual_write,
    )

    invite_selected = (
        decision is not None and decision.outcome == ScreeningDecisionOutcome.INVITE_TO_INTERVIEW
    )
    if not get_settings().candidate_status_dual_write_enabled:
        await apply_candidate_status(
            candidate,
            CandidateStatus.TEST1_COMPLETED,
            session=session,
            force=True,
            actor_type=actor_type or "system",
            actor_id=None,
            reason=f"{source_system} test1 completion",
        )
        if invite_selected:
            await apply_candidate_status(
                candidate,
                CandidateStatus.WAITING_SLOT,
                session=session,
                force=True,
                actor_type=actor_type or "system",
                actor_id=None,
                reason=f"{source_system} test1 invite_to_interview",
            )
        return None, None

    correlation_id = f"{source_system}-test1-{candidate.id}-{test_result.id}"
    base_idempotency_key = f"{source_system}-test1-{candidate.id}-{test_result.id}"
    application_id: int | None = None
    requisition_id: int | None = None

    async def _transition(target_status: CandidateStatus, *, source_ref_suffix: str) -> None:
        nonlocal application_id, requisition_id
        current_status = getattr(getattr(candidate, "candidate_status", None), "value", None)
        if current_status == target_status.value:
            return
        request = _build_status_request(
            candidate_id=int(candidate.id),
            status_from=current_status,
            status_to=target_status,
            source_ref=f"{source_ref_prefix}:{source_ref_suffix}",
            correlation_id=correlation_id,
            base_idempotency_key=base_idempotency_key,
            source_system=source_system,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        claim = await claim_candidate_status_transition(session, request)
        if claim.reused:
            return
        await apply_candidate_status(
            candidate,
            target_status,
            session=session,
            force=True,
            actor_type=actor_type or "system",
            actor_id=None,
            reason=f"{source_system} test1 screening",
        )
        result = await finalize_candidate_status_dual_write(
            session,
            candidate_id=int(candidate.id),
            status_from=current_status,
            status_to=target_status.value,
            reason=None,
            comment=None,
            request=request,
        )
        application_id = result.application_id
        requisition_id = result.requisition_id

    await _transition(CandidateStatus.TEST1_COMPLETED, source_ref_suffix="test1_completed")
    if invite_selected:
        await _transition(CandidateStatus.WAITING_SLOT, source_ref_suffix="waiting_slot")

    if decision is not None:
        screening_payload = build_screening_decision_payload(decision)
        if application_id is None or screening_payload is None:
            application_id, requisition_id = await session.run_sync(
                _resolve_application_anchor_sync,
                candidate_id=int(candidate.id),
                correlation_id=correlation_id,
                source_system=source_system,
                source_ref=f"{source_ref_prefix}:screening_anchor",
                actor_type=actor_type,
                actor_id=actor_id,
            )
        await session.run_sync(
            _publish_screening_events_sync,
            candidate_id=int(candidate.id),
            application_id=int(application_id),
            requisition_id=requisition_id,
            test_result=test_result,
            screening_decision=screening_payload,
            correlation_id=correlation_id,
            base_idempotency_key=base_idempotency_key,
            source_system=source_system,
            source_ref_prefix=source_ref_prefix,
            channel=channel,
            actor_type=actor_type,
            actor_id=actor_id,
        )

    return application_id, requisition_id


async def complete_test1_for_candidate(
    *,
    session: AsyncSession,
    candidate: User,
    journey_session: CandidateJourneySession,
    step_state: CandidateJourneyStepState,
    source: str,
    channel: str,
    surface: str,
    actor_type: str | None,
    actor_id: str | int | None,
) -> Test1SharedCompletionResult:
    payload = dict(step_state.payload_json or {})
    completion = payload.get("completion")
    if isinstance(completion, dict) and completion.get("completed"):
        return Test1SharedCompletionResult(
            test_result_id=int(completion.get("test_result_id") or 0),
            screening_decision=completion.get("screening_decision"),
            interview_offer=completion.get("interview_offer"),
            required_next_action=str(
                completion.get("required_next_action") or NEXT_ACTION_RECRUITER_REVIEW
            ),
            current_step_key=str(
                completion.get("current_step_key") or journey_session.current_step_key or TEST1_COMPLETED_STEP_KEY
            ),
            is_completed=True,
        )

    draft = dict(payload.get("draft") or {})
    answers = {str(key): str(value) for key, value in dict(draft.get("answers") or {}).items()}
    sequence = build_test1_sequence(answers)
    if not answers:
        raise ValueError("Test1 draft has no answers to complete.")

    question_data = build_test1_result_question_data(sequence=sequence, answers=answers)
    test_result = TestResult(
        user_id=int(candidate.id),
        raw_score=len(question_data),
        final_score=float(len(question_data)),
        rating="TEST1",
        source=source,
        total_time=0,
    )
    session.add(test_result)
    await session.flush()
    for item in question_data:
        session.add(
            QuestionAnswer(
                test_result_id=int(test_result.id),
                question_index=int(item["question_index"]),
                question_text=str(item["question_text"]),
                correct_answer=item["correct_answer"],
                user_answer=item["user_answer"],
                attempts_count=int(item["attempts_count"]),
                time_spent=int(item["time_spent"]),
                is_correct=bool(item["is_correct"]),
                overtime=bool(item["overtime"]),
            )
        )

    screening_decision_result: ScreeningDecisionResult | None = None
    screening_decision_payload: dict[str, Any] | None = None
    interview_offer_payload: dict[str, Any] | None = None
    required_next_action = NEXT_ACTION_RECRUITER_REVIEW
    current_step_key = TEST1_COMPLETED_STEP_KEY

    if get_settings().test1_screening_decision_enabled:
        screening_decision_result = evaluate_test1_screening_decision(
            candidate_id=int(candidate.id),
            application_id=journey_session.application_id,
            result_snapshot=build_test1_result_snapshot(
                test_result=test_result,
                sequence=sequence,
                answers=answers,
            ),
            signals=build_test1_screening_signals(
                payload=draft.get("payload") or {},
                candidate=candidate,
            ),
            context=ScreeningContext(
                candidate_id=int(candidate.id),
                application_id=journey_session.application_id,
                requisition_id=None,
                vacancy_id=None,
                city_id=draft.get("city_id"),
                candidate_tz=draft.get("candidate_tz"),
                source=source,
                channel=channel,
                surface=surface,
            ),
        )
        screening_decision_payload = build_screening_decision_payload(screening_decision_result)
        required_next_action = to_public_required_next_action(
            screening_decision_result.required_next_action
        )
        if screening_decision_result.outcome == ScreeningDecisionOutcome.INVITE_TO_INTERVIEW:
            offer_plan = await build_interview_offer_plan(
                candidate_id=int(candidate.id),
                application_id=journey_session.application_id,
                city_id=int(draft.get("city_id")),
                candidate_tz=str(draft.get("candidate_tz") or DEFAULT_TZ),
                recruiter_id=getattr(candidate, "responsible_recruiter_id", None),
                purpose="interview",
            )
            interview_offer_payload = dict(offer_plan.payload)
            if get_settings().auto_interview_offer_after_test1_enabled:
                current_step_key = BOOKING_STEP_KEY

    payload["completion"] = _build_completion_payload(
        test_result_id=int(test_result.id),
        screening_decision=screening_decision_payload,
        interview_offer=interview_offer_payload,
        required_next_action=required_next_action,
        current_step_key=current_step_key,
    )
    step_state.payload_json = payload
    step_state.status = CandidateJourneyStepStatus.COMPLETED.value
    step_state.completed_at = _utcnow()

    journey_payload = dict(journey_session.payload_json or {})
    journey_payload["candidate_access"] = {
        **dict(journey_payload.get("candidate_access") or {}),
        "allowed_next_actions": (
            [required_next_action]
            if required_next_action == NEXT_ACTION_SELECT_INTERVIEW_SLOT
            else []
        ),
        "test1": {
            "test_result_id": int(test_result.id),
            "screening_decision": screening_decision_payload,
            "interview_offer": interview_offer_payload,
            "required_next_action": required_next_action,
        },
    }
    journey_session.payload_json = journey_payload
    journey_session.current_step_key = current_step_key
    journey_session.last_activity_at = _utcnow()

    await _apply_test1_statuses(
        session=session,
        candidate=candidate,
        decision=screening_decision_result,
        test_result=test_result,
        source_system=source,
        source_ref_prefix=f"{source}:test1",
        actor_type=actor_type,
        actor_id=actor_id,
        channel=channel,
    )
    await session.flush()

    return Test1SharedCompletionResult(
        test_result_id=int(test_result.id),
        screening_decision=screening_decision_payload,
        interview_offer=interview_offer_payload,
        required_next_action=required_next_action,
        current_step_key=current_step_key,
        is_completed=True,
    )


def serialize_step_payload(
    *,
    draft_state: Test1DraftState,
    source: str,
    surface: str,
) -> dict[str, Any]:
    return {
        "draft": {
            "version": 1,
            "question_ids": list(draft_state.question_ids),
            "answers": dict(draft_state.answers),
            "payload": dict(draft_state.payload),
            "source": source,
            "surface": surface,
            "city_id": draft_state.city_id,
            "city_name": draft_state.city_name,
            "candidate_tz": draft_state.candidate_tz,
            "updated_at": _utcnow().isoformat(),
        }
    }


def build_test1_restart_snapshot(
    *,
    journey_session: CandidateJourneySession | None,
    step_state: CandidateJourneyStepState | None,
    current_status: CandidateStatus | str | None,
    actor_type: str | None,
    actor_id: str | int | None,
    reason: str | None,
    restarted_at: datetime | None = None,
) -> dict[str, Any] | None:
    if step_state is None and journey_session is None:
        return None

    payload = dict(step_state.payload_json or {}) if step_state is not None else {}
    draft = dict(payload.get("draft") or {})
    completion = dict(payload.get("completion") or {})
    booking_context = dict(
        dict(journey_session.payload_json or {}).get("candidate_access", {}).get("booking_context") or {}
    ) if journey_session is not None else {}
    timestamp = restarted_at or _utcnow()
    snapshot: dict[str, Any] = {
        "version": 1,
        "restarted_at": timestamp.isoformat(),
        "reason": str(reason or "").strip() or None,
        "actor_type": actor_type,
        "actor_id": str(actor_id) if actor_id is not None else None,
        "candidate_status": (
            current_status.value if isinstance(current_status, CandidateStatus) else str(current_status or "").strip() or None
        ),
        "current_step_key": getattr(journey_session, "current_step_key", None),
        "last_surface": getattr(journey_session, "last_surface", None),
        "last_auth_method": getattr(journey_session, "last_auth_method", None),
        "required_next_action": str(completion.get("required_next_action") or "").strip() or None,
        "test_result_id": int(completion.get("test_result_id") or 0) or None,
        "had_completion": bool(completion.get("completed")),
        "screening_outcome": str(
            dict(completion.get("screening_decision") or {}).get("outcome") or ""
        ).strip() or None,
        "answered_questions": len(dict(draft.get("answers") or {})),
        "question_ids": list(draft.get("question_ids") or []),
        "city_id": draft.get("city_id") or dict(completion.get("interview_offer") or {}).get("city_id"),
        "city_name": draft.get("city_name") or dict(completion.get("interview_offer") or {}).get("city_name"),
        "booking_context": {
            "city_id": booking_context.get("city_id"),
            "city_name": booking_context.get("city_name"),
            "recruiter_id": booking_context.get("recruiter_id"),
            "recruiter_name": booking_context.get("recruiter_name"),
        } if booking_context else None,
    }
    return {key: value for key, value in snapshot.items() if value is not None}


def reset_test1_progress(
    *,
    journey_session: CandidateJourneySession | None,
    step_state: CandidateJourneyStepState | None,
    restart_snapshot: dict[str, Any] | None,
    reset_at: datetime | None = None,
) -> None:
    now = reset_at or _utcnow()
    if step_state is not None:
        payload = dict(step_state.payload_json or {})
        history = list(payload.get("history") or [])
        if restart_snapshot:
            history.append(dict(restart_snapshot))
        step_state.payload_json = {"history": history} if history else None
        step_state.status = CandidateJourneyStepStatus.PENDING.value
        step_state.completed_at = None
        step_state.started_at = now

    if journey_session is None:
        return

    journey_payload = dict(journey_session.payload_json or {})
    candidate_access = dict(journey_payload.get("candidate_access") or {})
    history = list(candidate_access.get("history") or [])
    if restart_snapshot:
        history.append(
            {
                key: restart_snapshot.get(key)
                for key in (
                    "restarted_at",
                    "reason",
                    "candidate_status",
                    "current_step_key",
                    "last_surface",
                    "required_next_action",
                    "test_result_id",
                    "screening_outcome",
                )
                if restart_snapshot.get(key) is not None
            }
        )
    for key in ("allowed_next_actions", "test1", "booking_context", "chat_cursor", "active_surface"):
        candidate_access.pop(key, None)
    if history:
        candidate_access["history"] = history
    else:
        candidate_access.pop("history", None)
    if candidate_access:
        journey_payload["candidate_access"] = candidate_access
    else:
        journey_payload.pop("candidate_access", None)

    journey_session.payload_json = journey_payload or None
    journey_session.current_step_key = TEST1_STEP_KEY
    journey_session.last_access_session_id = None
    journey_session.last_surface = None
    journey_session.last_auth_method = None
    journey_session.status = CandidateJourneySessionStatus.ACTIVE.value
    journey_session.completed_at = None
    journey_session.last_activity_at = now
    journey_session.session_version = max(1, int(journey_session.session_version or 1)) + 1


def parse_test_question_payload(raw_payload: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return payload


__all__ = [
    "BOOKING_STEP_KEY",
    "NEXT_ACTION_ASK_CANDIDATE",
    "NEXT_ACTION_HOLD",
    "NEXT_ACTION_HUMAN_DECLINE_REVIEW",
    "NEXT_ACTION_RECRUITER_REVIEW",
    "NEXT_ACTION_SELECT_INTERVIEW_SLOT",
    "TEST1_COMPLETED_STEP_KEY",
    "TEST1_STEP_KEY",
    "Test1DraftState",
    "Test1SharedCompletionResult",
    "build_screening_decision_payload",
    "build_test1_result_question_data",
    "build_test1_result_snapshot",
    "build_test1_restart_snapshot",
    "build_test1_screening_signals",
    "build_test1_sequence",
    "complete_test1_for_candidate",
    "materialize_test1_questions",
    "merge_test1_answers",
    "parse_test_question_payload",
    "reset_test1_progress",
    "serialize_step_payload",
    "to_public_required_next_action",
]
