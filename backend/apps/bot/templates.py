"""Template helpers for bot messages."""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.domain.repositories import get_template
from backend.domain.template_stages import STAGE_DEFAULTS

DEFAULT_TEMPLATES: Dict[str, str] = {
    # Общие
    "choose_recruiter": (
        "👤 <b>Выбор рекрутёра</b>\n"
        "Нажмите на имя коллеги, чтобы увидеть доступные окна."
    ),
    "slot_taken": "Слот уже занят. Выберите другой:",
    "slot_sent": "Заявка отправлена. Ожидайте подтверждения.",
    "approved_msg": (
        "✅ <b>Встреча подтверждена</b>\n"
        "🗓 {dt}\n"
        "Ссылка/адрес придут после подтверждения явки за 2 часа."
    ),
    "confirm_2h": (
        "⏰ Напоминание: встреча (ознакомительный день) через 2 часа — {dt}.\n"
        "Пожалуйста, подтвердите участие. Ссылка придёт после подтверждения."
    ),
    "reminder_1h": "⏰ Напоминание: встреча (ознакомительный день) через час — {dt}.",
    "att_confirmed_link": "🔗 Ссылка на Яндекс.Телемост: {link}\nВстречаемся {dt}",
    "att_declined": "Понимаю. Давайте подберём другое время.",
    "result_fail": (
        "Спасибо за время! На текущем этапе мы не продолжаем процесс.\n"
        "Мы сохраним ваши контакты и свяжемся при появлении подходящих ролей."
    ),

    # Тест 1
    "t1_intro": (
        "✨ <b>SMART: мини-анкета</b>\n"
        "Ответьте, пожалуйста, на несколько вопросов — это займёт 2–3 минуты и поможет назначить интервью."
    ),
    "t1_progress": "<i>Вопрос {n}/{total}</i>",
    "t1_done": (
        "🎯 Спасибо! Анкета получена.\n"
        "Теперь выберите рекрутёра и время для короткого видео-интервью (15–20 минут)."
    ),

    # Тест 2
    "t2_intro": (
        "📘 <b>Ознакомительный тест</b>\n"
        "Вопросов: {qcount} • Лимит: {timelimit} мин/вопрос • Макс. попыток: {attempts}\n"
        "Учитываем скорость и число попыток."
    ),
    "t2_result": (
        "🎯 <b>Ваш результат</b>\n\n"
        "▫️ <b>Правильных ответов:</b> {correct}\n"
        "▫️ <b>Итоговый балл:</b> {score}\n"
        "▫️ <b>Уровень:</b> {rating}"
    ),

    # Выбор времени (после Теста 2)
    "no_slots": (
        "Пока нет свободных слотов у выбранного рекрутёра.\n"
        "Выберите другого специалиста или попробуйте позже."
    ),
}

DEFAULT_TEMPLATES.update(STAGE_DEFAULTS)

__all__ = ["DEFAULT_TEMPLATES", "tpl"]


async def _fetch_template(city_id: Optional[int], key: str) -> Optional[str]:
    """Return template text from DB (city specific or global)."""
    try:
        template = await get_template(city_id, key)
    except Exception:
        template = None
    if template is None:
        return None
    if isinstance(template, str):
        return template
    return getattr(template, "text", None) or getattr(template, "content", None)


async def tpl(city_id: Optional[int], key: str, **fmt: Any) -> str:
    text = await _fetch_template(city_id, key) or DEFAULT_TEMPLATES.get(key, "")
    if not fmt:
        return text
    try:
        return text.format(**fmt)
    except Exception:
        return text
