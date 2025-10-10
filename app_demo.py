"""FastAPI demo server with canned data for Liquid Glass previews."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from zoneinfo import ZoneInfo

from backend.domain.template_stages import CITY_TEMPLATE_STAGES, STAGE_DEFAULTS
STATIC_DIR = Path(__file__).parent / "backend" / "apps" / "admin_ui" / "static"
TEMPLATES_DIR = Path(__file__).parent / "backend" / "apps" / "admin_ui" / "templates"

app = FastAPI(title="HR Admin UI Demo", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

NOW_UTC = datetime.now(timezone.utc)


class AttrDict(dict):
    """Dictionary with attribute access retaining mapping methods."""

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as err:  # pragma: no cover - mirrors dict behaviour
            raise AttributeError(item) from err

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def __delattr__(self, key: str) -> None:
        del self[key]


def _ns(value: Any) -> Any:
    if isinstance(value, dict):
        return AttrDict({k: _ns(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_ns(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_ns(item) for item in value)
    return value


def build(value: Any) -> Any:
    return _ns(copy.deepcopy(value))


def fmt_utc(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M")


def fmt_local(dt: datetime | None, tz_name: str | None) -> str:
    if not dt or not tz_name:
        return "—"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # pragma: no cover - fallback for invalid tz
        return fmt_utc(dt)
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")


def tz_display(tz_name: str | None) -> str:
    if not tz_name:
        return "UTC±0"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # pragma: no cover
        return tz_name
    now_local = datetime.now(tz)
    offset = now_local.utcoffset() or timedelta()
    hours = int(offset.total_seconds() // 3600)
    minutes = int((abs(offset.total_seconds()) % 3600) // 60)
    sign = "+" if hours >= 0 else "-"
    return f"UTC{sign}{abs(hours):02d}:{minutes:02d} ({tz_name})"


def norm_status(value: str | None) -> str:
    if not value:
        return ""
    return value if isinstance(value, str) else str(value)


templates.env.globals.update(
    fmt_local=fmt_local,
    fmt_utc=fmt_utc,
    tz_display=tz_display,
    norm_status=norm_status,
)


# --- Demo data --------------------------------------------------------------

COUNTS_DATA = {
    "recruiters": 5,
    "cities": 8,
    "slots_total": 24,
    "slots_free": 8,
    "slots_pending": 5,
    "slots_booked": 9,
    "test1_total_seen": 156,
    "test1_rejections_total": 18,
    "test1_rejections_percent": 11.5,
    "test1_rejections_breakdown": {
        "Не пришёл на интервью": 7,
        "Не прошёл тест": 5,
        "Отказался": 6,
    },
}

BOT_STATUS_DATA = {
    "config_enabled": True,
    "runtime_enabled": True,
    "ready": True,
    "health": "ok",
    "mode": "production",
    "updated_at": fmt_utc(NOW_UTC - timedelta(minutes=12)),
}

ANALYTICS_DATA = {
    "total": 248,
    "active": 186,
    "inactive": 62,
    "upcoming_interviews": 14,
    "awaiting_confirmation": 4,
    "completed_interviews": 112,
    "tests_week": 46,
    "messages_week": 132,
    "need_followup": 8,
    "no_tests": 3,
    "pipeline": [
        {"slug": "new", "label": "Новые", "count": 32},
        {"slug": "interviews", "label": "Интервью", "count": 14},
        {"slug": "offers", "label": "Офферы", "count": 5},
        {"slug": None, "label": "Отклонено", "count": 9},
    ],
}

CANDIDATE_ROWS_DATA: List[Dict[str, Any]] = [
    {
        "user": {
            "id": 1,
            "fio": "Анна Смирнова",
            "telegram_id": 438201239,
            "city": "Москва",
            "is_active": True,
            "last_activity": NOW_UTC - timedelta(hours=2, minutes=15),
        },
        "stage": "Интервью",
        "latest_slot": {
            "status": "BOOKED",
            "start_utc": NOW_UTC + timedelta(days=1, hours=2),
            "candidate_tz": "Europe/Moscow",
        },
        "next_action": "Подтвердить участие",
        "tests_count": 4,
        "latest_result": {"final_score": 86, "raw_score": 100},
        "latest_message": {"message_text": "Мы назначили интервью на завтра в 15:00."},
    },
    {
        "user": {
            "id": 2,
            "fio": "Егор Кравцов",
            "telegram_id": 522118002,
            "city": "Санкт-Петербург",
            "is_active": False,
            "last_activity": NOW_UTC - timedelta(days=2, hours=4),
        },
        "stage": "Тест",
        "latest_slot": None,
        "next_action": "Напомнить о тесте",
        "tests_count": 1,
        "latest_result": None,
        "latest_message": None,
    },
]

CANDIDATE_DETAIL_DATA = {
    "user": build(CANDIDATE_ROWS_DATA[0]["user"]),
    "stats": {"tests_total": 4, "average_score": 87.2},
    "tests": [
        {
            "id": 101,
            "created_at": NOW_UTC - timedelta(days=3, hours=1),
            "final_score": 88,
            "raw_score": 100,
            "rating": "A",
            "total_time": 1250,
        },
        {
            "id": 102,
            "created_at": NOW_UTC - timedelta(days=12),
            "final_score": 82,
            "raw_score": 100,
            "rating": "B",
            "total_time": 1420,
        },
    ],
    "answers_map": {
        101: {"questions_correct": 18, "questions_total": 20, "questions_overtime": 1},
        102: {"questions_correct": 15, "questions_total": 20, "questions_overtime": 0},
    },
    "messages": [
        {
            "created_at": NOW_UTC - timedelta(days=1, hours=2),
            "send_time": "Сегодня 12:15",
            "message_text": "Напоминаем про интервью с Алексеем завтра в 15:00.",
            "is_active": True,
        },
        {
            "created_at": NOW_UTC - timedelta(days=5),
            "send_time": "07.09 10:00",
            "message_text": "Спасибо за прохождение теста! Мы свяжемся в ближайшее время.",
            "is_active": False,
        },
    ],
}

RECRUITER_ROWS_DATA: List[Dict[str, Any]] = [
    {
        "rec": {
            "id": 10,
            "name": "Алексей Захаров",
            "active": True,
            "tz": "Europe/Moscow",
            "tg_chat_id": 748293002,
        },
        "stats": {"free": 3, "pending": 2, "booked": 4, "total": 9},
        "cities": [("Москва", "Europe/Moscow"), ("Казань", "Europe/Moscow")],
        "next_free_local": "12 сентября, 14:00",
        "next_is_future": True,
    },
    {
        "rec": {
            "id": 11,
            "name": "Мария Орлова",
            "active": True,
            "tz": "Europe/Samara",
            "tg_chat_id": None,
        },
        "stats": {"free": 2, "pending": 1, "booked": 1, "total": 4},
        "cities": [("Самара", "Europe/Samara")],
        "next_free_local": "14 сентября, 10:30",
        "next_is_future": True,
    },
]

RECRUITER_OPTIONS_DATA = [
    {"id": item["rec"]["id"], "name": item["rec"]["name"], "tz": item["rec"].get("tz")}
    for item in RECRUITER_ROWS_DATA
]

SLOT_ROWS_DATA: List[Dict[str, Any]] = [
    {
        "id": 301,
        "status": "FREE",
        "duration_min": 45,
        "start_utc": NOW_UTC + timedelta(days=1, hours=1),
        "recruiter": {"id": 10, "name": "Алексей Захаров", "tz": "Europe/Moscow"},
        "candidate_fio": None,
        "candidate_tg_id": None,
        "candidate_tz": None,
        "interview_outcome": None,
    },
    {
        "id": 302,
        "status": "BOOKED",
        "duration_min": 45,
        "start_utc": NOW_UTC + timedelta(days=2, hours=3),
        "recruiter": {"id": 10, "name": "Алексей Захаров", "tz": "Europe/Moscow"},
        "candidate_fio": "Анна Смирнова",
        "candidate_tg_id": 438201239,
        "candidate_tz": "Europe/Moscow",
        "interview_outcome": None,
    },
    {
        "id": 303,
        "status": "PENDING",
        "duration_min": 30,
        "start_utc": NOW_UTC + timedelta(days=1, hours=5),
        "recruiter": {"id": 11, "name": "Мария Орлова", "tz": "Europe/Samara"},
        "candidate_fio": "Егор Кравцов",
        "candidate_tg_id": 522118002,
        "candidate_tz": "Europe/Moscow",
        "interview_outcome": None,
    },
]

STATUS_COUNTS_DATA = {
    "FREE": 8,
    "PENDING": 5,
    "BOOKED": 9,
    "CONFIRMED_BY_CANDIDATE": 2,
    "total": 24,
}

TEMPLATE_OVERVIEW_DATA = {
    "global": {
        "stages": [
            {
                "key": "invite",
                "title": "Приглашение",
                "description": "Предлагаем выбрать слот для интервью.",
                "default": "Добрый день! Выберите время интервью по ссылке...",
                "value": "Здравствуйте! Выберите удобный слот по ссылке {{slot_datetime_local}}.",
                "is_custom": True,
            },
            {
                "key": "reminder",
                "title": "Напоминание",
                "description": "Сообщение за 2 часа до встречи.",
                "default": "Напоминаем про интервью сегодня в {{slot_time_local}}.",
                "value": None,
                "is_custom": False,
            },
            {
                "key": "followup",
                "title": "Подтверждение",
                "description": "Просим подтвердить участие.",
                "default": "Подтвердите участие, ответив на это сообщение.",
                "value": None,
                "is_custom": False,
            },
            {
                "key": "welcome_day",
                "title": "Ознакомительный день",
                "description": "Информация после прохождения интервью.",
                "default": "Мы ждём вас на ознакомительный день {{slot_date_local}}.",
                "value": "Спасибо за интервью! Ждём вас {{slot_date_local}} по адресу {{address}}.",
                "is_custom": True,
            },
        ]
    },
    "cities": [
        {
            "city": {"id": 1, "name": "Москва", "tz": "Europe/Moscow"},
            "stages": [
                {
                    "key": "invite",
                    "title": "Приглашение",
                    "default": "Добрый день! Выберите время интервью по ссылке...",
                    "value": "Московская команда приглашает вас на интервью {{slot_datetime_local}}.",
                    "is_custom": True,
                },
                {
                    "key": "reminder",
                    "title": "Напоминание",
                    "default": "Напоминаем про интервью сегодня в {{slot_time_local}}.",
                    "value": None,
                    "is_custom": False,
                },
            ],
        },
    ],
}

QUESTIONS_DATA = [
    {
        "test_id": "test-1",
        "title": "Оценка сервиса",
        "questions": [
            {
                "id": 1,
                "index": 1,
                "title": "Почему вам интересна наша компания?",
                "prompt": "Выберите один вариант",
                "kind": "choice",
                "is_active": True,
                "updated_at": NOW_UTC - timedelta(days=1, hours=3),
                "options_count": 4,
                "correct_label": "Гибкий график",
            },
            {
                "id": 2,
                "index": 2,
                "title": "Опишите ваш опыт общения с клиентами",
                "prompt": "Свободный ответ",
                "kind": "text",
                "is_active": True,
                "updated_at": NOW_UTC - timedelta(days=5),
                "options_count": None,
                "correct_label": None,
            },
        ],
    },
    {
        "test_id": "test-2",
        "title": "Поведение в конфликте",
        "questions": [
            {
                "id": 3,
                "index": 1,
                "title": "Как вы решите конфликт в чате?",
                "prompt": None,
                "kind": "text",
                "is_active": False,
                "updated_at": NOW_UTC - timedelta(days=14),
                "options_count": None,
                "correct_label": None,
            }
        ],
    },
]

CITY_SEED_DATA = [
    {
        "name": "Москва",
        "tz": "Europe/Moscow",
        "criteria": "Опыт работы в рознице от 1 года",
        "experts": "2 наставника, 1 тимлид",
        "plan_week": 12,
        "plan_month": 48,
        "active": True,
    },
    {
        "name": "Казань",
        "tz": "Europe/Moscow",
        "criteria": "Отличное знание города",
        "experts": "1 наставник",
        "plan_week": 6,
        "plan_month": 24,
        "active": True,
    },
]

CITIES_DATA: List[Dict[str, Any]] = []
for index, seed in enumerate(CITY_SEED_DATA, start=1):
    entry = dict(seed)
    entry["id"] = index
    CITIES_DATA.append(entry)

EXTRA_CITIES = 210
TZ_ROTATION = ["Europe/Moscow", "Europe/Samara", "Asia/Yekaterinburg"]
for offset in range(EXTRA_CITIES):
    city_id = len(CITIES_DATA) + 1
    tz_choice = TZ_ROTATION[offset % len(TZ_ROTATION)]
    CITIES_DATA.append(
        {
            "id": city_id,
            "name": f"Город {city_id:03d}",
            "tz": tz_choice,
            "criteria": "Коротко: опыт продаж от 6 месяцев" if offset % 5 == 0 else "",
            "experts": "Два наставника по графику" if offset % 7 == 0 else "",
            "plan_week": 10 + (offset % 5) if offset % 2 == 0 else None,
            "plan_month": 40 + (offset % 6) * 4 if offset % 3 == 0 else None,
            "active": offset % 4 != 0,
        }
    )


def _build_stage_entries(custom_map: Dict[str, str]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for stage in CITY_TEMPLATE_STAGES:
        value = custom_map.get(stage.key, "")
        payload.append(
            {
                "key": stage.key,
                "title": stage.title,
                "description": stage.description,
                "default": STAGE_DEFAULTS.get(stage.key, ""),
                "value": value,
                "is_custom": bool(value.strip()),
            }
        )
    return payload


CITY_STAGE_CUSTOM_VALUES: Dict[int, Dict[str, str]] = {
    1: {
        "stage1_invite": "Москва ждёт вас {{slot_date_local}} в офисе на Новослободской.",
    }
}


CITY_STAGES_DATA = {
    city_id: _build_stage_entries(custom_map)
    for city_id, custom_map in CITY_STAGE_CUSTOM_VALUES.items()
}

OWNERS_DATA = {1: 10}
REC_MAP_DATA = {item["rec"]["id"]: item["rec"] for item in RECRUITER_ROWS_DATA}
CITY_CITIES_DATA = [
    {"id": city["id"], "name": city["name"], "tz": city["tz"]}
    for city in CITIES_DATA[:12]
]

TZ_OPTIONS_DATA = [
    {"value": tz_name, "label": tz_display(tz_name)}
    for tz_name in ["Europe/Moscow", "Europe/Samara", "Asia/Yekaterinburg"]
]

CITY_NAMES_DATA = [city["name"] for city in CITY_CITIES_DATA]


@dataclass
class DemoRoute:
    path: str
    template: str
    context_factory: Callable[[], Dict[str, Any]]
    slug: str


DEMO_ROUTES: List[DemoRoute] = []


def register_route(path: str, template_name: str, slug: str, context_factory: Callable[[], Dict[str, Any]]) -> None:
    DEMO_ROUTES.append(DemoRoute(path=path, template=template_name, context_factory=context_factory, slug=slug))

    @app.get(path, response_class=HTMLResponse)
    async def view(request: Request, factory: Callable[[], Dict[str, Any]] = context_factory, tpl: str = template_name) -> HTMLResponse:
        context = factory()
        context["request"] = request
        return templates.TemplateResponse(tpl, context)


# --- Context factories ------------------------------------------------------

def dashboard_context() -> Dict[str, Any]:
    return {"counts": build(COUNTS_DATA), "bot_status": build(BOT_STATUS_DATA)}


def candidates_list_context() -> Dict[str, Any]:
    return {
        "filters": {"search": ""},
        "analytics": build(ANALYTICS_DATA),
        "items": build(CANDIDATE_ROWS_DATA),
    }


def candidate_detail_context() -> Dict[str, Any]:
    detail = build(CANDIDATE_DETAIL_DATA)
    return {
        "user": detail.user,
        "stats": detail.stats,
        "tests": detail.tests,
        "answers_map": detail.answers_map,
        "messages": detail.messages,
    }


def candidates_new_context() -> Dict[str, Any]:
    return {"cities": list(CITY_NAMES_DATA)}


def recruiters_list_context() -> Dict[str, Any]:
    return {"recruiter_rows": build(RECRUITER_ROWS_DATA)}


def recruiters_new_context() -> Dict[str, Any]:
    return {"tz_options": list(TZ_OPTIONS_DATA), "cities": build(CITY_CITIES_DATA), "form_data": {}}


def slots_list_context() -> Dict[str, Any]:
    return {
        "slots": build(SLOT_ROWS_DATA),
        "status_counts": build(STATUS_COUNTS_DATA),
        "recruiter_options": build(RECRUITER_OPTIONS_DATA),
        "filter_recruiter_id": None,
        "filter_status": None,
        "per_page": 20,
        "page": 1,
        "pages_total": 1,
        "qrecr": "",
        "qstat": "",
        "qpp": "",
        "flash": None,
    }


def slots_new_context() -> Dict[str, Any]:
    return {"recruiters": build(RECRUITER_ROWS_DATA), "flash": None}


def templates_list_context() -> Dict[str, Any]:
    return {"overview": build(TEMPLATE_OVERVIEW_DATA)}


def questions_list_context() -> Dict[str, Any]:
    return {"tests": build(QUESTIONS_DATA)}


def cities_list_context() -> Dict[str, Any]:
    return {
        "cities": build(CITIES_DATA),
        "owners": build(OWNERS_DATA),
        "rec_map": build(REC_MAP_DATA),
        "city_stages": build(CITY_STAGES_DATA),
    }


def city_edit_context() -> Dict[str, Any]:
    city = build(CITIES_DATA[0])
    stage_payload = CITY_STAGES_DATA.get(city.id, _build_stage_entries({}))
    return {
        "city": city,
        "responsible_id": OWNERS_DATA.get(city.id),
        "recruiters": build([item["rec"] for item in RECRUITER_ROWS_DATA]),
        "stage_meta": CITY_TEMPLATE_STAGES,
        "stages": build(stage_payload),
        "stage_defaults": {stage.key: stage.default_text for stage in CITY_TEMPLATE_STAGES},
        "timezone_options": [option["value"] for option in TZ_OPTIONS_DATA],
    }


# Register routes in deterministic order for previews/screenshots.
register_route("/", "index.html", "index", dashboard_context)
register_route("/candidates", "candidates_list.html", "candidates", candidates_list_context)
register_route("/candidates/1", "candidates_detail.html", "candidate-detail", candidate_detail_context)
register_route("/candidates/new", "candidates_new.html", "candidate-new", candidates_new_context)
register_route("/recruiters", "recruiters_list.html", "recruiters", recruiters_list_context)
register_route("/recruiters/new", "recruiters_new.html", "recruiter-new", recruiters_new_context)
register_route("/slots", "slots_list.html", "slots", slots_list_context)
register_route("/slots/new", "slots_new.html", "slot-new", slots_new_context)
register_route("/templates", "templates_list.html", "templates", templates_list_context)
register_route("/questions", "questions_list.html", "questions", questions_list_context)
register_route("/cities", "cities_list.html", "cities", cities_list_context)
register_route("/cities/1/edit", "city_edit.html", "city-edit", city_edit_context)


__all__ = ["app", "templates", "DEMO_ROUTES", "dashboard_context"]
