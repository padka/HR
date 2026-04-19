# ruff: noqa: E402,F403,F405,I001,UP037
from __future__ import annotations

from sqlalchemy import select

from backend.core.db import async_session
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
    CandidateJourneyStepState,
    TestResult,
    User,
)
from backend.domain.candidates.test1_shared import (
    TEST1_STEP_KEY,
    Test1DraftState,
    complete_test1_for_candidate,
    serialize_step_payload,
)
from backend.domain.candidates.screening_decision import (
    ScreeningDecisionOutcome,
    ScreeningDecisionResult,
    ScreeningSignals,
    ScreeningTestResultSnapshot,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import (
    apply_candidate_status,
    set_status_test1_completed,
    set_status_waiting_slot,
)
from backend.domain.slot_offer_policy import (
    InterviewOfferMode,
    InterviewOfferPlan,
)

"""Test 1 flow services."""

from . import base as _base
from .base import *  # noqa: F403
from .broadcast import _share_test1_with_recruiters, notify_recruiters_waiting_slot
from .slot_flow import send_manual_scheduling_prompt

for _name in dir(_base):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)


@dataclass
class Test1AnswerResult:
    status: Literal["ok", "invalid", "reject"]
    message: Optional[str] = None
    hints: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    template_key: Optional[str] = None
    template_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Test1CompletionScreeningResult:
    candidate: User
    screening_decision: ScreeningDecisionResult | Dict[str, Any] | None
    interview_offer: Dict[str, Any] | None = None
    required_next_action: str | None = None
    current_step_key: str | None = None


REJECTION_TEMPLATES: Dict[str, str] = {
    "format_not_ready": "t1_format_reject",
    "schedule_conflict": "t1_schedule_reject",
    "study_flex_declined": "t1_schedule_reject",
}


async def _resolve_candidate_city(answer: str, metadata: Dict[str, Any]) -> Optional[CityInfo]:
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


def _validation_feedback(qid: str, exc: ValidationError) -> Tuple[str, List[str]]:
    hints: List[str] = []
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
    if qid in {"status", "format", FOLLOWUP_STUDY_MODE["id"], FOLLOWUP_STUDY_SCHEDULE["id"], FOLLOWUP_STUDY_FLEX["id"]}:
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


def _determine_test1_branch(
    qid: str,
    answer: str,
    payload: Test1Payload,
) -> Optional[Test1AnswerResult]:
    if qid == "format" and answer.strip() == "Пока не готов":
        return Test1AnswerResult(
            status="reject",
            reason="format_not_ready",
            template_key=REJECTION_TEMPLATES["format_not_ready"],
        )

    if qid == "format" and answer.strip() == "Нужен гибкий график":
        return Test1AnswerResult(
            status="ok",
            template_key="t1_format_clarify",
        )

    if qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
        normalized = answer.strip()
        normalized_lower = normalized.lower()
        if normalized in {"Нет, не смогу", "Будет сложно"} or normalized_lower in {
            "нет, не смогу",
            "будет сложно",
        }:
            return Test1AnswerResult(
                status="reject",
                reason="schedule_conflict",
                template_key=REJECTION_TEMPLATES["schedule_conflict"],
            )

    if qid == FOLLOWUP_STUDY_FLEX["id"]:
        if answer.strip().lower().startswith("нет"):
            return Test1AnswerResult(
                status="reject",
                reason="study_flex_declined",
                template_key=REJECTION_TEMPLATES["study_flex_declined"],
            )

    return None


def _format_validation_feedback(result: Test1AnswerResult) -> str:
    lines = [result.message or "Проверьте ответ."]
    if result.hints:
        lines.append("")
        lines.append("Примеры:")
        lines.extend(f"• {hint}" for hint in result.hints)
    return "\n".join(lines)


async def _handle_test1_rejection(user_id: int, result: Test1AnswerResult) -> None:
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    city_id = state.get("city_id")
    template_key = result.template_key or REJECTION_TEMPLATES.get(result.reason or "", "")
    context = dict(result.template_context)
    context.pop("city_id", None)
    context.setdefault("city_name", state.get("city_name") or "")
    message = await _render_tpl(city_id, template_key or "t1_schedule_reject", **context)
    if not message:
        message = (
            "Спасибо за ответы! На данном этапе мы не продолжаем процесс."
        )

    await get_bot().send_message(user_id, message)
    await record_test1_rejection(result.reason or "unknown")
    try:
        candidate = await candidate_services.get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST1_COMPLETED,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={"result": "failed", "reason": result.reason or "unknown"},
        )
    except Exception:
        logger.exception("Failed to log TEST1_COMPLETED (failed) for user %s", user_id)
    logger.info(
        "Test1 rejection emitted",
        extra={
            "user_id": user_id,
            "reason": result.reason,
            "city_id": city_id,
            "city_name": state.get("city_name"),
        },
    )
    await state_manager.delete(user_id)


async def _resolve_followup_message(
    result: Test1AnswerResult, state: State | Dict[str, Any]
) -> Optional[str]:
    if result.template_key is None and not result.message:
        return None

    template_context = dict(result.template_context)
    city_id = template_context.pop("city_id", None)
    if city_id is None and isinstance(state, dict):
        city_id = state.get("city_id")

    if result.template_key:
        text = await _render_tpl(city_id, result.template_key, **template_context)
        if text:
            return text

    return result.message


async def _notify_existing_reservation(callback: CallbackQuery, slot: Slot) -> None:
    user_id = callback.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    tz = state.get("candidate_tz") or slot.candidate_tz or DEFAULT_TZ
    labels = slot_local_labels(slot.start_utc, tz)
    message = await _render_tpl(
        getattr(slot, "candidate_city_id", None),
        "existing_reservation",
        recruiter_name=slot.recruiter.name if slot.recruiter else "",
        dt=labels["slot_datetime_local"],
    )
    await callback.answer("Бронь уже оформлена", show_alert=True)
    await get_bot().send_message(user_id, message)

def _format_prompt(prompt: Any) -> str:
    if isinstance(prompt, (list, tuple)):
        return "\n".join(str(p) for p in prompt)
    return str(prompt)


