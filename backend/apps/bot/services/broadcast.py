"""Recruiter broadcast helpers."""

from pathlib import Path
from typing import Any

from . import base as _base

for _name in dir(_base):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)

FSInputFile = _base.FSInputFile
REPORTS_DIR = _base.REPORTS_DIR
State = _base.State
_candidate_report_paths = _base._candidate_report_paths
candidate_services = _base.candidate_services
escape_html = _base.escape_html
get_active_recruiters_for_city = _base.get_active_recruiters_for_city
get_bot = _base.get_bot
get_recruiter = _base.get_recruiter
get_settings = _base.get_settings
logger = _base.logger


def _channel_identity_line(
    *,
    source_channel: str,
    candidate_external_id: str | None,
    candidate_tg_id: int | None,
) -> str | None:
    channel_label = str(source_channel or "telegram").strip().upper()
    if candidate_external_id:
        return f"{escape_html(channel_label)}: <code>{escape_html(str(candidate_external_id))}</code>"
    if candidate_tg_id is not None:
        return f"TG: <code>{candidate_tg_id}</code>"
    return None


async def _resolve_recruiter_recipients(
    *,
    city_id: int | None,
    responsible_recruiter_id: int | None = None,
) -> list[Any]:
    recipients: list[Any] = []
    seen_chats: set[Any] = set()

    if responsible_recruiter_id:
        try:
            responsible = await get_recruiter(int(responsible_recruiter_id))
        except Exception:
            responsible = None
        chat_id = getattr(responsible, "tg_chat_id", None) if responsible else None
        if chat_id:
            recipients.append(responsible)
            seen_chats.add(chat_id)

    if not recipients and city_id:
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

    return recipients


def _candidate_notification_markup(candidate_db_id: int | None, crm_link: str | None) -> Any:
    if not candidate_db_id:
        return None
    try:
        from ..keyboards import kb_candidate_notification

        return kb_candidate_notification(int(candidate_db_id), crm_link or "")
    except Exception:
        logger.debug("Could not build candidate notification keyboard", exc_info=True)
        return None


def _candidate_crm_link(candidate_db_id: int | None) -> str | None:
    try:
        settings = get_settings()
        public_base = (settings.crm_public_url or settings.bot_backend_url or "").rstrip("/")
        if candidate_db_id and public_base:
            return f"{public_base}/app/candidates/{int(candidate_db_id)}"
    except Exception:
        return None
    return None

async def _share_test1_with_recruiters(user_id: int, state: State, form_path: Path) -> bool:
    city_id = state.get("city_id")
    try:
        recruiters = await get_active_recruiters_for_city(city_id) if city_id else []
    except Exception:
        recruiters = []

    recipients: list[Any] = []
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


async def notify_recruiters_waiting_slot(user_id: int, candidate_name: str, city_name: str, city_id: int | None) -> bool:
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
    recipients: list[Any] = []
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
    candidate_tg_id: int | None,
    candidate_name: str,
    city_name: str,
    city_id: int,
    availability_window: str | None,
    availability_note: str,
    candidate_db_id: int | None = None,
    responsible_recruiter_id: int | None = None,
    source_channel: str = "telegram",
    candidate_external_id: str | None = None,
) -> bool:
    """Notify recruiters that a candidate provided/updated manual availability.

    This is used when there are no auto slots or when a candidate requests a
    reschedule and proposes a new time window. Best effort: failures should not
    break the candidate flow.
    """

    if not city_id:
        return False

    recipients = await _resolve_recruiter_recipients(
        city_id=int(city_id),
        responsible_recruiter_id=responsible_recruiter_id,
    )

    if not recipients:
        return False

    crm_link = _candidate_crm_link(candidate_db_id)

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
    identity_line = _channel_identity_line(
        source_channel=source_channel,
        candidate_external_id=candidate_external_id,
        candidate_tg_id=candidate_tg_id,
    )
    if identity_line:
        lines.append(identity_line)
    message = "\n".join(lines)

    reply_markup = _candidate_notification_markup(candidate_db_id, crm_link)

    delivered = False
    bot = get_bot()
    for recruiter in recipients:
        chat_id = getattr(recruiter, "tg_chat_id", None)
        if not chat_id:
            continue

        sent = False
        report_paths: list[Path] = []
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


