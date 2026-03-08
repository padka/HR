"""Recruiter-facing Telegram bot services.

This module contains all new recruiter-facing business logic to keep it
separate from the 7500+ line services.py monolith.  It imports shared
helpers from services.py and domain services from admin_ui.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from backend.apps.admin_ui.services.bot_service import get_bot_service
from backend.apps.admin_ui.services.chat import send_chat_message
from backend.core.settings import get_settings

from .keyboards import fmt_dt_local
from .security import sign_callback_data, verify_callback_data
from .services import (
    escape_html,
    get_bot,
    get_recruiter_by_chat_id,
    get_state_manager,
    safe_edit_text_or_caption,
    safe_remove_reply_markup,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status code mapping for compact callback data (2-3 chars)
# ---------------------------------------------------------------------------

_STATUS_TO_CODE: Dict[str, str] = {
    "lead": "LD",
    "contacted": "CT",
    "invited": "IN",
    "test1_completed": "T1",
    "waiting_slot": "WS",
    "stalled_waiting_slot": "SW",
    "slot_pending": "SP",
    "interview_scheduled": "IS",
    "interview_confirmed": "IC",
    "interview_declined": "ID",
    "test2_sent": "T2S",
    "test2_completed": "T2C",
    "test2_failed": "T2F",
    "intro_day_scheduled": "IDS",
    "intro_day_confirmed_preliminary": "ICP",
    "intro_day_declined_invitation": "IDI",
    "intro_day_confirmed_day_of": "ICD",
    "intro_day_declined_day_of": "IDD",
    "hired": "HI",
    "not_hired": "NH",
}

_CODE_TO_STATUS: Dict[str, str] = {v: k for k, v in _STATUS_TO_CODE.items()}

# Recruiter state keys (prefixed to avoid collision with candidate state)
_RC_STATE_PREFIX = "rc:"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _crm_base_url() -> str:
    """Return the CRM base URL for deep links."""
    try:
        settings = get_settings()
        url = settings.crm_public_url or settings.bot_backend_url
        return url.rstrip("/") if url else ""
    except Exception:
        return ""


def _crm_candidate_url(candidate_id: int) -> str:
    """Build a CRM deep link to a candidate."""
    base = _crm_base_url()
    if not base:
        return ""
    return f"{base}/app/candidates/{candidate_id}"


async def _get_candidate_by_id(candidate_id: int, recruiter: Any) -> Any:
    """Fetch a recruiter-visible candidate by DB id."""
    from backend.apps.admin_ui.services.recruiter_access import get_candidate_for_recruiter

    return await get_candidate_for_recruiter(candidate_id, recruiter, detach=True)


# ---------------------------------------------------------------------------
# Callback dispatcher
# ---------------------------------------------------------------------------


async def handle_recruiter_callback(callback: CallbackQuery) -> None:
    """Dispatch recruiter candidate action callbacks (rc:* prefix)."""
    raw = callback.data or ""
    payload = verify_callback_data(raw, expected_prefix="rc:")
    if payload is None:
        await callback.answer("Ссылка устарела", show_alert=True)
        return

    # payload format: rc:{action}:{entity_id}[:{extra}]
    parts = payload.split(":")
    if len(parts) < 3:
        await callback.answer("Неверный формат", show_alert=True)
        return

    action = parts[1]
    try:
        entity_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Неверный формат", show_alert=True)
        return

    # Auth check
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка авторизации", show_alert=True)
        return

    recruiter = await get_recruiter_by_chat_id(user.id)
    if recruiter is None:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    if action == "inbox":
        await _show_inbox_via_callback(callback, recruiter)
    elif action == "st":
        await _show_status_transitions(callback, entity_id, recruiter)
    elif action == "ss":
        # rc:ss:{candidate_id}:{status_code}
        status_code = parts[3] if len(parts) > 3 else ""
        await _apply_status_change(callback, entity_id, status_code, recruiter)
    elif action == "mg":
        await _start_messaging(callback, entity_id, recruiter)
    else:
        await callback.answer("Действие пока недоступно", show_alert=True)


# ---------------------------------------------------------------------------
# /inbox — Incoming candidates
# ---------------------------------------------------------------------------


async def show_recruiter_inbox(user_id: int, recruiter: Any = None) -> None:
    """Show top waiting candidates to the recruiter (via /inbox command)."""
    bot = get_bot()

    if recruiter is None:
        recruiter = await get_recruiter_by_chat_id(user_id)
    if recruiter is None:
        await bot.send_message(
            user_id,
            "Ваш чат не привязан к рекрутёру. Используйте /iam <Имя из админки>.",
        )
        return

    try:
        from backend.apps.admin_ui.services.dashboard import get_waiting_candidates
        from backend.apps.admin_ui.security import Principal

        principal = Principal(type="recruiter", id=recruiter.id)
        candidates = await get_waiting_candidates(limit=5, principal=principal)
    except Exception:
        logger.exception("Failed to load waiting candidates", extra={"recruiter_id": recruiter.id})
        await bot.send_message(user_id, "Не удалось загрузить входящих. Попробуйте позже.")
        return

    if not candidates:
        await bot.send_message(user_id, "Нет ожидающих кандидатов ✅")
        return

    from .keyboards import kb_candidate_actions

    total = len(candidates)
    lines = [f"📥 <b>Входящие кандидаты ({total})</b>\n"]

    for i, c in enumerate(candidates[:5], 1):
        name = c.get("name", c.get("fio", "—"))
        city = c.get("city", "—")
        waiting = c.get("waiting_hours", 0)
        waiting_label = f"{int(waiting)}ч" if waiting else "—"
        lines.append(f"{i}. 👤 {escape_html(str(name))} · {escape_html(str(city))} · {waiting_label}")

    text = "\n".join(lines)

    crm_url = _crm_base_url()
    from .keyboards import kb_recruiter_dashboard
    kb = kb_recruiter_dashboard(total, crm_url) if crm_url else None

    await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=kb)


async def _show_inbox_via_callback(callback: CallbackQuery, recruiter: Any) -> None:
    """Show inbox triggered by callback button."""
    user = callback.from_user
    if not user:
        return
    await callback.answer()
    await show_recruiter_inbox(user.id, recruiter=recruiter)


# ---------------------------------------------------------------------------
# /find — Candidate search
# ---------------------------------------------------------------------------


async def search_candidates(user_id: int, query: str, recruiter: Any) -> None:
    """Search candidates by name/city and send results to the recruiter."""
    bot = get_bot()

    if not query.strip():
        await bot.send_message(user_id, "Использование: /find <имя или город>")
        return

    try:
        from backend.core.db import async_session
        from backend.domain.candidates.models import User
        from backend.domain.candidates.status import STATUS_LABELS, CandidateStatus
        from sqlalchemy import or_, select, func

        like_value = f"%{query.strip()}%"

        async with async_session() as session:
            q = select(User).where(
                or_(
                    User.fio.ilike(like_value),
                    User.city.ilike(like_value),
                ),
                User.is_active.is_(True),
            )
            # Scope to recruiter's candidates unless admin
            if getattr(recruiter, "is_admin", False) is not True:
                q = q.where(User.responsible_recruiter_id == recruiter.id)

            q = q.order_by(User.last_activity.desc()).limit(5)
            result = await session.execute(q)
            candidates = list(result.scalars().all())
            for c in candidates:
                session.expunge(c)

            # Get total count
            count_q = select(func.count(User.id)).where(
                or_(
                    User.fio.ilike(like_value),
                    User.city.ilike(like_value),
                ),
                User.is_active.is_(True),
            )
            if getattr(recruiter, "is_admin", False) is not True:
                count_q = count_q.where(User.responsible_recruiter_id == recruiter.id)
            total = await session.scalar(count_q) or 0
    except Exception:
        logger.exception("Failed to search candidates", extra={"recruiter_id": recruiter.id, "query": query})
        await bot.send_message(user_id, "Ошибка поиска. Попробуйте позже.")
        return

    if not candidates:
        await bot.send_message(
            user_id,
            f"По запросу «{escape_html(query)}» ничего не найдено.",
            parse_mode="HTML",
        )
        return

    from .keyboards import kb_candidate_actions

    lines = [f"🔍 <b>Результаты поиска</b> ({total})\n"]
    crm_base = _crm_base_url()

    for i, c in enumerate(candidates, 1):
        status_label = ""
        if c.candidate_status:
            try:
                status_label = STATUS_LABELS.get(c.candidate_status, str(c.candidate_status))
            except Exception:
                status_label = str(c.candidate_status) if c.candidate_status else ""
        city = c.city or "—"
        lines.append(
            f"{i}. 👤 {escape_html(c.fio)} · {escape_html(city)}"
            + (f" · {escape_html(status_label)}" if status_label else "")
        )

    if total > 5:
        crm_search_url = f"{crm_base}/app/candidates?search={query}" if crm_base else ""
        footer = f"\nПоказано 5 из {total}."
        if crm_search_url:
            footer += f" <a href='{escape_html(crm_search_url)}'>Все в CRM ↗</a>"
        lines.append(footer)

    text = "\n".join(lines)

    # Send individual messages per candidate with action buttons, or one summary
    # For simplicity: send one summary message. Per-candidate buttons would require
    # separate messages (Telegram limitation: one keyboard per message).
    # We send per-candidate messages for action buttons.
    await bot.send_message(user_id, text, parse_mode="HTML")

    # Send per-candidate action buttons (max 5)
    for c in candidates[:5]:
        crm_url = _crm_candidate_url(c.id)
        kb = kb_candidate_actions(c.id, crm_url)
        label = f"👤 {escape_html(c.fio)}"
        await bot.send_message(user_id, label, parse_mode="HTML", reply_markup=kb)


# ---------------------------------------------------------------------------
# Status change flow (two-step)
# ---------------------------------------------------------------------------


async def _show_status_transitions(callback: CallbackQuery, candidate_id: int, recruiter: Any) -> None:
    """Step 1: Show current status and allowed transitions as buttons."""
    candidate = await _get_candidate_by_id(candidate_id, recruiter)
    if candidate is None:
        await callback.answer("Кандидат не найден", show_alert=True)
        return

    from backend.domain.candidates.status import (
        STATUS_LABELS,
        CandidateStatus,
        get_next_statuses,
    )

    current = candidate.candidate_status
    current_label = STATUS_LABELS.get(current, "Нет статуса") if current else "Нет статуса"

    transitions = get_next_statuses(current)
    if not transitions:
        await callback.answer(f"Статус «{current_label}» — финальный", show_alert=True)
        return

    rows: List[List[InlineKeyboardButton]] = []
    for target_status, label in transitions:
        code = _STATUS_TO_CODE.get(target_status.value, target_status.value[:3].upper())
        cb_data = sign_callback_data(f"rc:ss:{candidate_id}:{code}")
        rows.append([InlineKeyboardButton(text=f"→ {label}", callback_data=cb_data)])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    text = (
        f"👤 {escape_html(candidate.fio)}\n"
        f"Текущий статус: <b>{escape_html(current_label)}</b>\n\n"
        "Выберите новый статус:"
    )
    await callback.answer()
    await get_bot().send_message(callback.from_user.id, text, parse_mode="HTML", reply_markup=kb)


async def _apply_status_change(
    callback: CallbackQuery,
    candidate_id: int,
    status_code: str,
    recruiter: Any,
) -> None:
    """Step 2: Apply the selected status transition."""
    target_slug = _CODE_TO_STATUS.get(status_code)
    if not target_slug:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    candidate = await _get_candidate_by_id(candidate_id, recruiter)
    if candidate is None:
        await callback.answer("Кандидат не найден", show_alert=True)
        return

    from backend.domain.candidate_status_service import (
        CandidateStatusService,
        CandidateStatusTransitionError,
    )
    from backend.domain.candidates.status import CandidateStatus, STATUS_LABELS

    try:
        target_status = CandidateStatus(target_slug)
    except ValueError:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    svc = CandidateStatusService()
    try:
        changed = await svc.advance(candidate, target_status)
    except CandidateStatusTransitionError as exc:
        await callback.answer(f"Ошибка: {exc}", show_alert=True)
        return

    if changed:
        # Persist the change
        from backend.core.db import async_session

        async with async_session() as session:
            await session.merge(candidate)
            await session.commit()

    new_label = STATUS_LABELS.get(target_status, target_slug)
    text = (
        f"✅ Статус обновлён\n\n"
        f"👤 {escape_html(candidate.fio)}\n"
        f"Новый статус: <b>{escape_html(new_label)}</b>"
    )
    await callback.answer("Статус обновлён")

    # Edit the status selection message to show result and remove keyboard
    try:
        if callback.message:
            await safe_edit_text_or_caption(callback.message, text)
            await safe_remove_reply_markup(callback.message)
    except Exception:
        logger.debug("Could not edit status change message", exc_info=True)
        await get_bot().send_message(callback.from_user.id, text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Free-text messaging to candidates
# ---------------------------------------------------------------------------


async def _start_messaging(callback: CallbackQuery, candidate_id: int, recruiter: Any) -> None:
    """Set recruiter state to capture next free-text message for a candidate."""
    candidate = await _get_candidate_by_id(candidate_id, recruiter)
    if candidate is None:
        await callback.answer("Кандидат не найден", show_alert=True)
        return

    if not candidate.telegram_id:
        await callback.answer("У кандидата нет Telegram", show_alert=True)
        return

    state_manager = get_state_manager()
    user_id = callback.from_user.id

    # Store messaging intent in recruiter state namespace
    rc_state = {
        "rc_awaiting_msg": True,
        "rc_target_id": candidate.id,
        "rc_target_tg_id": candidate.telegram_id,
        "rc_target_name": candidate.fio,
    }
    await state_manager.set(f"{_RC_STATE_PREFIX}{user_id}", rc_state)

    await callback.answer()
    text = f"✉️ Введите сообщение для <b>{escape_html(candidate.fio)}</b>:"
    await get_bot().send_message(callback.from_user.id, text, parse_mode="HTML")


async def handle_recruiter_free_text(user_id: int, text: str) -> bool:
    """Check if recruiter has pending message state and forward text to candidate.

    Returns True if the text was handled (recruiter was in messaging mode).
    """
    state_manager = get_state_manager()
    rc_key = f"{_RC_STATE_PREFIX}{user_id}"

    try:
        rc_state = await state_manager.get(rc_key)
    except Exception:
        return False

    if not rc_state or not isinstance(rc_state, dict) or not rc_state.get("rc_awaiting_msg"):
        return False

    target_tg_id = rc_state.get("rc_target_tg_id")
    target_id = rc_state.get("rc_target_id")
    target_name = rc_state.get("rc_target_name", "кандидат")

    if not target_tg_id and not target_id:
        await state_manager.delete(rc_key)
        return False

    # Clear state before sending to prevent double-sends
    await state_manager.delete(rc_key)

    bot = get_bot()
    try:
        if target_id:
            await send_chat_message(
                int(target_id),
                text=text,
                client_request_id=None,
                author_label="Рекрутер",
                bot_service=get_bot_service(),
            )
        else:
            await bot.send_message(int(target_tg_id), text)
    except Exception:
        logger.exception(
            "Failed to send recruiter message",
            extra={"candidate_id": target_id, "telegram_id": target_tg_id},
        )
        await bot.send_message(
            user_id,
            f"❌ Не удалось отправить сообщение для {escape_html(str(target_name))}.",
            parse_mode="HTML",
        )
        return True

    await bot.send_message(
        user_id,
        f"✅ Сообщение отправлено для <b>{escape_html(str(target_name))}</b>.",
        parse_mode="HTML",
    )
    return True


# ---------------------------------------------------------------------------
# Bot commands registration for recruiter chats
# ---------------------------------------------------------------------------


async def set_recruiter_commands(chat_id: int) -> None:
    """Set bot command menu for a recruiter chat."""
    from aiogram.types import BotCommand, BotCommandScopeChat

    bot = get_bot()
    commands = [
        BotCommand(command="admin", description="Расписание и KPI"),
        BotCommand(command="inbox", description="Входящие кандидаты"),
        BotCommand(command="find", description="Поиск кандидата"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=chat_id))
    except Exception:
        logger.debug("Could not set recruiter commands for chat %s", chat_id, exc_info=True)

    # Set Menu Button to open Mini App
    await set_recruiter_menu_button(chat_id)


async def set_recruiter_menu_button(chat_id: int) -> None:
    """Set the bot's menu button to open the recruiter Mini App."""
    from aiogram.types import MenuButtonWebApp, WebAppInfo

    base = _crm_base_url()
    if not base:
        logger.debug("No CRM base URL configured, skipping menu button for chat %s", chat_id)
        return

    bot = get_bot()
    webapp_url = f"{base}/tg-app"
    try:
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(
                text="📊 Панель",
                web_app=WebAppInfo(url=webapp_url),
            ),
        )
    except Exception:
        logger.debug("Could not set menu button for chat %s", chat_id, exc_info=True)


# ---------------------------------------------------------------------------
# Enhanced dashboard (delegates to existing)
# ---------------------------------------------------------------------------


async def show_enhanced_dashboard(user_id: int, recruiter: Any = None) -> None:
    """Enhanced /admin dashboard with KPI header and action buttons."""
    from .services import show_recruiter_dashboard
    await show_recruiter_dashboard(user_id, recruiter=recruiter)