def _ensure_question_id(question: Dict[str, Any], idx: int) -> str:
    """
    Guarantee that a question dict has an 'id' field.
    If absent, derive a stable fallback based on position.
    """

    qid = question.get("id")
    if not qid:
        qid = question.get("question_id") or f"q{idx + 1}"
        question["id"] = qid
    return str(qid)


def _sync_test1_sequence_if_needed(state: State) -> None:
    """Ensure state's Test1 sequence matches the latest question bank.

    Admins can edit questions while the bot is running. The bot refreshes the global
    question bank via Redis pub/sub and at flow entry points, but active sessions may
    still carry an older `t1_sequence`. We resync best-effort and try to continue from
    the first unanswered question (by question id) to avoid repeating answered items.
    """

    current_version = get_questions_bank_version()
    stored_raw = state.get("questions_bank_version")
    try:
        stored_version = int(stored_raw) if stored_raw is not None else 0
    except (TypeError, ValueError):
        stored_version = 0
    if stored_version == current_version:
        return

    new_sequence: List[Dict[str, Any]] = list(TEST1_QUESTIONS)

    answers = state.get("test1_answers") or {}
    answered_ids: set[str] = set()
    if isinstance(answers, dict):
        answered_ids = {str(k) for k in answers.keys() if k is not None}

    if answered_ids:
        next_idx = 0
        for idx, q in enumerate(new_sequence):
            qid = q.get("id") or q.get("question_id") or f"q{idx + 1}"
            if str(qid) not in answered_ids:
                next_idx = idx
                break
        else:
            next_idx = len(new_sequence)
        state["t1_idx"] = next_idx
    else:
        if state.get("t1_idx") is None:
            state["t1_idx"] = 0

    state["t1_sequence"] = new_sequence
    state["questions_bank_version"] = current_version