async def notify_recruiters_test1_completed(
    *,
    candidate_name: str,
    city_name: str,
    city_id: int | None,
    candidate_db_id: int | None = None,
    responsible_recruiter_id: int | None = None,
    source_channel: str = "telegram",
    candidate_external_id: str | None = None,
    candidate_tg_id: int | None = None,
    report_path: Path | None = None,
    screening_outcome_label: str | None = None,
) -> bool:
    recipients = await _resolve_recruiter_recipients(
        city_id=city_id,
        responsible_recruiter_id=responsible_recruiter_id,
    )
    if not recipients:
        return False

    crm_link = _candidate_crm_link(candidate_db_id)
    reply_markup = _candidate_notification_markup(candidate_db_id, crm_link)
    lines = [
        "📋 <b>Кандидат завершил Тест 1</b>",
        "",
        f"👤 {escape_html(str(candidate_name))}",
        f"📍 {escape_html(str(city_name or '—'))}",
    ]
    if screening_outcome_label:
        lines.append(f"🧭 {escape_html(str(screening_outcome_label))}")
    identity_line = _channel_identity_line(
        source_channel=source_channel,
        candidate_external_id=candidate_external_id,
        candidate_tg_id=candidate_tg_id,
    )
    if identity_line:
        lines.append(identity_line)
    message = "\n".join(lines)

    delivered = False
    bot = get_bot()
    for recruiter in recipients:
        chat_id = getattr(recruiter, "tg_chat_id", None)
        if not chat_id:
            continue
        if report_path and report_path.exists():
            try:
                await bot.send_document(
                    chat_id,
                    FSInputFile(str(report_path)),
                    caption=message,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                delivered = True
                continue
            except Exception:
                logger.exception(
                    "Failed to deliver Test 1 attachment to recruiter %s",
                    getattr(recruiter, "id", None),
                )
        try:
            await bot.send_message(chat_id, message, parse_mode="HTML", reply_markup=reply_markup)
            delivered = True
        except Exception:
            logger.exception(
                "Failed to send Test 1 completion notification to recruiter %s",
                getattr(recruiter, "id", None),
            )
    return delivered


async def notify_recruiters_slot_selected(
    *,
    candidate_name: str,
    city_name: str,
    city_id: int | None,
    slot_start_local: str,
    recruiter_name: str | None,
    candidate_db_id: int | None = None,
    responsible_recruiter_id: int | None = None,
    source_channel: str = "telegram",
    candidate_external_id: str | None = None,
    candidate_tg_id: int | None = None,
) -> bool:
    recipients = await _resolve_recruiter_recipients(
        city_id=city_id,
        responsible_recruiter_id=responsible_recruiter_id,
    )
    if not recipients:
        return False
    crm_link = _candidate_crm_link(candidate_db_id)
    reply_markup = _candidate_notification_markup(candidate_db_id, crm_link)
    lines = [
        "🗓 <b>Кандидат выбрал слот собеседования</b>",
        "",
        f"👤 {escape_html(str(candidate_name))}",
        f"📍 {escape_html(str(city_name or '—'))}",
        f"⏰ {escape_html(str(slot_start_local))}",
    ]
    if recruiter_name:
        lines.append(f"👔 {escape_html(str(recruiter_name))}")
    identity_line = _channel_identity_line(
        source_channel=source_channel,
        candidate_external_id=candidate_external_id,
        candidate_tg_id=candidate_tg_id,
    )
    if identity_line:
        lines.append(identity_line)
    message = "\n".join(lines)

    delivered = False
    bot = get_bot()
    for recruiter in recipients:
        chat_id = getattr(recruiter, "tg_chat_id", None)
        if not chat_id:
            continue
        try:
            await bot.send_message(chat_id, message, parse_mode="HTML", reply_markup=reply_markup)
            delivered = True
        except Exception:
            logger.exception(
                "Failed to send slot selected notification to recruiter %s",
                getattr(recruiter, "id", None),
            )
    return delivered

__all__ = [
    '_share_test1_with_recruiters',
    'notify_recruiters_test1_completed',
    'notify_recruiters_slot_selected',
    'notify_recruiters_manual_availability',
    'notify_recruiters_waiting_slot',
]
