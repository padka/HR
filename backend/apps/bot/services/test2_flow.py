"""Test 2 flow services."""

from . import base as _base

for _name in dir(_base):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)

async def set_pending_test2(candidate_id: int, context: Dict[str, object]) -> None:
    state_manager = get_state_manager()

    def _update(state: State) -> Tuple[State, None]:
        pending = dict(state.get("pending_test2") or {})
        pending.update(context)
        state["pending_test2"] = pending
        return state, None

    await state_manager.atomic_update(candidate_id, _update)


async def dispatch_interview_success(event: InterviewSuccessEvent) -> None:
    importlib.import_module("backend.apps.bot.handlers.interview")

    if not _interview_success_handlers:
        logger.warning("No interview success handlers registered; skipping dispatch.")
        return

    errors: List[BaseException] = []
    for handler in list(_interview_success_handlers):
        try:
            await handler(event)
        except Exception as exc:  # pragma: no cover - handler safety net
            logger.exception(
                "Interview success handler %r failed",
                handler,
                extra={"candidate_id": event.candidate_id},
            )
            errors.append(exc)

    if errors:
        raise errors[0]


async def _begin_test2_flow(
    candidate_id: int,
    candidate_tz: str,
    candidate_city_id: Optional[int],
    candidate_name: str,
    previous_state: Optional[Dict[str, object]] = None,
) -> None:
    state_manager = get_state_manager()
    base_state = previous_state or (await state_manager.get(candidate_id) or {})

    sequence = base_state.get("t1_sequence")
    if sequence:
        try:
            sequence = list(sequence)
        except TypeError:
            sequence = list(TEST1_QUESTIONS)
    else:
        sequence = list(TEST1_QUESTIONS)

    new_state: Dict[str, object] = {
        "flow": "intro",
        "t1_idx": None,
        "t1_current_idx": None,
        "test1_answers": base_state.get("test1_answers", {}),
        "t1_last_prompt_id": None,
        "t1_last_question_text": "",
        "t1_requires_free_text": False,
        "t1_sequence": sequence,
        "fio": base_state.get("fio", candidate_name or ""),
        "city_name": base_state.get("city_name", ""),
        "city_id": base_state.get("city_id", candidate_city_id),
        "candidate_tz": candidate_tz,
        "t2_attempts": {},
        "picked_recruiter_id": None,
        "picked_slot_id": None,
    }

    await state_manager.set(candidate_id, new_state)
    await start_test2(candidate_id)


async def launch_test2(candidate_id: int) -> None:
    state_manager = get_state_manager()
    previous_state = await state_manager.get(candidate_id) or {}
    pending: Dict[str, Any] = dict(previous_state.get("pending_test2") or {})

    if not pending and previous_state.get("flow") == "intro":
        return

    candidate_tz = pending.get("candidate_tz") or previous_state.get("candidate_tz") or DEFAULT_TZ
    candidate_city_id = pending.get("candidate_city_id") or previous_state.get("city_id")
    candidate_name = pending.get("candidate_name") or previous_state.get("fio") or ""

    def _clear(state: State) -> Tuple[State, None]:
        state.pop("pending_test2", None)
        return state, None

    await state_manager.atomic_update(candidate_id, _clear)
    await _begin_test2_flow(
        candidate_id,
        candidate_tz,
        candidate_city_id,
        candidate_name,
        previous_state=previous_state,
    )

async def start_test2(user_id: int) -> None:
    # Refresh questions so admin changes are reflected without restart.
    refresh_questions_bank()
    questions_version = get_questions_bank_version()

    bot = get_bot()
    state_manager = get_state_manager()

    def _init_attempts(state: State) -> Tuple[State, Dict[str, Optional[int]]]:
        state["questions_bank_version"] = questions_version
        state["t2_attempts"] = {
            q_index: {"answers": [], "is_correct": False, "start_time": None}
            for q_index in range(len(TEST2_QUESTIONS))
        }
        return state, {"city_id": state.get("city_id")}

    ctx = await state_manager.atomic_update(user_id, _init_attempts)
    try:
        candidate = await candidate_services.get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST2_STARTED,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={"channel": "telegram"},
        )
    except Exception:
        logger.exception("Failed to log TEST2_STARTED for user %s", user_id)
    intro = await _render_tpl(
        ctx.get("city_id"),
        "t2_intro",
        qcount=len(TEST2_QUESTIONS),
        timelimit=TIME_LIMIT // 60,
        attempts=MAX_ATTEMPTS,
    )
    await bot.send_message(user_id, intro)
    await send_test2_question(user_id, 0)