async def send_test1_question(user_id: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    def _prepare(state: State) -> Tuple[State, Dict[str, Any]]:
        working = state
        _sync_test1_sequence_if_needed(working)
        sequence = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence
        idx = int(working.get("t1_idx") or 0)
        total = len(sequence)
        if idx >= total:
            return working, {"done": True}
        question = dict(sequence[idx])
        sequence[idx] = question
        _ensure_question_id(question, idx)
        return working, {
            "done": False,
            "idx": idx,
            "total": total,
            "question": question,
            "city_id": working.get("city_id"),
        }

    ctx = await state_manager.atomic_update(user_id, _prepare)
    if ctx.get("done"):
        await finalize_test1(user_id)
        return

    idx = ctx["idx"]
    total = ctx["total"]
    question: Dict[str, Any] = ctx["question"]
    city_id = ctx.get("city_id")

    progress = await _render_tpl(city_id, "t1_progress", n=idx + 1, total=total)
    progress_bar = create_progress_bar(idx, total)
    helper = question.get("helper")
    base_text = f"{progress}\n{progress_bar}\n\n{_format_prompt(question['prompt'])}"
    if helper:
        base_text += f"\n\n<i>{helper}</i>"

    resolved_options = await _resolve_test1_options(question)
    if resolved_options is not None:
        question["options"] = resolved_options

        def _attach_options(state: State) -> Tuple[State, None]:
            sequence = list(state.get("t1_sequence") or [])
            if idx < len(sequence):
                stored = dict(sequence[idx])
                stored["options"] = resolved_options
                sequence[idx] = stored
                state["t1_sequence"] = sequence
            return state, None

        await state_manager.atomic_update(user_id, _attach_options)

    options = question.get("options") or []
    if options:
        markup = _build_test1_options_markup(idx, options)
        sent = await bot.send_message(user_id, base_text, reply_markup=markup)
        requires_free_text = False
    else:
        placeholder = question.get("placeholder", "Введите ответ…")[:64]
        sent = await bot.send_message(
            user_id,
            base_text,
            reply_markup=ForceReply(selective=True, input_field_placeholder=placeholder),
        )
        requires_free_text = True

    def _store_prompt(state: State) -> Tuple[State, None]:
        state["t1_last_prompt_id"] = sent.message_id
        state["t1_last_question_text"] = base_text
        state["t1_current_idx"] = idx
        state["t1_requires_free_text"] = requires_free_text
        state["t1_last_hint_sent"] = False
        return state, None

    await state_manager.atomic_update(user_id, _store_prompt)


def _build_test1_options_markup(question_idx: int, options: List[Any]) -> Optional[Any]:
    if not options:
        return None
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = []
    for opt_idx, option in enumerate(options):
        buttons.append(
            [
                InlineKeyboardButton(
                    text=_extract_option_label(option),
                    callback_data=f"t1opt:{question_idx}:{opt_idx}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _extract_option_label(option: Any) -> str:
    if isinstance(option, dict):
        return str(option.get("label") or option.get("text") or option.get("value"))
    if isinstance(option, (tuple, list)) and option:
        return str(option[0])
    return str(option)


def _extract_option_value(option: Any) -> str:
    if isinstance(option, dict):
        return str(option.get("value") or option.get("label") or option.get("text"))
    if isinstance(option, (tuple, list)):
        return str(option[1] if len(option) > 1 else option[0])
    return str(option)


def _match_question_option_value(question: Dict[str, Any], answer: str) -> Tuple[Optional[str], List[str]]:
    raw_options = question.get("options")
    if not isinstance(raw_options, list) or not raw_options:
        return answer, []

    normalized_answer = answer.strip().casefold()
    hints: List[str] = []
    seen_hints: set[str] = set()

    for option in raw_options:
        label = _extract_option_label(option).strip()
        value = _extract_option_value(option).strip()
        visible = label or value
        if visible and visible not in seen_hints:
            hints.append(visible)
            seen_hints.add(visible)

        candidates = {item.casefold() for item in (label, value) if item}
        if normalized_answer and normalized_answer in candidates:
            return (value or label), hints

    return None, hints


async def _resolve_test1_options(question: Dict[str, Any]) -> Optional[List[Any]]:
    qid = question.get("id")
    if qid == "city":
        cities = await list_candidate_cities()
        return [
            {
                "label": city.display_name or city.name_plain,
                "value": city.name_plain,
                "city_id": city.id,
                "tz": city.tz,
                "name": city.name_plain,
            }
            for city in cities
        ]
    return None


def _shorten_answer(text: str, limit: int = 80) -> str:
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


def _build_test1_result_snapshot(
    *,
    test_result: TestResult,
    sequence: List[Dict[str, Any]],
    answers: Dict[str, Any],
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


def _build_test1_question_data(
    *,
    sequence: List[Dict[str, Any]],
    answers: Dict[str, Any],
) -> list[dict[str, Any]]:
    question_data: list[dict[str, Any]] = []
    for idx, question in enumerate(sequence, start=1):
        prompt = question.get("prompt", "")
        qid = question.get("id")
        answer = answers.get(qid, "")
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


def _build_test1_screening_signals(
    *,
    state: Dict[str, Any],
    candidate: User | None,
) -> ScreeningSignals:
    missing_data: list[str] = []
    if not str(state.get("fio") or "").strip():
        missing_data.append("fio")
    if state.get("city_id") is None:
        missing_data.append("city_id")
    if not str(state.get("candidate_tz") or "").strip():
        missing_data.append("candidate_tz")
    if candidate is None or not str(candidate.candidate_id or "").strip():
        missing_data.append("candidate_anchor")

    clarification_signals: list[str] = []
    if str(state.get("format_choice") or "").strip() == "Нужен гибкий график":
        clarification_signals.append("format_requires_clarification")

    soft_blockers: list[str] = []
    if str(state.get("study_schedule") or "").strip() == "Смогу, но нужен запас по времени":
        soft_blockers.append("study_schedule_needs_buffer")

    return ScreeningSignals(
        hard_blockers=(),
        soft_blockers=tuple(soft_blockers),
        missing_data=tuple(missing_data),
        clarification_signals=tuple(clarification_signals),
        operational_holds=(),
        notes=(),
    )


def _screening_followup_text(
    *,
    done_text: str,
    decision: ScreeningDecisionResult | Dict[str, Any],
) -> str:
    outcome = getattr(decision, "outcome", None)
    if not isinstance(outcome, ScreeningDecisionOutcome):
        raw_outcome = outcome if isinstance(outcome, str) else None
        if raw_outcome is None and isinstance(decision, dict):
            raw_outcome = str(decision.get("outcome") or "").strip()
        try:
            outcome = ScreeningDecisionOutcome(str(raw_outcome))
        except ValueError:
            return done_text

    outcome_notes = {
        ScreeningDecisionOutcome.MANUAL_REVIEW: (
            "Анкета передана рекрутеру на ручную проверку. "
            "Мы свяжемся с вами после проверки."
        ),
        ScreeningDecisionOutcome.ASK_CLARIFICATION: (
            "Нужно уточнить несколько деталей по анкете. "
            "Рекрутер свяжется с вами после проверки."
        ),
        ScreeningDecisionOutcome.HOLD: (
            "Анкета сохранена. Сейчас автоматически продолжить процесс нельзя, "
            "поэтому рекрутер вернётся к вам позже."
        ),
        ScreeningDecisionOutcome.NOT_QUALIFIED_REQUIRES_HUMAN_REVIEW: (
            "Анкета передана рекрутеру на дополнительную проверку. "
            "Финальное решение будет принимать человек."
        ),
    }
    note = outcome_notes.get(outcome)
    if not note:
        return done_text
    if done_text:
        return f"{done_text}\n\n{note}"
    return note


def _render_interview_offer_plan_message(
    *,
    plan: InterviewOfferPlan,
    candidate_tz: str,
) -> str:
    if plan.mode == InterviewOfferMode.SINGLE:
        title = "Мы подобрали ближайшее время для собеседования:"
    else:
        title = "Мы подобрали несколько ближайших вариантов для собеседования:"

    lines = [title]
    for index, option in enumerate(plan.options, start=1):
        dt_label = fmt_dt_local(option.start_utc, candidate_tz)
        prefix = "Рекомендуем" if option.is_recommended else f"Вариант {index}"
        lines.append(f"{prefix}: {dt_label}")
    lines.append("")
    lines.append("Ниже можно продолжить назначение через стандартный сценарий.")
    return "\n".join(lines)


def _render_interview_offer_payload_message(
    *,
    offer_payload: Dict[str, Any],
    candidate_tz: str,
) -> str:
    mode = str(offer_payload.get("mode") or InterviewOfferMode.SHORTLIST.value)
    if mode == InterviewOfferMode.SINGLE.value:
        title = "Мы подобрали ближайшее время для собеседования:"
    else:
        title = "Мы подобрали несколько ближайших вариантов для собеседования:"

    lines = [title]
    for index, option in enumerate(list(offer_payload.get("options") or []), start=1):
        raw_start = str(option.get("start_utc") or "")
        dt_label = raw_start
        if raw_start:
            try:
                dt_label = fmt_dt_local(datetime.fromisoformat(raw_start), candidate_tz)
            except ValueError:
                dt_label = raw_start
        prefix = "Рекомендуем" if option.get("is_recommended") else f"Вариант {index}"
        lines.append(f"{prefix}: {dt_label}")
    lines.append("")
    lines.append("Ниже можно продолжить назначение через стандартный сценарий.")
    return "\n".join(lines)


def _build_test1_status_dual_write_request(
    *,
    candidate_id: int,
    status_from: str | None,
    status_to: CandidateStatus,
    source_ref: str,
    correlation_id: str,
    base_idempotency_key: str,
) -> object:
    from backend.apps.admin_ui.services.candidates.application_dual_write import (
        CandidateStatusDualWriteRequest,
        build_candidate_status_payload_fingerprint,
    )

    return CandidateStatusDualWriteRequest(
        idempotency_key=f"{base_idempotency_key}:{status_to.value}",
        correlation_id=correlation_id,
        payload_fingerprint=build_candidate_status_payload_fingerprint(
            candidate_id=candidate_id,
            status_to=status_to,
            reason=None,
            comment=None,
            principal_type="system",
            principal_id="bot_test1_flow",
            source_ref=source_ref,
        ),
        principal_type="system",
        principal_id="bot_test1_flow",
        source_ref=source_ref,
    )


def _resolve_screening_application_anchor_sync(
    sync_session,
    *,
    candidate_id: int,
    correlation_id: str,
) -> tuple[int, int | None]:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    resolver = PrimaryApplicationResolver(
        SqlAlchemyApplicationResolverRepository(sync_session, uow=uow)
    )
    with uow.begin():
        resolution = resolver.ensure_application_for_candidate(
            candidate_id,
            ResolverContext(
                producer_family="bot_test1_screening",
                source_system="bot",
                source_ref="bot:test1:screening_anchor",
                candidate_id=candidate_id,
                actor_type="system",
                actor_id="bot_test1_flow",
                correlation_id=correlation_id,
                allow_create=True,
                require_application_anchor=True,
            ),
        )
        if resolution.status not in {ResolutionStatus.RESOLVED, ResolutionStatus.CREATED}:
            raise RuntimeError(
                "bot test1 screening could not resolve a primary application"
            )
        if resolution.application_id is None:
            raise RuntimeError("bot test1 screening returned no application id")
        return resolution.application_id, resolution.requisition_id


def _publish_test1_screening_events_sync(
    sync_session,
    *,
    candidate_id: int,
    application_id: int,
    requisition_id: int | None,
    test_result: TestResult,
    decision: ScreeningDecisionResult,
    correlation_id: str,
    base_idempotency_key: str,
) -> None:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    publisher = ApplicationEventPublisher(
        SqlAlchemyApplicationEventRepository(sync_session, uow=uow)
    )
    base_metadata = {
        "test_kind": "test1",
        "test_result_id": int(test_result.id),
        "decision_outcome": decision.outcome.value,
        "reason_code": decision.reason_code,
        "required_next_action": decision.required_next_action.value,
        "strictness": decision.strictness.value,
        "screening_payload": dict(decision.event_payload),
    }
    with uow.begin():
        publisher.publish_application_event(
            ApplicationEventCommand(
                producer_family="bot_test1_screening",
                idempotency_key=f"{base_idempotency_key}:assessment.completed",
                event_type=ApplicationEventType.ASSESSMENT_COMPLETED.value,
                candidate_id=candidate_id,
                source_system="bot",
                source_ref="bot:test1:assessment_completed",
                correlation_id=correlation_id,
                actor_type="system",
                actor_id="bot_test1_flow",
                application_id=application_id,
                requisition_id=requisition_id,
                channel="telegram",
                metadata_json=base_metadata,
            )
        )
        publisher.publish_application_event(
            ApplicationEventCommand(
                producer_family="bot_test1_screening",
                idempotency_key=f"{base_idempotency_key}:screening.decision_made",
                event_type=ApplicationEventType.SCREENING_DECISION_MADE.value,
                candidate_id=candidate_id,
                source_system="bot",
                source_ref="bot:test1:screening_decision",
                correlation_id=correlation_id,
                actor_type="system",
                actor_id="bot_test1_flow",
                application_id=application_id,
                requisition_id=requisition_id,
                channel="telegram",
                metadata_json=base_metadata,
            )
        )


async def _apply_test1_screening_statuses(
    *,
    candidate: User,
    decision: ScreeningDecisionResult,
    test_result: TestResult,
) -> tuple[int | None, int | None]:
    from backend.apps.admin_ui.services.candidates.application_dual_write import (
        claim_candidate_status_transition,
        finalize_candidate_status_dual_write,
    )

    if not get_settings().candidate_status_dual_write_enabled:
        await set_status_test1_completed(candidate.telegram_id)
        if decision.outcome == ScreeningDecisionOutcome.INVITE_TO_INTERVIEW:
            await set_status_waiting_slot(candidate.telegram_id)
        return None, None

    correlation_id = f"bot-test1-{candidate.id}-{test_result.id}"
    base_idempotency_key = f"bot-test1-{candidate.id}-{test_result.id}"

    async with async_session() as session:
        async with session.begin():
            user = await session.scalar(
                select(User).where(User.id == candidate.id).with_for_update()
            )
            if user is None:
                raise RuntimeError("candidate not found for bot test1 screening status update")

            application_id: int | None = None
            requisition_id: int | None = None

            async def _transition(target_status: CandidateStatus, *, source_ref: str) -> None:
                nonlocal application_id, requisition_id
                current_status = getattr(getattr(user, "candidate_status", None), "value", None)
                if current_status == target_status.value:
                    return
                request = _build_test1_status_dual_write_request(
                    candidate_id=int(user.id),
                    status_from=current_status,
                    status_to=target_status,
                    source_ref=source_ref,
                    correlation_id=correlation_id,
                    base_idempotency_key=base_idempotency_key,
                )
                claim = await claim_candidate_status_transition(session, request)
                if claim.reused:
                    return
                await apply_candidate_status(
                    user,
                    target_status,
                    session=session,
                    force=True,
                    actor_type="system",
                    actor_id=None,
                    reason="bot test1 screening",
                )
                result = await finalize_candidate_status_dual_write(
                    session,
                    candidate_id=int(user.id),
                    status_from=current_status,
                    status_to=target_status.value,
                    reason=None,
                    comment=None,
                    request=request,
                )
                application_id = result.application_id
                requisition_id = result.requisition_id

            await _transition(
                CandidateStatus.TEST1_COMPLETED,
                source_ref="bot:test1:test1_completed",
            )
            if decision.outcome == ScreeningDecisionOutcome.INVITE_TO_INTERVIEW:
                await _transition(
                    CandidateStatus.WAITING_SLOT,
                    source_ref="bot:test1:waiting_slot",
                )

            if application_id is None:
                application_id, requisition_id = await session.run_sync(
                    _resolve_screening_application_anchor_sync,
                    candidate_id=int(user.id),
                    correlation_id=correlation_id,
                )

            await session.run_sync(
                _publish_test1_screening_events_sync,
                candidate_id=int(user.id),
                application_id=application_id,
                requisition_id=requisition_id,
                test_result=test_result,
                decision=decision,
                correlation_id=correlation_id,
                base_idempotency_key=base_idempotency_key,
            )

            return application_id, requisition_id


async def _persist_test1_completion_and_screening(
    *,
    user_id: int,
    state: Dict[str, Any],
    sequence: List[Dict[str, Any]],
    answers: Dict[str, Any],
    screening_enabled: bool,
) -> Test1CompletionScreeningResult:
    fio = state.get("fio") or f"TG {user_id}"
    city_name = state.get("city_name") or ""
    username = state.get("username") or None
    candidate = await candidate_services.create_or_update_user(
        telegram_id=user_id,
        fio=fio,
        city=city_name,
        username=username,
    )
    draft_payload = dict(state.get("test1_payload") or {})
    if state.get("fio") is not None:
        draft_payload.setdefault("fio", state.get("fio"))
    if state.get("city_id") is not None:
        draft_payload["city_id"] = state.get("city_id")
    if state.get("city_name") is not None:
        draft_payload["city_name"] = state.get("city_name")
    draft_payload["candidate_tz"] = state.get("candidate_tz") or DEFAULT_TZ
    for key in (
        "age",
        "status",
        "format_choice",
        "study_mode",
        "study_schedule",
        "study_flex",
    ):
        if state.get(key) is not None:
            draft_payload[key] = state.get(key)

    draft_state = Test1DraftState(
        answers={str(key): str(value) for key, value in dict(answers or {}).items()},
        payload=draft_payload,
        question_ids=[_ensure_question_id(question, idx) for idx, question in enumerate(sequence)],
        city_id=state.get("city_id"),
        city_name=state.get("city_name"),
        candidate_tz=str(state.get("candidate_tz") or DEFAULT_TZ),
    )

    async with async_session() as session:
        async with session.begin():
            candidate_record = await session.scalar(
                select(User).where(User.id == int(candidate.id)).with_for_update()
            )
            if candidate_record is None:
                raise RuntimeError("candidate not found for bot Test1 completion")

            journey_session = await session.scalar(
                select(CandidateJourneySession)
                .where(
                    CandidateJourneySession.candidate_id == int(candidate.id),
                    CandidateJourneySession.entry_channel == "telegram",
                )
                .order_by(CandidateJourneySession.id.desc())
                .limit(1)
                .with_for_update()
            )
            if journey_session is None:
                journey_session = CandidateJourneySession(
                    candidate_id=int(candidate.id),
                    entry_channel="telegram",
                    current_step_key=TEST1_STEP_KEY,
                    last_surface="telegram_bot",
                    last_auth_method="telegram_bot",
                )
                session.add(journey_session)
                await session.flush()

            journey_session.current_step_key = TEST1_STEP_KEY
            journey_session.last_surface = "telegram_bot"
            journey_session.last_auth_method = "telegram_bot"

            step_state = await session.scalar(
                select(CandidateJourneyStepState)
                .where(
                    CandidateJourneyStepState.session_id == int(journey_session.id),
                    CandidateJourneyStepState.step_key == TEST1_STEP_KEY,
                )
                .limit(1)
                .with_for_update()
            )
            if step_state is None:
                step_state = CandidateJourneyStepState(
                    session_id=int(journey_session.id),
                    step_key=TEST1_STEP_KEY,
                    step_type="form",
                )
                session.add(step_state)
                await session.flush()

            step_state.payload_json = serialize_step_payload(
                draft_state=draft_state,
                source="bot",
                surface="telegram_bot",
            )
            step_state.status = "in_progress"
            step_state.completed_at = None

            shared_completion = await complete_test1_for_candidate(
                session=session,
                candidate=candidate_record,
                journey_session=journey_session,
                step_state=step_state,
                source="bot",
                channel="telegram",
                surface="telegram_bot",
                actor_type="system",
                actor_id="bot_test1_flow",
            )

    if not screening_enabled and candidate.telegram_id is not None:
        try:
            await set_status_waiting_slot(candidate.telegram_id)
        except Exception:
            logger.exception(
                "Failed to preserve legacy waiting_slot status for user %s",
                candidate.telegram_id,
            )

    persisted_candidate = await candidate_services.get_user_by_telegram_id(user_id)
    if persisted_candidate is None:
        persisted_candidate = candidate

    return Test1CompletionScreeningResult(
        candidate=persisted_candidate,
        screening_decision=shared_completion.screening_decision,
        interview_offer=shared_completion.interview_offer,
        required_next_action=shared_completion.required_next_action,
        current_step_key=shared_completion.current_step_key,
    )


async def _mark_test1_question_answered(user_id: int, summary: str) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state:
        return
    prompt_id = state.get("t1_last_prompt_id")
    if not prompt_id:
        return
    base_text = state.get("t1_last_question_text") or ""
    updated = f"{base_text}\n\n✅ <i>{html.escape(summary)}</i>"
    try:
        await bot.edit_message_text(updated, chat_id=user_id, message_id=prompt_id)
    except TelegramBadRequest:
        pass

    def _cleanup(st: State) -> Tuple[State, None]:
        st["t1_last_prompt_id"] = None
        st["t1_last_question_text"] = ""
        st["t1_requires_free_text"] = False
        return st, None

    await state_manager.atomic_update(user_id, _cleanup)


def _recruiter_header(name: str, tz_label: str) -> str:
    return (
        f"👤 <b>{name}</b>\n"
        f"🕒 Время отображается в вашем поясе: <b>{tz_label}</b>.\n"
        "Выберите удобное окно:"
    )


async def save_test1_answer(
    user_id: int,
    question: Dict[str, Any],
    answer: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> Test1AnswerResult:
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    current_idx = int(state.get("t1_current_idx", state.get("t1_idx", 0)) or 0)
    qid = _ensure_question_id(question, current_idx)
    meta = metadata or {}
    payload_data: Dict[str, Any] = dict(state.get("test1_payload") or {})
    answer_clean = answer.strip()

    city_info = None
    should_insert_flex = False

    if qid != "city":
        matched_option, option_hints = _match_question_option_value(question, answer_clean)
        if matched_option is None:
            return Test1AnswerResult(
                status="invalid",
                message="Выберите один из вариантов в списке.",
                hints=option_hints,
            )
        answer_clean = matched_option

    if qid == "fio":
        payload_data["fio"] = answer_clean
    elif qid == "city":
        city_info = await _resolve_candidate_city(answer_clean, meta)
        if city_info is None:
            city_names = [city.name for city in await list_candidate_cities()][:5]
            return Test1AnswerResult(
                status="invalid",
                message="Пока работаем в указанных городах. Выберите подходящий вариант из списка.",
                hints=city_names,
            )
        payload_data["city_id"] = city_info.id
        payload_data["city_name"] = city_info.name
    elif qid == "age":
        try:
            payload_data["age"] = convert_age(answer_clean)
        except ValueError as exc:
            return Test1AnswerResult(
                status="invalid",
                message=str(exc),
                hints=["Например: 23", "Возраст указываем цифрами"],
            )
    elif qid == "status":
        payload_data["status"] = answer_clean
    elif qid == "format":
        payload_data["format_choice"] = answer_clean
    elif qid == FOLLOWUP_STUDY_MODE["id"]:
        payload_data["study_mode"] = answer_clean
    elif qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
        payload_data["study_schedule"] = answer_clean
    elif qid == FOLLOWUP_STUDY_FLEX["id"]:
        payload_data["study_flex"] = answer_clean

    try:
        validated_model = apply_partial_validation(payload_data)
    except ValidationError as exc:
        message, hints = _validation_feedback(qid, exc)
        return Test1AnswerResult(status="invalid", message=message, hints=hints)

    if qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
        should_insert_flex = _should_insert_study_flex(validated_model, answer_clean)

    def _apply(state: State) -> Tuple[State, Dict[str, Any]]:
        working = state
        answers = working.setdefault("test1_answers", {})
        sequence = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence
        _ensure_question_id(question, current_idx)

        if qid == "fio":
            working["fio"] = validated_model.fio or answer_clean
        elif qid == "city" and city_info is not None:
            working["city_name"] = city_info.name
            working["city_id"] = city_info.id
            working["candidate_tz"] = city_info.tz or DEFAULT_TZ
            answers[qid] = city_info.name
        elif qid == "age":
            answers[qid] = str(payload_data.get("age", answer_clean))
        elif qid == "status":
            answers[qid] = answer_clean
            insert_pos = current_idx + 1
            existing_ids = {item.get("id") for item in sequence}

            lowered = answer_clean.lower()
            if "работ" in lowered:
                if FOLLOWUP_NOTICE_PERIOD["id"] not in existing_ids:
                    sequence.insert(insert_pos, FOLLOWUP_NOTICE_PERIOD.copy())
                    existing_ids.add(FOLLOWUP_NOTICE_PERIOD["id"])
                    insert_pos += 1
            elif "уч" in lowered:
                if FOLLOWUP_STUDY_MODE["id"] not in existing_ids:
                    sequence.insert(insert_pos, FOLLOWUP_STUDY_MODE.copy())
                    existing_ids.add(FOLLOWUP_STUDY_MODE["id"])
                    insert_pos += 1
                if FOLLOWUP_STUDY_SCHEDULE["id"] not in existing_ids:
                    sequence.insert(insert_pos, FOLLOWUP_STUDY_SCHEDULE.copy())
                    existing_ids.add(FOLLOWUP_STUDY_SCHEDULE["id"])
        else:
            if qid:
                answers[qid] = answer_clean

        if qid == FOLLOWUP_STUDY_MODE["id"]:
            answers[qid] = answer_clean
        if qid == FOLLOWUP_STUDY_SCHEDULE["id"]:
            answers[qid] = answer_clean
            if should_insert_flex:
                existing_ids = {item.get("id") for item in sequence}
                if FOLLOWUP_STUDY_FLEX["id"] not in existing_ids:
                    sequence.insert(current_idx + 1, FOLLOWUP_STUDY_FLEX.copy())
        if qid == FOLLOWUP_STUDY_FLEX["id"]:
            answers[qid] = answer_clean

        working["test1_answers"] = answers
        working["test1_payload"] = validated_model.model_dump(exclude_none=True)

        if qid == "city" and city_info is not None:
            working.setdefault("candidate_tz", city_info.tz or DEFAULT_TZ)

        if validated_model.format_choice is not None:
            working["format_choice"] = validated_model.format_choice
        if validated_model.study_mode is not None:
            working["study_mode"] = validated_model.study_mode
        if validated_model.study_schedule is not None:
            working["study_schedule"] = validated_model.study_schedule
        if validated_model.study_flex is not None:
            working["study_flex"] = validated_model.study_flex

        return working, {
            "city_id": working.get("city_id"),
            "city_name": working.get("city_name"),
        }

    update_info = await state_manager.atomic_update(user_id, _apply)

    branch = _determine_test1_branch(qid, answer_clean, validated_model)
    if branch is not None:
        if not branch.template_key:
            branch.template_key = REJECTION_TEMPLATES.get(branch.reason or "", "")
        if "city_name" not in branch.template_context and update_info.get("city_name"):
            branch.template_context["city_name"] = update_info.get("city_name")
        if validated_model.fio and "fio" not in branch.template_context:
            branch.template_context["fio"] = validated_model.fio
        if update_info.get("city_id") is not None:
            branch.template_context.setdefault("city_id", update_info.get("city_id"))
        return branch

    return Test1AnswerResult(status="ok")


async def handle_test1_answer(message: Message) -> None:
    user_id = message.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state or state.get("flow") != "interview":
        return

    try:
        if await candidate_services.is_chat_mode_active(user_id):
            logger.info(
                "Chat mode active; skipping questionnaire response",
                extra={"user_id": user_id},
            )
            return
    except Exception:  # pragma: no cover - conversation mode failures shouldn't break flow
        logger.debug("Failed to check conversation mode for %s", user_id, exc_info=True)

    # Update username if available (for existing users)
    username = getattr(message.from_user, "username", None)
    if username and state.get("username") != username:
        def _update_username(st: State) -> Tuple[State, None]:
            st["username"] = username
            return st, None
        await state_manager.atomic_update(user_id, _update_username)

    idx = state.get("t1_current_idx", state.get("t1_idx", 0))
    sequence = state.get("t1_sequence") or list(TEST1_QUESTIONS)
    total = len(sequence)
    if idx >= total:
        return

    question = sequence[idx]
    _ensure_question_id(question, idx)
    if not state.get("t1_requires_free_text", True):
        # Разрешаем текстовый ответ даже если ранее ожидались кнопки
        def _allow_text(st: State) -> Tuple[State, None]:
            st["t1_requires_free_text"] = True
            return st, None
        await state_manager.atomic_update(user_id, _allow_text)

    answer_text = (message.text or message.caption or "").strip()
    if not answer_text:
        if not state.get("t1_last_hint_sent"):
            await message.reply(
                "Нажмите «Ответить» на сообщение с вопросом или напишите текст, чтобы зафиксировать ответ."
            )

            def _mark_hint_sent(st: State) -> Tuple[State, None]:
                st["t1_last_hint_sent"] = True
                return st, None

            await state_manager.atomic_update(user_id, _mark_hint_sent)
        return

    result = await save_test1_answer(user_id, question, answer_text)

    if result.status == "invalid":
        feedback = _format_validation_feedback(result)
        await message.reply(feedback)
        return

    updated_state = await state_manager.get(user_id) or {}

    if result.status == "reject":
        await _handle_test1_rejection(user_id, result)
        return

    followup_text = await _resolve_followup_message(result, updated_state)
    if followup_text:
        await message.answer(followup_text)

    await _mark_test1_question_answered(user_id, _shorten_answer(answer_text))

    def _advance(st: State) -> Tuple[State, Dict[str, int]]:
        working = st
        sequence_local = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence_local
        current = int(working.get("t1_current_idx", working.get("t1_idx", 0)) or 0)
        if current != idx:
            return working, {"advanced": 0, "total": len(sequence_local)}
        next_idx = idx + 1
        working["t1_idx"] = next_idx
        return working, {"advanced": 1, "total": len(sequence_local), "next_idx": next_idx}

    advance_info = await state_manager.atomic_update(user_id, _advance)
    if not advance_info.get("advanced"):
        return

    next_idx = advance_info.get("next_idx", idx + 1)
    total = advance_info.get("total", len(sequence))
    if next_idx >= total:
        await finalize_test1(user_id)
    else:
        await send_test1_question(user_id)


async def handle_test1_option(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state or state.get("flow") != "interview":
        await callback.answer("Сценарий неактивен", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    _, idx_s, opt_idx_s = parts
    try:
        idx = int(idx_s)
        opt_idx = int(opt_idx_s)
    except ValueError:
        await callback.answer()
        return

    current_idx = state.get("t1_current_idx", state.get("t1_idx", 0))
    if idx != current_idx:
        await callback.answer("Вопрос уже пройден", show_alert=True)
        return

    sequence = state.get("t1_sequence") or list(TEST1_QUESTIONS)
    if idx >= len(sequence):
        await callback.answer("Вопрос недоступен", show_alert=True)
        return

    question = sequence[idx]
    options = question.get("options") or []
    if opt_idx < 0 or opt_idx >= len(options):
        await callback.answer("Вариант недоступен", show_alert=True)
        return

    option_meta = options[opt_idx]
    label = _extract_option_label(option_meta)
    value = _extract_option_value(option_meta)

    metadata = option_meta if isinstance(option_meta, dict) else None

    result = await save_test1_answer(user_id, question, value, metadata=metadata)

    if result.status == "invalid":
        short_msg = result.message or "Проверьте ответ"
        await callback.answer(short_msg[:150], show_alert=True)
        feedback = _format_validation_feedback(result)
        await callback.message.answer(feedback)
        return

    updated_state = await state_manager.get(user_id) or {}

    if result.status == "reject":
        await _handle_test1_rejection(user_id, result)
        return

    followup_text = await _resolve_followup_message(result, updated_state)
    if followup_text:
        await callback.message.answer(followup_text)

    await _mark_test1_question_answered(user_id, label)

    def _advance(st: State) -> Tuple[State, Dict[str, int]]:
        working = st
        sequence_local = list(working.get("t1_sequence") or TEST1_QUESTIONS)
        working["t1_sequence"] = sequence_local
        current = int(working.get("t1_current_idx", working.get("t1_idx", 0)) or 0)
        if current != idx:
            return working, {"advanced": 0, "total": len(sequence_local)}
        next_idx = idx + 1
        working["t1_idx"] = next_idx
        return working, {"advanced": 1, "total": len(sequence_local), "next_idx": next_idx}

    advance_info = await state_manager.atomic_update(user_id, _advance)

    await callback.answer(f"Выбрано: {label}")

    if not advance_info.get("advanced"):
        return

    next_idx = advance_info.get("next_idx", idx + 1)
    total = advance_info.get("total", len(sequence))
    if next_idx >= total:
        await finalize_test1(user_id)
    else:
        await send_test1_question(user_id)


async def finalize_test1(user_id: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    settings = get_settings()
    state = await state_manager.get(user_id) or {}
    sequence = state.get("t1_sequence", list(TEST1_QUESTIONS))
    answers = state.get("test1_answers") or {}
    lines = [
        "📋 Анкета кандидата (Тест 1)",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        f"TG ID: {user_id}",
        f"ФИО: {state.get('fio') or '—'}",
        f"Город: {state.get('city_name') or '—'}",
        "",
        "Ответы:",
    ]
    for idx, q in enumerate(sequence):
        qid = _ensure_question_id(q, idx)
        lines.append(f"- {q.get('prompt')}\n  {answers.get(qid, '—')}")

    report_content = "\n".join(lines)
    fname = TEST1_DIR / f"test1_{(state.get('fio') or user_id)}.txt"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(report_content)
    except Exception:
        logger.warning(
            "test1.report_write_failed",
            extra={"user_id": user_id, "filename": str(fname)},
            exc_info=True,
        )

    if not state.get("t1_notified"):
        shared = await _share_test1_with_recruiters(user_id, state, fname)

        if shared:
            def _mark_shared(st: State) -> Tuple[State, None]:
                st["t1_notified"] = True
                return st, None

            await state_manager.atomic_update(user_id, _mark_shared)

    done_text = await _render_tpl(state.get("city_id"), "t1_done")
    manual_prompt_sent = False
    offer_menu_presented = False
    screening_enabled = settings.test1_screening_decision_enabled
    auto_offer_enabled = settings.auto_interview_offer_after_test1_enabled

    candidate = None
    screening_decision = None
    try:
        completion = await _persist_test1_completion_and_screening(
            user_id=user_id,
            state=state,
            sequence=sequence,
            answers=answers,
            screening_enabled=screening_enabled,
        )
        candidate = completion.candidate
        screening_decision = completion.screening_decision
        screening_outcome = getattr(screening_decision, "outcome", None)
        if not isinstance(screening_outcome, ScreeningDecisionOutcome):
            raw_outcome = screening_outcome if isinstance(screening_outcome, str) else None
            if raw_outcome is None and isinstance(screening_decision, dict):
                raw_outcome = str(screening_decision.get("outcome") or "")
            try:
                screening_outcome = ScreeningDecisionOutcome(str(raw_outcome or ""))
            except ValueError:
                screening_outcome = None

        if screening_decision is None:
            status_updated = True
            if candidate.city:
                city_record = await find_city_by_plain_name(candidate.city)
                if city_record and not await city_has_available_slots(city_record.id):
                    if status_updated:
                        try:
                            candidate_name = state.get("fio") or f"User {candidate.telegram_id}"
                            city_name = state.get("city_name") or candidate.city
                            await notify_recruiters_waiting_slot(
                                user_id=candidate.telegram_id,
                                candidate_name=candidate_name,
                                city_name=city_name,
                                city_id=city_record.id,
                            )
                        except Exception:
                            logger.exception(
                                "Failed to notify recruiters about waiting_slot for candidate %s",
                                candidate.telegram_id
                            )
                        try:
                            manual_prompt_sent = await send_manual_scheduling_prompt(
                                candidate.telegram_id,
                                notice=done_text,
                            )
                        except Exception:
                            logger.exception(
                                "Failed to prompt candidate %s for manual schedule window",
                                candidate.telegram_id,
                            )
        elif screening_outcome == ScreeningDecisionOutcome.INVITE_TO_INTERVIEW:
            if not auto_offer_enabled:
                status_updated = True
                if candidate.city:
                    city_record = await find_city_by_plain_name(candidate.city)
                    if city_record and not await city_has_available_slots(city_record.id):
                        if status_updated:
                            try:
                                candidate_name = state.get("fio") or f"User {candidate.telegram_id}"
                                city_name = state.get("city_name") or candidate.city
                                await notify_recruiters_waiting_slot(
                                    user_id=candidate.telegram_id,
                                    candidate_name=candidate_name,
                                    city_name=city_name,
                                    city_id=city_record.id,
                                )
                            except Exception:
                                logger.exception(
                                    "Failed to notify recruiters about waiting_slot for candidate %s",
                                    candidate.telegram_id
                                )
                            try:
                                manual_prompt_sent = await send_manual_scheduling_prompt(
                                    candidate.telegram_id,
                                    notice=done_text,
                                )
                            except Exception:
                                logger.exception(
                                    "Failed to prompt candidate %s for manual schedule window",
                                    candidate.telegram_id,
                                )
            else:
                interview_offer = dict(completion.interview_offer or {})
                if (
                    str(interview_offer.get("mode") or "") == InterviewOfferMode.FALLBACK.value
                    or not list(interview_offer.get("options") or [])
                ):
                    if candidate.city:
                        city_record = await find_city_by_plain_name(candidate.city)
                        if city_record is not None:
                            try:
                                candidate_name = state.get("fio") or f"User {candidate.telegram_id}"
                                city_name = state.get("city_name") or candidate.city
                                await notify_recruiters_waiting_slot(
                                    user_id=candidate.telegram_id,
                                    candidate_name=candidate_name,
                                    city_name=city_name,
                                    city_id=city_record.id,
                                )
                            except Exception:
                                logger.exception(
                                    "Failed to notify recruiters about waiting_slot for candidate %s",
                                    candidate.telegram_id
                                )
                    manual_prompt_sent = await send_manual_scheduling_prompt(
                        candidate.telegram_id,
                        notice=done_text,
                    )
                else:
                    combined_text = _screening_followup_text(
                        done_text=done_text,
                        decision=screening_decision,
                    )
                    if combined_text:
                        await bot.send_message(candidate.telegram_id, combined_text)
                    await bot.send_message(
                        candidate.telegram_id,
                        _render_interview_offer_payload_message(
                            offer_payload=interview_offer,
                            candidate_tz=state.get("candidate_tz") or DEFAULT_TZ,
                        ),
                    )
                    try:
                        offer_menu_presented = await show_recruiter_menu(candidate.telegram_id)
                    except Exception:
                        logger.exception(
                            "Failed to present recruiter menu after auto-offer for user %s",
                            candidate.telegram_id,
                        )
        else:
            followup_text = _screening_followup_text(
                done_text=done_text,
                decision=screening_decision,
            )
            if followup_text:
                await bot.send_message(candidate.telegram_id, followup_text)

        try:
            report_dir = REPORTS_DIR / str(candidate.id)
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "test1.txt"
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(report_content)
            rel_path = str(Path("reports") / str(candidate.id) / "test1.txt")
            await candidate_services.update_candidate_reports(candidate.id, test1_path=rel_path)
        except Exception:
            logger.exception("Failed to persist Test 1 report for candidate %s", candidate.id)
    except Exception:  # pragma: no cover - auxiliary sync must not break flow
        logger.exception("Failed to persist candidate profile for Test1")

    should_show_legacy_menu = (
        screening_decision is None
        or getattr(screening_decision, "outcome", None) == ScreeningDecisionOutcome.INVITE_TO_INTERVIEW
        or (
            isinstance(screening_decision, dict)
            and screening_decision.get("outcome") == ScreeningDecisionOutcome.INVITE_TO_INTERVIEW.value
        )
    )
    if should_show_legacy_menu and not manual_prompt_sent and not offer_menu_presented:
        try:
            await show_recruiter_menu(user_id, notice=done_text)
        except Exception:
            logger.exception("Failed to present recruiter menu after Test 1 completion")

    await record_test1_completion()
    try:
        candidate_for_event = candidate
        if candidate_for_event is None:
            candidate_for_event = await candidate_services.get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST1_COMPLETED,
            user_id=user_id,
            candidate_id=candidate_for_event.id if candidate_for_event else None,
            metadata={"result": "passed"},
        )
    except Exception:
        logger.exception("Failed to log TEST1_COMPLETED for user %s", user_id)

    def _reset(st: State) -> Tuple[State, None]:
        st["t1_idx"] = None
        st["t1_last_prompt_id"] = None
        st["t1_last_question_text"] = ""
        st["t1_requires_free_text"] = False
        return st, None

    await state_manager.atomic_update(user_id, _reset)

__all__ = [
    'Test1AnswerResult',
    '_extract_option_label',
    '_extract_option_value',
    '_mark_test1_question_answered',
    '_shorten_answer',
    'finalize_test1',
    'handle_test1_answer',
    'handle_test1_option',
    'save_test1_answer',
    'send_test1_question',
]
