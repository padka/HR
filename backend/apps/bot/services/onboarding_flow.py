"""Onboarding and recruiter entry flow services."""

from backend.core.db import async_session
from backend.domain.candidates.models import User

from . import base as _base

for _name in dir(_base):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)

from .test1_flow import send_test1_question
from .test2_flow import start_test2


async def _send_active_candidate_summary(user_id: int, *, candidate: User) -> None:
    async with async_session() as session:
        async with session.begin():
            stored_candidate = await session.get(User, int(candidate.id))
            if stored_candidate is None:
                await get_bot().send_message(
                    user_id,
                    "Мы нашли ваш профиль, но не смогли восстановить текущий этап. Попросите рекрутера отправить следующий шаг заново.",
                )
                return
    lines = [
        "У вас уже есть активность в системе. Повторно проходить Test 1 не нужно.",
        f"Статус: {stored_candidate.status or 'В работе'}",
        "Продолжайте текущий путь кандидата в этом чате.",
    ]
    lines.append("Если нужно продолжение, рекрутер отправит следующий шаг прямо в Telegram.")
    await get_bot().send_message(user_id, "\n".join(lines))

async def begin_interview(user_id: int, username: Optional[str] = None) -> None:
    # Ensure we use the freshest question set after admin edits.
    refresh_questions_bank()
    questions_version = get_questions_bank_version()

    state_manager = get_state_manager()
    bot = get_bot()

    # If this chat belongs to a recruiter, switch to recruiter-facing mode
    try:
        recruiter = await get_recruiter_by_chat_id(user_id)
    except Exception:
        recruiter = None

    if recruiter is not None:
        await state_manager.set(
            user_id,
            State(
                flow="recruiter",
                questions_bank_version=questions_version,
                t1_idx=None,
                test1_answers={},
                t1_last_prompt_id=None,
                t1_last_question_text="",
                t1_requires_free_text=False,
                t1_sequence=list(TEST1_QUESTIONS),
                fio=recruiter.name or "",
                city_name="",
                city_id=None,
                candidate_tz=recruiter.tz or DEFAULT_TZ,
                t2_attempts={},
                picked_recruiter_id=None,
                picked_slot_id=None,
                test1_payload={},
                username=username or "",
                t1_last_hint_sent=False,
            ),
        )
        await show_recruiter_dashboard(user_id, recruiter=recruiter)
        return

    try:
        await candidate_services.set_conversation_mode(user_id, "flow")
    except Exception:  # pragma: no cover - best effort
        logger.debug("Failed to reset conversation mode for %s", user_id, exc_info=True)
    existing_candidate = await candidate_services.get_user_by_telegram_id(user_id)
    if existing_candidate is not None:
        await _send_active_candidate_summary(user_id, candidate=existing_candidate)
        return
    await state_manager.set(
        user_id,
        State(
            flow="interview",
            questions_bank_version=questions_version,
            t1_idx=0,
            test1_answers={},
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=True,
            t1_sequence=list(TEST1_QUESTIONS),
            fio="",
            city_name="",
            city_id=None,
            candidate_tz=DEFAULT_TZ,
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload={},
            username=username or "",  # Save username for later use
            t1_last_hint_sent=False,
        ),
    )
    try:
        candidate = await candidate_services.get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST1_STARTED,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={"channel": "telegram"},
        )
    except Exception:
        logger.exception("Failed to log TEST1_STARTED for user %s", user_id)
    intro = await _render_tpl(None, "t1_intro")
    if not (intro or "").strip():
        from backend.apps.bot.defaults import DEFAULT_TEMPLATES
        intro = DEFAULT_TEMPLATES.get("t1_intro", "").strip() or "Начнём анкету."
    await bot.send_message(user_id, intro)
    await send_test1_question(user_id)


