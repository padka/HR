"""Recruiter broadcast helpers."""

from . import base as _base

for _name in dir(_base):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)

async def _share_test1_with_recruiters(user_id: int, state: State, form_path: Path) -> bool:
    city_id = state.get("city_id")
    try:
        recruiters = await get_active_recruiters_for_city(city_id) if city_id else []
    except Exception:
        recruiters = []

    recipients: List[Any] = []
    seen_chats: set[Any] = set()
    for rec in recruiters:
        chat_id = getattr(rec, "tg_chat_id", None)
        if not chat_id:
            continue
        if chat_id in seen_chats:
            continue
        recipients.append(rec)
        seen_chats.add(chat_id)
    if not recipients:
        return False

    bot = get_bot()
    candidate_name = escape_html(state.get("fio") or str(user_id))
    city_name = escape_html(state.get("city_name") or "—")
    caption = (
        "📋 <b>Кандидат прошел Тест 1, но не выбрал время собеседования</b>\n"
        f"👤 {candidate_name}\n"
        f"📍 {city_name}\n"
        f"TG: {user_id}\n\n"
        "⚠️ <b>Требуется связаться вручную</b> для назначения собеседования."
    )

    attachments = [
        form_path,
        REPORTS_DIR / f"report_{state.get('fio') or user_id}.txt",
    ]

    delivered = False
    for recruiter in recipients:
        sent = False
        for path in attachments:
            if not path.exists():
                continue
            try:
                await bot.send_document(
                    recruiter.tg_chat_id,
                    FSInputFile(str(path)),
                    caption=caption,
                )
                sent = True
                delivered = True
                break
            except Exception:
                logger.exception(
                    "Failed to deliver Test 1 attachment to recruiter %s", recruiter.id
                )
        if sent:
            continue
        try:
            await bot.send_message(recruiter.tg_chat_id, caption)
            delivered = True
        except Exception:
            logger.exception(
                "Failed to send Test 1 summary to recruiter %s", recruiter.id
            )
    return delivered


async def notify_recruiters_waiting_slot(user_id: int, candidate_name: str, city_name: str, city_id: Optional[int]) -> bool:
    """Notify recruiters when a candidate is waiting for a manual slot assignment.

    Args:
        user_id: Telegram ID of the candidate
        candidate_name: Full name of the candidate
        city_name: Name of the city
        city_id: ID of the city (for finding responsible recruiters)

    Returns:
        True if at least one recruiter was notified
    """
    try:
        recruiters = await get_active_recruiters_for_city(city_id) if city_id else []
    except Exception:
        logger.exception("Failed to get active recruiters for city %s", city_id)
        recruiters = []

    if not recruiters:
        logger.warning("No active recruiters found for city %s (candidate %s waiting)", city_id, user_id)
        return False

    # Deduplicate recruiters by chat_id
    recipients: List[Any] = []
    seen_chats: set[Any] = set()
    for rec in recruiters:
        chat_id = getattr(rec, "tg_chat_id", None)
        if not chat_id or chat_id in seen_chats:
            continue
        recipients.append(rec)
        seen_chats.add(chat_id)

    if not recipients:
        logger.warning("No recruiters with chat_id found for city %s", city_id)
        return False

    bot = get_bot()
    message = (
        "⏳ <b>Кандидат ждёт назначения слота</b>\n\n"
        f"👤 {escape_html(candidate_name)}\n"
        f"📍 {escape_html(city_name)}\n"
        f"TG: <code>{user_id}</code>\n\n"
        "⚠️ <b>Нет доступных автоматических слотов</b>\n"
        "Требуется ручное назначение времени собеседования."
    )

    # Build action keyboard with CRM deep link
    reply_markup = None
    try:
        candidate_record = await candidate_services.get_user_by_telegram_id(user_id)
        if candidate_record is not None:
            settings = get_settings()
            crm_base = ((settings.crm_public_url or settings.bot_backend_url) or "").rstrip("/")
            crm_url = f"{crm_base}/app/candidates/{candidate_record.id}" if crm_base else ""
            from ..keyboards import kb_candidate_notification
            reply_markup = kb_candidate_notification(candidate_record.id, crm_url)
    except Exception:
        logger.debug("Could not build candidate notification keyboard", exc_info=True)

    delivered = False
    for recruiter in recipients:
        try:
            await bot.send_message(
                recruiter.tg_chat_id, message, parse_mode="HTML", reply_markup=reply_markup,
            )
            delivered = True
            logger.info(
                "Sent waiting_slot notification to recruiter %s (chat_id=%s) for candidate %s",
                recruiter.id,
                recruiter.tg_chat_id,
                user_id,
            )
        except Exception:
            logger.exception(
                "Failed to send waiting_slot notification to recruiter %s", recruiter.id
            )

    return delivered