async def send_test2_question(user_id: int, q_index: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()

    def _mark_start(state: State) -> Tuple[State, None]:
        attempts = state.setdefault("t2_attempts", {})
        attempt = attempts.setdefault(
            q_index, {"answers": [], "is_correct": False, "start_time": None}
        )
        attempt["start_time"] = datetime.now(timezone.utc)
        return state, None

    await state_manager.atomic_update(user_id, _mark_start)
    question = TEST2_QUESTIONS[q_index]
    txt = (
        f"🔹 <b>Вопрос {q_index + 1}/{len(TEST2_QUESTIONS)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{question['text']}"
    )
    await bot.send_message(
        user_id, txt, reply_markup=create_keyboard(question["options"], q_index)
    )


async def handle_test2_answer(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    state_manager = get_state_manager()
    state = await state_manager.get(user_id)
    if not state or "t2_attempts" not in state or state.get("flow") != "intro":
        await callback.answer()
        return

    try:
        _, qidx_s, ans_s = callback.data.split("_")
        q_index = int(qidx_s)
        answer_index = int(ans_s)
    except ValueError:
        await callback.answer()
        return

    question = TEST2_QUESTIONS[q_index]

    now = datetime.now(timezone.utc)
    correct_answer = question.get("correct")

    def _apply(state: State) -> Tuple[State, Dict[str, Any]]:
        attempts = state.get("t2_attempts")
        if not isinstance(attempts, dict):
            return state, {"skip": True}
        attempt = attempts.get(q_index)
        if attempt is None:
            attempt = {"answers": [], "is_correct": False, "start_time": None}
            attempts[q_index] = attempt

        answers = attempt.setdefault("answers", [])
        start_time = attempt.get("start_time")
        time_spent = (now - start_time).seconds if isinstance(start_time, datetime) else 0
        overtime = time_spent > TIME_LIMIT

        answers.append(
            {"answer": answer_index, "time": now.isoformat(), "overtime": overtime}
        )
        is_correct = answer_index == correct_answer
        attempt["is_correct"] = is_correct

        attempts_left = MAX_ATTEMPTS - len(answers)
        if attempts_left < 0:
            attempts_left = 0

        return state, {
            "skip": False,
            "is_correct": is_correct,
            "answers_count": len(answers),
            "attempts_left": attempts_left,
            "overtime": overtime,
        }

    result = await state_manager.atomic_update(user_id, _apply)
    if result.get("skip"):
        await callback.answer()
        return

    is_correct = bool(result.get("is_correct"))
    attempts_left = int(result.get("attempts_left", 0))
    overtime = bool(result.get("overtime"))
    answers_count = int(result.get("answers_count", 0))

    feedback = question.get("feedback")
    if isinstance(feedback, list):
        feedback_message = feedback[answer_index]
    else:
        feedback_message = feedback if is_correct else "❌ <i>Неверно.</i>"

    if is_correct:
        final_feedback = f"{feedback_message}"
        if overtime:
            final_feedback += "\n⏰ <i>Превышено время</i>"
        if answers_count > 1:
            penalty = 10 * (answers_count - 1)
            final_feedback += f"\n⚠️ <i>Попыток: {answers_count} (-{penalty}%)</i>"
        await callback.message.edit_text(final_feedback)

        if q_index < len(TEST2_QUESTIONS) - 1:
            await send_test2_question(user_id, q_index + 1)
        else:
            await finalize_test2(user_id)
    else:
        final_feedback = f"{feedback_message}"
        if attempts_left > 0:
            final_feedback += f"\nОсталось попыток: {attempts_left}"
            await callback.message.edit_text(
                final_feedback,
                reply_markup=create_keyboard(question["options"], q_index),
            )
        else:
            final_feedback += "\n🚫 <i>Лимит попыток исчерпан</i>"
            await callback.message.edit_text(final_feedback)
            if q_index < len(TEST2_QUESTIONS) - 1:
                await send_test2_question(user_id, q_index + 1)
            else:
                await finalize_test2(user_id)


async def finalize_test2(user_id: int) -> None:
    bot = get_bot()
    state_manager = get_state_manager()
    state = await state_manager.get(user_id) or {}
    attempts = state.get("t2_attempts", {})
    correct_answers = sum(1 for attempt in attempts.values() if attempt["is_correct"])
    score = calculate_score(attempts)
    rating = get_rating(score)

    fio = state.get("fio") or f"TG {user_id}"
    city_name = state.get("city_name") or ""
    username = state.get("username") or None

    candidate = None
    try:
        existing = await candidate_services.get_user_by_telegram_id(user_id)
        if existing is None:
            candidate = await candidate_services.create_or_update_user(
                telegram_id=user_id,
                fio=fio,
                city=city_name,
                username=username,
            )
        else:
            candidate = await candidate_services.create_or_update_user(
                telegram_id=user_id,
                fio=fio,
                city=city_name,
                username=username,
            )
    except Exception:
        logger.exception("Failed to ensure candidate profile before Test 2 report")
        candidate = None

    question_data: List[dict] = []
    report_lines = [
        "📋 Отчёт по Тесту 2",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        f"TG ID: {user_id}",
        f"ФИО: {fio}",
        f"Город: {city_name or '—'}",
        f"Баллы: {score} ({correct_answers}/{len(TEST2_QUESTIONS)} верных)",
        f"Рейтинг: {rating}",
        "",
        "Вопросы:",
    ]

    for idx, question in enumerate(TEST2_QUESTIONS, start=1):
        options = question.get("options") or []
        attempt = attempts.get(idx - 1, {})
        answers_seq = attempt.get("answers", [])
        attempts_count = len(answers_seq)
        user_answer_idx = answers_seq[-1].get("answer") if answers_seq else None
        if isinstance(user_answer_idx, int) and 0 <= user_answer_idx < len(options):
            user_answer_text = options[user_answer_idx]
        else:
            user_answer_text = "—"
        correct_idx = question.get("correct")
        if isinstance(correct_idx, int) and 0 <= correct_idx < len(options):
            correct_text = options[correct_idx]
        else:
            correct_text = "—"
        overtime = any(entry.get("overtime") for entry in answers_seq)
        question_data.append(
            {
                "question_index": idx,
                "question_text": question.get("text", ""),
                "correct_answer": correct_text,
                "user_answer": user_answer_text,
                "attempts_count": attempts_count,
                "time_spent": 0,
                "is_correct": bool(attempt.get("is_correct")),
                "overtime": overtime,
            }
        )
        report_lines.append(f"{idx}. {question.get('text', '')}")
        report_lines.append(f"   Ответ кандидата: {user_answer_text}")
        report_lines.append(
            f"   Правильный ответ: {correct_text} {'✅' if attempt.get('is_correct') else '❌'}"
        )
        report_lines.append(
            f"   Попыток: {attempts_count} · Просрочено: {'да' if overtime else 'нет'}"
        )
        report_lines.append("")

    report_content = "\n".join(report_lines)

    if candidate is not None:
        try:
            await candidate_services.save_test_result(
                user_id=candidate.id,
                raw_score=correct_answers,
                final_score=score,
                rating="TEST2",
                total_time=int(state.get("test2_duration") or 0),
                question_data=question_data,
                source="bot",
            )
        except Exception:
            logger.exception("Failed to persist Test 2 result for candidate %s", candidate.id)

        try:
            report_dir = REPORTS_DIR / str(candidate.id)
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "test2.txt"
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(report_content)
            rel_path = str(Path("reports") / str(candidate.id) / "test2.txt")
            await candidate_services.update_candidate_reports(
                candidate.id,
                test2_path=rel_path,
            )
        except Exception:
            logger.exception("Failed to persist Test 2 report for candidate %s", candidate.id)

    result_text = await _render_tpl(
        state.get("city_id"),
        "t2_result",
        correct=correct_answers,
        score=score,
        rating=rating,
    )
    await bot.send_message(user_id, result_text)
    pct = correct_answers / max(1, len(TEST2_QUESTIONS))
    try:
        result_flag = "failed" if pct < PASS_THRESHOLD else "passed"
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST2_COMPLETED,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={
                "result": result_flag,
                "score": score,
                "correct": correct_answers,
                "total": len(TEST2_QUESTIONS),
            },
        )
    except Exception:
        logger.exception("Failed to log TEST2_COMPLETED for user %s", user_id)
    if pct < PASS_THRESHOLD:
        provider = get_template_provider()
        candidate_name = (candidate.fio if candidate else "") or str(user_id)
        ctx = {"candidate_name": candidate_name, "candidate_fio": candidate_name}
        rendered = await provider.render(
            "candidate_rejection", 
            ctx, 
            city_id=state.get("city_id")
        )
        if rendered:
            await bot.send_message(user_id, rendered.text)

        # Update candidate status to TEST2_FAILED
        try:
            from backend.domain.candidates.status_service import set_status_test2_failed
            await set_status_test2_failed(user_id)
        except Exception:
            logger.exception("Failed to update candidate status to TEST2_FAILED for user %s", user_id)

        await state_manager.delete(user_id)
        return

    final_notice = await _render_tpl(state.get("city_id"), "slot_sent")
    if not final_notice:
        final_notice = "Заявка отправлена. Ожидайте подтверждения."
    await bot.send_message(user_id, final_notice)

    # Update candidate status to TEST2_COMPLETED
    try:
        from backend.domain.candidates.status_service import set_status_test2_completed
        await set_status_test2_completed(user_id, force=True)
    except Exception:
        logger.exception("Failed to update candidate status to TEST2_COMPLETED for user %s", user_id)

def get_rating(score: float) -> str:
    if score >= 6.5:
        return "⭐⭐⭐⭐⭐ "
    if score >= 5:
        return "⭐⭐⭐⭐ "
    if score >= 3.5:
        return "⭐⭐⭐ "
    if score >= 2:
        return "⭐⭐ "
    return "⭐ (Не рекомендован)"

__all__ = [
    'dispatch_interview_success',
    'finalize_test2',
    'get_rating',
    'handle_test2_answer',
    'launch_test2',
    'send_test2_question',
    'set_pending_test2',
    'start_test2',
]