async def show_recruiter_dashboard(user_id: int, recruiter: Optional[Recruiter] = None, horizon_hours: int = 48) -> None:
    """Send recruiter a compact dashboard of upcoming slots with KPI header."""
    bot = get_bot()
    if recruiter is None:
        recruiter = await get_recruiter_by_chat_id(user_id)
    if recruiter is None:
        await bot.send_message(
            user_id,
            "Ваш чат не привязан к рекрутёру. Используйте /iam <Имя из админки>, затем /start.",
        )
        return

    # Fetch KPI counts for the dashboard header
    waiting_count = 0
    try:
        from backend.apps.admin_ui.services.dashboard import dashboard_counts as _dashboard_counts
        from backend.apps.admin_ui.security import Principal

        principal = Principal(type="recruiter", id=recruiter.id)
        counts = await _dashboard_counts(principal=principal)
        waiting_count = int(counts.get("waiting_candidates_total", 0))
    except Exception:
        logger.debug("Could not load dashboard KPIs for recruiter %s", recruiter.id, exc_info=True)

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=horizon_hours)
    try:
        slots = await get_recruiter_agenda_by_chat_id(
            user_id, start_utc=now, end_utc=end, limit=30
        )
    except Exception:
        logger.exception("Failed to load recruiter agenda", extra={"chat_id": user_id})
        await bot.send_message(user_id, "Не удалось загрузить расписание. Попробуйте позже.")
        return

    # Build KPI header
    scheduled = sum(1 for s in (slots or []) if (s.status or "").lower() not in (SlotStatus.FREE, "free"))
    free = sum(1 for s in (slots or []) if (s.status or "").lower() in (SlotStatus.FREE, "free"))
    kpi_lines = [
        "📊 <b>Ваша панель</b>\n",
        f"• Встреч запланировано: {scheduled}",
        f"• Ожидают назначения: {waiting_count}",
        f"• Слотов свободно: {free}",
    ]

    if not slots:
        kpi_lines.append(f"\nБлижайшие {horizon_hours}ч — нет встреч.")
    else:
        kpi_lines.append(f"\n<b>Ближайшее:</b>")
        for slot in slots[:8]:
            status = (slot.status or "").lower()
            if status in (SlotStatus.FREE, "free"):
                continue
            purpose = "Ознакомительный день" if (slot.purpose or "").lower() == "intro_day" else "Собеседование"
            candidate_label = slot.candidate_fio or "—"
            tz = slot.tz_name or recruiter.tz or DEFAULT_TZ
            dt_local = fmt_dt_local(slot.start_utc, tz)
            kpi_lines.append(f"• {dt_local} · {purpose} · {candidate_label}")

    settings = get_settings()
    crm_base = ((settings.crm_public_url or settings.bot_backend_url) or "").rstrip("/")
    from ..keyboards import kb_recruiter_dashboard
    reply_markup = kb_recruiter_dashboard(waiting_count, crm_base) if crm_base else None

    await bot.send_message(
        user_id,
        "\n".join(kpi_lines),
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def send_welcome(user_id: int) -> None:
    bot = get_bot()
    text = (
        "👋 Добро пожаловать!\n"
        "Нажмите «Начать», чтобы заполнить мини-анкету и выбрать время для интервью."
    )
    await bot.send_message(user_id, text, reply_markup=kb_start())


async def handle_recruiter_identity_command(message: Message) -> None:
    """Process the `/iam` command sent by a recruiter."""

    text = (message.text or "").strip()
    _, _, args = text.partition(" ")
    name_hint = args.strip()
    if not name_hint:
        await message.answer("Используйте команду в формате: /iam <Имя>")
        return

    updated = await set_recruiter_chat_id_by_command(name_hint, chat_id=message.chat.id)
    if not updated:
        await message.answer(
            "Рекрутер не найден. Убедитесь, что имя совпадает с записью в системе."
        )
        return

    await message.answer(
        "Готово! Уведомления о брони и подтверждениях будут приходить в этот чат."
    )

    # Register bot commands for the recruiter chat
    try:
        from ..recruiter_service import set_recruiter_commands
        await set_recruiter_commands(message.chat.id)
    except Exception:
        logger.debug("Could not set recruiter commands after /iam", exc_info=True)


async def start_introday_flow(message: Message) -> None:
    # Ensure we use the freshest question set after admin edits.
    refresh_questions_bank()
    questions_version = get_questions_bank_version()

    state_manager = get_state_manager()
    user_id = message.from_user.id
    prev = await state_manager.get(user_id) or {}
    await state_manager.set(
        user_id,
        State(
            flow="intro",
            questions_bank_version=questions_version,
            t1_idx=None,
            test1_answers=prev.get("test1_answers", {}),
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=False,
            t1_sequence=prev.get("t1_sequence", list(TEST1_QUESTIONS)),
            fio=prev.get("fio", ""),
            city_name=prev.get("city_name", ""),
            city_id=prev.get("city_id"),
            candidate_tz=prev.get("candidate_tz", DEFAULT_TZ),
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload=prev.get("test1_payload", {}),
            format_choice=prev.get("format_choice"),
            study_mode=prev.get("study_mode"),
            study_schedule=prev.get("study_schedule"),
            study_flex=prev.get("study_flex"),
        ),
    )
    await start_test2(user_id)

async def handle_home_start(callback: CallbackQuery) -> None:
    await callback.answer()
    await begin_interview(callback.from_user.id)

__all__ = [
    'begin_interview',
    'handle_home_start',
    'handle_recruiter_identity_command',
    'send_welcome',
    'show_recruiter_dashboard',
    'start_introday_flow',
]
