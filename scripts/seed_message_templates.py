#!/usr/bin/env python3
"""Seed default message templates for the Telegram bot (TG/RU, global)."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

# Ensure project root is on sys.path when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load env defaults if DATABASE_URL isn't set in the shell.
if "DATABASE_URL" not in os.environ:
    from backend.core.env import load_env  # noqa: E402

    load_env()
    if "DATABASE_URL" not in os.environ:
        example_env = PROJECT_ROOT / ".env.local.example"
        if example_env.exists():
            load_env(example_env)

from backend.core.db import sync_session  # noqa: E402
from backend.domain.models import MessageTemplate  # noqa: E402

DEFAULT_LOCALE = "ru"
DEFAULT_CHANNEL = "tg"
DEFAULT_VERSION = 1
UPDATED_BY = "seed"

TEMPLATES: dict[str, str] = {
    # Registration
    "choose_recruiter": "Привет! Выберите рекрутёра, чтобы продолжить запись.",
    "existing_reservation": "У вас уже есть запись на {{dt_local}}. Если нужно изменить — напишите /start.",
    "manual_schedule_prompt": "Сейчас нет слотов. Напишите удобный диапазон времени (например: 25.07 12:00–16:00).",
    "no_slots": "Свободных слотов нет. Мы напишем, когда появятся новые.",

    # Testing
    "t1_intro": "Начинаем тест 1. Ответьте на вопросы в чате.",
    "t1_progress": "Ответ принят. Продолжаем тест 1.",
    "t1_done": "Тест 1 завершён. Спасибо!",
    "t1_format_reject": "Ответ не принят: неверный формат. Попробуйте ещё раз.",
    "t1_format_clarify": "Проверьте формат ответа и отправьте ещё раз.",
    "t1_schedule_reject": "По результатам теста запись на следующий этап недоступна.",
    "t2_intro": "Начинаем тест 2. Ответьте на вопросы ниже.",
    "t2_result": "Тест 2 завершён. Рекрутёр сообщит результат.",

    # Interview
    "slot_taken": "Этот слот уже занят. Пожалуйста, выберите другое время.",
    "slot_sent": "Вы записаны на {{dt_local}}. Напоминание придёт перед встречей.",
    "slot_reschedule": "Запрос на перенос получен. Мы предложим новое время.",
    "slot_proposal_candidate": "Вам доступен слот {{slot_date_local}} в {{slot_time_local}}. Подтвердите участие.",
    "slot_proposal": "Предлагаем время {{dt_local}}. Подтвердите, подходит ли.",
    "interview_confirmed_candidate": "Запись подтверждена! Встреча: {{dt_local}}.",
    "interview_confirmed": "Интервью подтверждено: {{dt_local}}.",
    "interview_preparation": "Подготовка к интервью: проверьте связь и документы. Время: {{dt_local}}.",
    "interview_invite_details": "Приглашаем на интервью {{dt_local}}. Ссылка: {{join_link}}.",
    "candidate_reschedule_prompt": "Хотите перенести встречу? Выберите удобное время.",
    "reschedule_prompt": "Запрос на перенос принят. Мы свяжемся с вами.",
    "reschedule_approved_candidate": "Перенос подтверждён. Новое время: {{dt_local}}.",
    "reschedule_declined_candidate": "Перенос отклонён. Оставляем время: {{dt_local}}.",
    "slot_assignment_offer": "Предлагаем слот {{dt_local}}. Подтвердите участие.",
    "slot_assignment_reschedule_approved": "Перенос слота подтверждён: {{dt_local}}.",
    "slot_assignment_reschedule_declined": "Перенос слота отклонён. Время остаётся: {{dt_local}}.",
    "slot_assignment_reschedule_requested": "Запрос на перенос слота получен.",
    "stage1_invite": "Этап 1: приглашаем на собеседование {{dt_local}}.",

    # Intro day
    "intro_day_invitation": "Приглашаем на ознакомительный день {{dt_local}}. Адрес: {{intro_address}}.",
    "intro_day_invite_city": "Ознакомительный день в {{city_name}}: {{dt_local}}. Адрес: {{intro_address}}.",
    "intro_day_reminder": "Напоминание: ознакомительный день {{dt_local}}. Адрес: {{intro_address}}.",
    "intro_day_remind_2h": "Через 2 часа ознакомительный день. Адрес: {{intro_address}}.",
    "stage3_intro_invite": "Этап 3: ознакомительный день {{dt_local}}. Адрес: {{intro_address}}.",
    "stage4_intro_reminder": "Этап 4: подтвердите участие в ознакомительном дне {{dt_local}}.",

    # Reminders & confirmations
    "reminder_2h": "Напоминание: встреча через 2 часа ({{dt_local}}).",
    "reminder_30m": "Напоминание: встреча через 30 минут ({{dt_local}}).",
    "reminder_3h": "Напоминание: встреча через 3 часа ({{dt_local}}).",
    "reminder_6h": "Напоминание: встреча через 6 часов ({{dt_local}}).",
    "confirm_6h": "Подтвердите участие: встреча через 6 часов ({{dt_local}}).",
    "confirm_2h": "Подтвердите участие: встреча через 2 часа ({{dt_local}}).",
    "att_confirmed_link": "Спасибо за подтверждение! Ссылка: {{join_link}}.",
    "att_confirmed_ack": "Спасибо! Подтверждение получено.",
    "att_declined": "Вы отказались от встречи. Если хотите перенести — напишите /start.",
    "stage2_interview_reminder": "Этап 2: напоминание за 2 часа ({{dt_local}}).",
    "interview_remind_confirm_2h": "Напоминание за 2 часа: подтвердите участие. Время: {{dt_local}}.",
    "no_show_gentle": "Мы не дождались вас на встрече. Если хотите продолжить — напишите /start.",

    # Results
    "approved_msg": "Поздравляем! Вы одобрены. Рекрутёр свяжется с вами.",
    "result_fail": "К сожалению, по результатам мы не можем продолжить процесс.",
    "candidate_rejection": "Спасибо за интерес. К сожалению, мы не готовы продолжить.",

    # Service (recruiter-facing)
    "slot_confirmed_recruiter": "Кандидат подтвердил слот: {{dt_local}}.",
    "reschedule_requested_recruiter": "Кандидат запросил перенос встречи.",
    "recruiter_candidate_confirmed_notice": "Кандидат подтвердил участие во встрече.",
}


def seed_templates(*, overwrite: bool = False, dry_run: bool = False) -> None:
    now = datetime.now(timezone.utc)
    keys = list(TEMPLATES.keys())

    with sync_session() as session:
        existing_rows = session.scalars(
            select(MessageTemplate).where(
                MessageTemplate.key.in_(keys),
                MessageTemplate.locale == DEFAULT_LOCALE,
                MessageTemplate.channel == DEFAULT_CHANNEL,
                MessageTemplate.city_id.is_(None),
                MessageTemplate.version == DEFAULT_VERSION,
            )
        ).all()
        existing_map = {row.key: row for row in existing_rows}

        created = 0
        updated = 0
        skipped = 0

        for key, body in TEMPLATES.items():
            existing = existing_map.get(key)
            if existing:
                if overwrite:
                    existing.body_md = body
                    existing.is_active = True
                    existing.updated_by = UPDATED_BY
                    existing.updated_at = now
                    updated += 1
                else:
                    skipped += 1
                continue

            tmpl = MessageTemplate(
                key=key,
                locale=DEFAULT_LOCALE,
                channel=DEFAULT_CHANNEL,
                body_md=body,
                version=DEFAULT_VERSION,
                is_active=True,
                city_id=None,
                updated_by=UPDATED_BY,
                updated_at=now,
                created_at=now,
            )
            session.add(tmpl)
            created += 1

        if dry_run:
            session.rollback()
        else:
            session.commit()

    print("Seed templates summary")
    print(f"  created: {created}")
    print(f"  updated: {updated}")
    print(f"  skipped: {skipped}")
    if dry_run:
        print("  (dry-run: no changes were saved)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed default message templates (TG/RU, global).")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing templates.")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without saving.")
    args = parser.parse_args()

    seed_templates(overwrite=args.overwrite, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
