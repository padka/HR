from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0014_notification_outbox_and_templates"
down_revision = "0013_enhance_notification_logs"
branch_labels = None
depends_on = None


TABLE_MESSAGE_TEMPLATES = "message_templates"
TABLE_OUTBOX = "outbox_notifications"
TABLE_NOTIFICATION_LOGS = "notification_logs"


def _get_operations(conn: Connection) -> Tuple[Operations, MigrationContext, Connection]:
    engine = getattr(conn, "engine", None)
    standalone_conn = engine.connect() if engine is not None else conn
    if engine is not None and engine.dialect.name == "sqlite" and standalone_conn is not conn:
        standalone_conn.close()
        standalone_conn = conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def upgrade(conn: Connection) -> None:
    op, context, standalone_conn = _get_operations(conn)
    try:
        dialect = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect.name if dialect is not None else ""

        with context.begin_transaction():
            op.create_table(
                TABLE_MESSAGE_TEMPLATES,
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("key", sa.String(length=100), nullable=False),
                sa.Column("locale", sa.String(length=16), nullable=False, server_default="ru"),
                sa.Column("channel", sa.String(length=32), nullable=False, server_default="tg"),
                sa.Column("body_md", sa.Text(), nullable=False),
                sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                ),
                sa.UniqueConstraint(
                    "key",
                    "locale",
                    "channel",
                    "version",
                    name="uq_template_key_locale_channel_version",
                ),
            )

            op.create_table(
                TABLE_OUTBOX,
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("booking_id", sa.Integer(), nullable=True),
                sa.Column("type", sa.String(length=50), nullable=False),
                sa.Column("payload_json", sa.JSON(), nullable=True),
                sa.Column("candidate_tg_id", sa.BigInteger(), nullable=True),
                sa.Column("recruiter_tg_id", sa.BigInteger(), nullable=True),
                sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
                sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                ),
                sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("last_error", sa.Text(), nullable=True),
                sa.Column("correlation_id", sa.String(length=64), nullable=True),
                sa.ForeignKeyConstraint(["booking_id"], ["slots.id"], ondelete="CASCADE"),
            )

            op.add_column(
                TABLE_NOTIFICATION_LOGS,
                sa.Column("template_key", sa.String(length=100), nullable=True),
            )
            op.add_column(
                TABLE_NOTIFICATION_LOGS,
                sa.Column("template_version", sa.Integer(), nullable=True),
            )

        if dialect_name == "postgresql":
            with context.autocommit_block():
                op.create_index(
                    "uq_outbox_type_booking_candidate",
                    TABLE_OUTBOX,
                    ["type", "booking_id", "candidate_tg_id"],
                    unique=True,
                    postgresql_concurrently=True,
                )
            with context.autocommit_block():
                op.create_index(
                    "ix_outbox_status_next_retry",
                    TABLE_OUTBOX,
                    ["status", "next_retry_at"],
                    postgresql_concurrently=True,
                )
            with context.autocommit_block():
                op.create_index(
                    "ix_template_active_lookup",
                    TABLE_MESSAGE_TEMPLATES,
                    ["key", "locale", "channel", "is_active"],
                    postgresql_concurrently=True,
                )
        else:
            with context.begin_transaction():
                op.create_index(
                    "uq_outbox_type_booking_candidate",
                    TABLE_OUTBOX,
                    ["type", "booking_id", "candidate_tg_id"],
                    unique=True,
                )
                op.create_index(
                    "ix_outbox_status_next_retry",
                    TABLE_OUTBOX,
                    ["status", "next_retry_at"],
                )
                op.create_index(
                    "ix_template_active_lookup",
                    TABLE_MESSAGE_TEMPLATES,
                    ["key", "locale", "channel", "is_active"],
                )

        seed_rows = [
            {
                "key": "interview_confirmed_candidate",
                "locale": "ru",
                "channel": "tg",
                "body_md": (
                    "{candidate_name} 👋\n"
                    "Поздравляем — вы шаг ближе к команде **SMART SERVICE**!\n\n"
                    "🗓 {dt_local}\n"
                    "💬 Формат: видеочат | 15–20 мин\n\n"
                    "⚡ Что нужно заранее:\n"
                    "• стабильный интернет\n"
                    "• 2–3 вопроса о вакансии\n\n"
                    "🔔 Не забудьте поставить напоминание на телефон."
                ),
                "version": 1,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "key": "interview_reminder_2h",
                "locale": "ru",
                "channel": "tg",
                "body_md": (
                    "Напоминаем: интервью начнётся через 2 часа.\n\n"
                    "🗓 {dt_local}\n"
                    "🔗 Ссылка на встречу: {join_link}\n\n"
                    "Если планы поменялись — напишите нам, чтобы подобрать другое время."
                ),
                "version": 1,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "key": "recruiter_candidate_confirmed_notice",
                "locale": "ru",
                "channel": "tg",
                "body_md": (
                    "✅ Кандидат {candidate_name} подтвердил участие\n"
                    "📅 {dt_local}\n"
                    "💬 Рекрутёр: {recruiter_name}"
                ),
                "version": 1,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "key": "candidate_reschedule_prompt",
                "locale": "ru",
                "channel": "tg",
                "body_md": (
                    "🔁 Мы освободили ваш слот.\n"
                    "Выберите, пожалуйста, новое время в расписании — просто нажмите кнопку «Выбрать слот»."
                ),
                "version": 1,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "key": "no_slots_fallback",
                "locale": "ru",
                "channel": "tg",
                "body_md": (
                    "Свободных слотов сейчас нет.\n"
                    "Оставьте сообщение рекрутёру — мы подберём интервью и вернёмся с предложением времени."
                ),
                "version": 1,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc),
            },
        ]

        with context.begin_transaction():
            op.bulk_insert(
                sa.table(
                    TABLE_MESSAGE_TEMPLATES,
                    sa.column("key", sa.String()),
                    sa.column("locale", sa.String()),
                    sa.column("channel", sa.String()),
                    sa.column("body_md", sa.Text()),
                    sa.column("version", sa.Integer()),
                    sa.column("is_active", sa.Boolean()),
                    sa.column("updated_at", sa.DateTime(timezone=True)),
                ),
                seed_rows,
            )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    op, context, standalone_conn = _get_operations(conn)
    try:
        with context.begin_transaction():
            op.drop_column(TABLE_NOTIFICATION_LOGS, "template_version")
            op.drop_column(TABLE_NOTIFICATION_LOGS, "template_key")

        with context.begin_transaction():
            op.drop_table(TABLE_OUTBOX)
            op.drop_table(TABLE_MESSAGE_TEMPLATES)
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
