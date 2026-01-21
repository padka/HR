"""FastAPI demo server with canned data for Liquid Glass previews."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, date as date_type, time as time_type
from pathlib import Path
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from zoneinfo import ZoneInfo

from backend.apps.admin_ui.services.candidates import (
    INTERVIEW_SCRIPT_STEPS,
    INTRO_DAY_MESSAGE_TEMPLATE,
)

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
    csrf_token=lambda _request=None: "",
    csrf_input=lambda _request=None: "",
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

WEEKLY_KPIS_DATA = {
    "timezone": "Europe/Moscow",
    "current": {
        "week_start": "2024-03-24",
        "week_end": "2024-03-31",
        "label": "24.03.2024 — 30.03.2024",
        "metrics": [
            {
                "key": "tested",
                "label": "Проходили тест",
                "tone": "progress",
                "icon": "🧪",
                "value": 42,
                "previous": 35,
                "trend": {
                    "direction": "up",
                    "percent": 20.0,
                    "display": "↑ 20%",
                    "label": "Рост на 20%",
                    "arrow": "↑",
                    "magnitude": "20",
                },
                "details": [
                    {
                        "candidate": "Анна Смирнова",
                        "recruiter": "—",
                        "event_at": "2024-03-25T10:00:00+03:00",
                        "event_label": "25.03.2024 10:00 MSK",
                        "city": "Москва",
                        "timezone": "Europe/Moscow",
                    },
                    {
                        "candidate": "Павел Кузнецов",
                        "recruiter": "—",
                        "event_at": "2024-03-27T13:45:00+03:00",
                        "event_label": "27.03.2024 13:45 MSK",
                        "city": "Санкт-Петербург",
                        "timezone": "Europe/Moscow",
                    },
                ],
            },
            {
                "key": "completed_test",
                "label": "Дошли до конца теста",
                "tone": "success",
                "icon": "🎯",
                "value": 38,
                "previous": 32,
                "trend": {
                    "direction": "up",
                    "percent": 18.8,
                    "display": "↑ 18.8%",
                    "label": "Рост на 18.8%",
                    "arrow": "↑",
                    "magnitude": "18.8",
                },
                "details": [
                    {
                        "candidate": "Илья Фомин",
                        "recruiter": "—",
                        "event_at": "2024-03-26T12:15:00+03:00",
                        "event_label": "26.03.2024 12:15 MSK",
                        "city": "Казань",
                        "timezone": "Europe/Moscow",
                    }
                ],
            },
            {
                "key": "booked",
                "label": "Записались на собеседование",
                "tone": "progress",
                "icon": "🗓",
                "value": 24,
                "previous": 28,
                "trend": {
                    "direction": "down",
                    "percent": -14.3,
                    "display": "↓ 14.3%",
                    "label": "Снижение на 14.3%",
                    "arrow": "↓",
                    "magnitude": "14.3",
                },
                "details": [
                    {
                        "candidate": "Мария Лебедева",
                        "recruiter": "Алексей Захаров",
                        "event_at": "2024-03-28T15:00:00+03:00",
                        "event_label": "28.03.2024 15:00 MSK",
                        "city": "Москва",
                        "timezone": "Europe/Moscow",
                    },
                    {
                        "candidate": "Егор Кравцов",
                        "recruiter": "Мария Орлова",
                        "event_at": "2024-03-29T11:30:00+03:00",
                        "event_label": "29.03.2024 11:30 MSK",
                        "city": "Самара",
                        "timezone": "Europe/Samara",
                    },
                ],
            },
            {
                "key": "confirmed",
                "label": "Подтвердили участие",
                "tone": "success",
                "icon": "✅",
                "value": 19,
                "previous": 20,
                "trend": {
                    "direction": "down",
                    "percent": -5.0,
                    "display": "↓ 5%",
                    "label": "Снижение на 5%",
                    "arrow": "↓",
                    "magnitude": "5",
                },
                "details": [
                    {
                        "candidate": "Софья Егорова",
                        "recruiter": "Мария Орлова",
                        "event_at": "2024-03-27T18:10:00+03:00",
                        "event_label": "27.03.2024 18:10 MSK",
                        "city": "Самара",
                        "timezone": "Europe/Samara",
                    }
                ],
            },
            {
                "key": "interview_passed",
                "label": "Прошли собеседование",
                "tone": "success",
                "icon": "🏁",
                "value": 11,
                "previous": 9,
                "trend": {
                    "direction": "up",
                    "percent": 22.2,
                    "display": "↑ 22.2%",
                    "label": "Рост на 22.2%",
                    "arrow": "↑",
                    "magnitude": "22.2",
                },
                "details": [
                    {
                        "candidate": "Дмитрий Титов",
                        "recruiter": "Алексей Захаров",
                        "event_at": "2024-03-26T17:40:00+03:00",
                        "event_label": "26.03.2024 17:40 MSK",
                        "city": "Москва",
                        "timezone": "Europe/Moscow",
                    }
                ],
            },
            {
                "key": "intro_day",
                "label": "Пришли на ознакомительный день",
                "tone": "warning",
                "icon": "🌅",
                "value": 6,
                "previous": 0,
                "trend": {
                    "direction": "up",
                    "percent": None,
                    "display": "—",
                    "label": "Нет данных за прошлую неделю",
                    "arrow": "→",
                    "magnitude": None,
                },
                "details": [
                    {
                        "candidate": "Ирина Ким",
                        "recruiter": "Наталья Соколова",
                        "event_at": "2024-03-30T09:00:00+03:00",
                        "event_label": "30.03.2024 09:00 MSK",
                        "city": "Москва",
                        "timezone": "Europe/Moscow",
                    }
                ],
            },
        ],
    },
    "previous": {
        "week_start": "2024-03-17",
        "week_end": "2024-03-24",
        "label": "17.03.2024 — 23.03.2024",
        "metrics": {
            "tested": 35,
            "completed_test": 32,
            "booked": 28,
            "confirmed": 20,
            "interview_passed": 9,
            "intro_day": 0,
        },
        "computed_at": "2024-03-24T00:05:00+03:00",
    },
}

CALENDAR_TZ = "Europe/Moscow"
CALENDAR_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _calendar_stub() -> Dict[str, object]:
    zone = ZoneInfo(CALENDAR_TZ)
    today = NOW_UTC.astimezone(zone).date()
    tomorrow = today + timedelta(days=1)

    def _day(date: date_type, *, count: int, selected: bool) -> Dict[str, object]:
        return {
            "date": date.isoformat(),
            "label": date.strftime("%d.%m"),
            "weekday": CALENDAR_WEEKDAYS[date.weekday() % 7],
            "count": count,
            "is_today": date == today,
            "is_selected": selected,
        }

    start_local = datetime.combine(today, time_type(hour=10), tzinfo=zone)
    end_local = start_local + timedelta(minutes=60)

    return {
        "ok": True,
        "selected_date": today.isoformat(),
        "selected_label": "сегодня",
        "selected_human": today.strftime("%d.%m.%Y"),
        "timezone": CALENDAR_TZ,
        "days": [_day(today, count=1, selected=True), _day(tomorrow, count=0, selected=False)],
        "events": [
            {
                "id": 101,
                "status": "CONFIRMED_BY_CANDIDATE",
                "status_label": "Подтверждено кандидатом",
                "status_variant": "success",
                "start_time": start_local.strftime("%H:%M"),
                "end_time": end_local.strftime("%H:%M"),
                "start_iso": start_local.astimezone(timezone.utc).isoformat(),
                "duration": 60,
                "recruiter": {"id": 7, "name": "Ирина Никифорова", "tz": CALENDAR_TZ},
                "city": {"id": 1, "name": "Москва"},
                "candidate": {
                    "name": "Алексей Смирнов",
                    "profile_url": "/candidates/42",
                    "telegram_id": 123456789,
                },
            }
        ],
        "events_total": 1,
        "status_summary": {
            "CONFIRMED_BY_CANDIDATE": 1,
            "BOOKED": 0,
            "PENDING": 0,
            "CANCELED": 0,
        },
        "meta": "Подтверждено: 1",
        "updated_label": NOW_UTC.astimezone(zone).strftime("Обновлено %H:%M"),
        "generated_at": NOW_UTC.isoformat(),
        "window_days": 7,
    }


DASHBOARD_CALENDAR_DATA = _calendar_stub()

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

primary_slot = {
    "id": 401,
    "start_utc": NOW_UTC + timedelta(hours=3),
    "status": "booked",
    "duration_min": 45,
    "candidate_tg_id": CANDIDATE_ROWS_DATA[0]["user"]["telegram_id"],
    "candidate_fio": CANDIDATE_ROWS_DATA[0]["user"]["fio"],
    "candidate_tz": "Europe/Moscow",
    "recruiter": {"name": "Алексей Захаров", "telemost_url": "https://telemost.yandex.ru/j/SMART_ONBOARDING"},
    "city": {"name": "Москва"},
    "interview_outcome": "success",
    "test2_sent_at": NOW_UTC - timedelta(hours=1),
    "interview_feedback": {
        "checklist": {step["id"]: (step["id"] != "company_intro") for step in INTERVIEW_SCRIPT_STEPS},
        "notes": "Кандидат уверенно отвечает на вопросы и заинтересован в развитии.",
        "updated_at": (NOW_UTC - timedelta(hours=1)).isoformat(),
    },
}

secondary_slot = {
    "id": 402,
    "start_utc": NOW_UTC - timedelta(days=5),
    "status": "completed",
    "duration_min": 30,
    "candidate_tg_id": CANDIDATE_ROWS_DATA[0]["user"]["telegram_id"],
    "candidate_fio": CANDIDATE_ROWS_DATA[0]["user"]["fio"],
    "candidate_tz": "Europe/Moscow",
    "recruiter": {"name": "Мария Орлова", "telemost_url": None},
    "city": {"name": "Санкт-Петербург"},
    "interview_outcome": "reject",
    "test2_sent_at": None,
    "interview_feedback": None,
}

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
        101: {
            "questions_correct": 18,
            "questions_total": 20,
            "questions_overtime": 1,
            "questions": [
                {
                    "question_text": "Как вы объясните клиенту ценность услуги SMART?",
                    "user_answer": "Рассказываю о результатах и поддержке команды",
                    "correct_answer": "Подчеркнуть выгоду для клиента и сопровождение",
                    "attempts_count": 1,
                    "time_spent": 42,
                    "is_correct": True,
                    "overtime": False,
                },
                {
                    "question_text": "Что сделать, если клиент сомневается?",
                    "user_answer": "Предложить попробовать и поддержать",
                    "correct_answer": "Предложить демо и рассказать про сопровождение",
                    "attempts_count": 2,
                    "time_spent": 65,
                    "is_correct": False,
                    "overtime": True,
                },
            ],
        },
        102: {
            "questions_correct": 15,
            "questions_total": 20,
            "questions_overtime": 0,
            "questions": [
                {
                    "question_text": "Основная цель ознакомительного дня?",
                    "user_answer": "Познакомить с командой",
                    "correct_answer": "Погружение в процессы и знакомство с командой",
                    "attempts_count": 1,
                    "time_spent": 30,
                    "is_correct": True,
                    "overtime": False,
                }
            ],
        },
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
    "slots": [primary_slot, secondary_slot],
    "latest_interview": primary_slot,
    "upcoming_slot": primary_slot,
    "stage": "Интервью назначено",
    "timeline": [
        {
            "kind": "slot",
            "dt": primary_slot["start_utc"],
            "status": primary_slot["status"],
            "recruiter": primary_slot["recruiter"]["name"],
            "city": primary_slot["city"]["name"],
            "tz": primary_slot["candidate_tz"],
        },
        {
            "kind": "test",
            "dt": NOW_UTC - timedelta(days=3, hours=1),
            "score": 88,
            "rating": "A",
        },
        {
            "kind": "message",
            "dt": NOW_UTC - timedelta(days=1, hours=2),
            "send_time": "Сегодня 12:15",
            "text": "Напоминаем про интервью с Алексеем завтра в 15:00.",
            "is_active": True,
        },
    ],
    "test_stage_summary": [
        {
            "label": "Тест 1",
            "score": 82,
            "raw_score": 100,
            "rating": "B",
            "dt": NOW_UTC - timedelta(days=12),
        },
        {
            "label": "Тест 2",
            "score": 88,
            "raw_score": 100,
            "rating": "A",
            "dt": NOW_UTC - timedelta(days=3, hours=1),
        },
    ],
    "interview_feedback": primary_slot["interview_feedback"],
    "interview_script": INTERVIEW_SCRIPT_STEPS,
    "intro_message_template": INTRO_DAY_MESSAGE_TEMPLATE,
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

CITIES_DATA = [
    {
        "id": 1,
        "name": "Москва",
        "tz": "Europe/Moscow",
        "criteria": "Опыт работы в рознице от 1 года",
        "experts": "2 наставника, 1 тимлид",
        "plan_week": 12,
        "plan_month": 48,
    },
    {
        "id": 2,
        "name": "Казань",
        "tz": "Europe/Moscow",
        "criteria": "Отличное знание города",
        "experts": "1 наставник",
        "plan_week": 6,
        "plan_month": 24,
    },
]

CITY_STAGES_DATA = {
    1: [
        {
            "key": "invite",
            "title": "Приглашение",
            "default": "Добрый день! Выберите время интервью по ссылке...",
            "value": "Москва ждёт вас {{slot_date_local}} в офисе на Новослободской.",
        },
        {
            "key": "reminder",
            "title": "Напоминание",
            "default": "Напоминаем про интервью сегодня в {{slot_time_local}}.",
            "value": None,
        },
    ]
}

CITY_RESPONSIBLES_DATA = {
    1: [
        {"id": 10, "name": "Алексей Захаров"},
        {"id": 11, "name": "Мария Орлова"},
    ],
    2: [
        {"id": 10, "name": "Алексей Захаров"},
    ],
}

OWNERS_DATA = {1: 10}
REC_MAP_DATA = {item["rec"]["id"]: item["rec"] for item in RECRUITER_ROWS_DATA}
CITY_CITIES_DATA = [
    {"id": 1, "name": "Москва", "tz": "Europe/Moscow"},
    {"id": 2, "name": "Казань", "tz": "Europe/Moscow"},
]

TZ_OPTIONS_DATA = [
    {"value": "Europe/Moscow", "label": tz_display("Europe/Moscow")},
    {"value": "Europe/Samara", "label": tz_display("Europe/Samara")},
    {"value": "Asia/Yekaterinburg", "label": tz_display("Asia/Yekaterinburg")},
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
    return {
        "counts": build(COUNTS_DATA),
        "bot_status": build(BOT_STATUS_DATA),
        "weekly_kpis": build(WEEKLY_KPIS_DATA),
        "calendar": build(DASHBOARD_CALENDAR_DATA),
    }


def candidates_list_context() -> Dict[str, Any]:
    return {
        "filters": {"search": ""},
        "analytics": build(ANALYTICS_DATA),
        "items": build(CANDIDATE_ROWS_DATA),
    }


def candidate_detail_context() -> Dict[str, Any]:
    detail = build(CANDIDATE_DETAIL_DATA)
    # The candidate profile template expects the full enriched payload that the
    # production service returns. Re-expose every key from the demo fixture so
    # that previewing "/candidates/1" renders the same sections (interview
    # timeline, script checklist, intro-day scheduler, etc.) as the real page.
    return dict(detail)


def candidates_new_context() -> Dict[str, Any]:
    return {"cities": list(CITY_NAMES_DATA)}


def recruiters_list_context() -> Dict[str, Any]:
    return {"recruiter_rows": build(RECRUITER_ROWS_DATA)}


def recruiters_new_context() -> Dict[str, Any]:
    return {"tz_options": list(TZ_OPTIONS_DATA), "cities": build(CITY_CITIES_DATA), "form_data": {}}


def recruiters_edit_context() -> Dict[str, Any]:
    recruiter = build(RECRUITER_ROWS_DATA[0]["rec"])
    editor_cities = build(
        CITY_CITIES_DATA
        + [
            {"id": 3, "name": "Самара", "tz": "Europe/Samara"},
            {"id": 4, "name": "Екатеринбург", "tz": "Asia/Yekaterinburg"},
            {"id": 5, "name": "Новосибирск", "tz": "Asia/Novosibirsk"},
            {"id": 6, "name": "Владивосток", "tz": "Asia/Vladivostok"},
        ]
    )
    return {
        "recruiter": recruiter,
        "cities": editor_cities,
        "selected_ids": {1, 4},
        "tz_options": list(TZ_OPTIONS_DATA),
        "form_data": {},
        "form_error": None,
    }


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
        "city_responsibles": build(CITY_RESPONSIBLES_DATA),
    }


# Register routes in deterministic order for previews/screenshots.
register_route("/", "index.html", "index", dashboard_context)
register_route("/candidates", "candidates_list.html", "candidates", candidates_list_context)
register_route("/candidates/1", "candidates_detail.html", "candidate-detail", candidate_detail_context)
register_route("/candidates/new", "candidates_new.html", "candidate-new", candidates_new_context)
register_route("/recruiters", "recruiters_list.html", "recruiters", recruiters_list_context)
register_route("/recruiters/new", "recruiters_new.html", "recruiter-new", recruiters_new_context)
register_route("/recruiters/10/edit", "recruiters_edit.html", "recruiter-edit", recruiters_edit_context)
register_route("/slots", "slots_list.html", "slots", slots_list_context)
register_route("/slots/new", "slots_new.html", "slot-new", slots_new_context)
register_route("/templates", "templates_list.html", "templates", templates_list_context)
register_route("/questions", "questions_list.html", "questions", questions_list_context)
register_route("/cities", "cities_list.html", "cities", cities_list_context)


__all__ = ["app", "templates", "DEMO_ROUTES", "dashboard_context"]