async def notify_recruiters_manual_availability(
    *,
    candidate_tg_id: Optional[int],
    candidate_name: str,
    city_name: str,
    city_id: int,
    availability_window: Optional[str],
    availability_note: str,
    candidate_db_id: Optional[int] = None,
    responsible_recruiter_id: Optional[int] = None,
    source_channel: str = "telegram",
    candidate_external_id: Optional[str] = None,
) -> bool:
    """Notify recruiters that a candidate provided/updated manual availability.

    This is used when there are no auto slots or when a candidate requests a
    reschedule and proposes a new time window. Best effort: failures should not
    break the candidate flow.
    """

    if not city_id:
        return False

    recipients: List[Any] = []
    seen_chats: set[Any] = set()

    if responsible_recruiter_id:
        try:
            responsible = await get_recruiter(int(responsible_recruiter_id))
        except Exception:
            responsible = None
        chat_id = getattr(responsible, "tg_chat_id", None) if responsible else None
        if chat_id:
            recipients = [responsible]
            seen_chats.add(chat_id)

    if not recipients:
        try:
            recruiters = await get_active_recruiters_for_city(int(city_id))
        except Exception:
            recruiters = []
        for rec in recruiters:
            chat_id = getattr(rec, "tg_chat_id", None)
            if not chat_id or chat_id in seen_chats:
                continue
            recipients.append(rec)
            seen_chats.add(chat_id)

    if not recipients:
        return False

    crm_link = None
    try:
        settings = get_settings()
        public_base = (settings.crm_public_url or settings.bot_backend_url or "").rstrip("/")
        if candidate_db_id and public_base:
            crm_link = f"{public_base}/app/candidates/{int(candidate_db_id)}"
    except Exception:
        crm_link = None

    lines = [
        "🕒 <b>Кандидат указал удобное время</b>",
        "",
        f"👤 {escape_html(str(candidate_name))}",
        f"📍 {escape_html(str(city_name))}",
    ]
    if availability_window:
        lines.append(f"🗓 {escape_html(str(availability_window))}")
    if availability_note:
        lines.append(f"💬 {escape_html(str(availability_note))}")
    channel_label = str(source_channel or "telegram").strip().upper()
    if candidate_external_id:
        lines.append(f"{escape_html(channel_label)}: <code>{escape_html(str(candidate_external_id))}</code>")
    elif candidate_tg_id is not None:
        lines.append(f"TG: <code>{candidate_tg_id}</code>")
    message = "\n".join(lines)

    # Build inline keyboard with action buttons and CRM deep link
    reply_markup = None
    if candidate_db_id:
        try:
            from ..keyboards import kb_candidate_notification
            reply_markup = kb_candidate_notification(int(candidate_db_id), crm_link or "")
        except Exception:
            logger.debug("Could not build manual availability keyboard", exc_info=True)

    delivered = False
    bot = get_bot()
    for recruiter in recipients:
        chat_id = getattr(recruiter, "tg_chat_id", None)
        if not chat_id:
            continue

        sent = False
        report_paths: List[Path] = []
        if candidate_tg_id is not None:
            try:
                db_user = await candidate_services.get_user_by_telegram_id(candidate_tg_id)
                if db_user is not None:
                    report_paths = _candidate_report_paths(db_user)
            except Exception:
                report_paths = []

        if report_paths and hasattr(bot, "send_document"):
            for path in report_paths[:1]:  # send the most useful one (Test 1) to avoid spam
                try:
                    await bot.send_document(chat_id, FSInputFile(str(path)), caption=message, parse_mode="HTML", reply_markup=reply_markup)
                    sent = True
                    delivered = True
                    break
                except Exception:
                    logger.exception(
                        "Failed to deliver manual availability attachment to recruiter %s",
                        getattr(recruiter, "id", None),
                    )

        if sent:
            continue

        try:
            await bot.send_message(chat_id, message, parse_mode="HTML", reply_markup=reply_markup)
            delivered = True
        except Exception:
            logger.exception(
                "Failed to send manual availability notification to recruiter %s",
                getattr(recruiter, "id", None),
            )

    return delivered

__all__ = [
    '_share_test1_with_recruiters',
    'notify_recruiters_manual_availability',
    'notify_recruiters_waiting_slot',
]
