from typing import List, Dict

from backend.domain.template_stages import CITY_TEMPLATE_STAGES, STAGE_DEFAULTS
from backend.apps.bot.defaults import DEFAULT_TEMPLATES

STAGE_KEYS: List[str] = [stage.key for stage in CITY_TEMPLATE_STAGES]

PRESET_LABELS = {
    "intro_day_invitation": "Приглашение на ознакомительный день",
    "intro_day_reminder": "Напоминание об ОД (за 3 часа)",
    "approved_msg": "Встреча подтверждена",
    "result_fail": "Отказ (общий)",
    "t1_intro": "Тест 1: Приветствие",
    "t1_done": "Тест 1: Завершение",
    "t2_intro": "Тест 2: Приветствие",
    "t2_result": "Тест 2: Результат",
    "slot_proposal_candidate": "Предложение слота (кандидату)",
    "slot_confirmed_recruiter": "Слот подтвержден (рекрутеру)",
    "reschedule_requested_recruiter": "Запрос переноса (рекрутеру)",
    "reschedule_approved_candidate": "Перенос одобрен (кандидату)",
    "reschedule_declined_candidate": "Перенос отклонен (кандидату)",
    "manual_schedule_prompt": "Запрос ручного выбора времени",
    "choose_recruiter": "Выбор рекрутера",
    "reminder_2h": "Напоминание за 2ч",
    "reminder_30m": "Напоминание за 30мин",
    "confirm_6h": "Запрос подтверждения (за 6ч)",
    "confirm_2h": "Запрос подтверждения (за 2ч)",
}

def list_known_template_keys() -> List[str]:
    """Return all template keys known to the runtime and admin UI."""
    keys = set(STAGE_KEYS)
    keys.update(DEFAULT_TEMPLATES.keys())
    return sorted(keys)

def known_template_presets() -> List[Dict[str, str]]:
    """Return default texts and labels for known template keys."""
    presets: Dict[str, str] = {}
    presets.update(DEFAULT_TEMPLATES)

    for stage in CITY_TEMPLATE_STAGES:
        presets[stage.key] = stage.default_text

    result: List[Dict[str, str]] = []
    stage_map = {s.key: s.title for s in CITY_TEMPLATE_STAGES}
    
    for key, text in presets.items():
        label = stage_map.get(key) or PRESET_LABELS.get(key) or key
        result.append({
            "key": key,
            "label": label,
            "text": text,
        })

    result.sort(key=lambda x: x["label"])
    return result
