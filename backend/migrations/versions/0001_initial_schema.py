"""Create core database tables."""

from __future__ import annotations

import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None


def _define_tables(metadata: sa.MetaData) -> None:
    sa.Table(
        "recruiters",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("tg_chat_id", sa.BigInteger, unique=True, nullable=True),
        sa.Column("tz", sa.String(64), nullable=False, server_default=sa.text("'Europe/Moscow'")),
        sa.Column("telemost_url", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    sa.Table(
        "cities",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("tz", sa.String(64), nullable=False, server_default=sa.text("'Europe/Moscow'")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name", name="uq_city_name"),
    )

    sa.Table(
        "recruiter_cities",
        metadata,
        sa.Column("recruiter_id", sa.Integer, nullable=False),
        sa.Column("city_id", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(["recruiter_id"], ["recruiters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recruiter_id", "city_id"),
        sa.UniqueConstraint("city_id", name="uq_recruiter_city_unique_city"),
    )

    sa.Table(
        "templates",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("city_id", sa.Integer, nullable=True),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], name="fk_templates_city_id", ondelete="CASCADE"),
        sa.UniqueConstraint("city_id", "key", name="uq_city_key"),
    )

    sa.Table(
        "slots",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("recruiter_id", sa.Integer, nullable=False),
        sa.Column("city_id", sa.Integer, nullable=True),
        sa.Column("candidate_city_id", sa.Integer, nullable=True),
        sa.Column("purpose", sa.String(32), nullable=False, server_default=sa.text("'interview'")),
        sa.Column("tz_name", sa.String(64), nullable=False, server_default=sa.text("'Europe/Moscow'")),
        sa.Column("start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_min", sa.Integer, nullable=False, server_default=sa.text("60")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'free'")),
        sa.Column("candidate_tg_id", sa.BigInteger, nullable=True),
        sa.Column("candidate_fio", sa.String(160), nullable=True),
        sa.Column("candidate_tz", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recruiter_id"], ["recruiters.id"], name="fk_slots_recruiter_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], name="fk_slots_city_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["candidate_city_id"],
            ["cities.id"],
            name="fk_slots_candidate_city_id",
            ondelete="SET NULL",
        ),
    )

    sa.Table(
        "test_questions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("test_id", sa.String(50), nullable=False),
        sa.Column("question_index", sa.Integer, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("test_id", "question_index", name="uq_test_question_index"),
    )

    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("fio", sa.String(160), nullable=False),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Index("ix_users_telegram_id", metadata.tables["users"].c.telegram_id)

    sa.Table(
        "test_results",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("raw_score", sa.Integer, nullable=False),
        sa.Column("final_score", sa.Float, nullable=False),
        sa.Column("rating", sa.String(50), nullable=False),
        sa.Column("total_time", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_test_results_user_id", ondelete="CASCADE"),
    )

    sa.Table(
        "question_answers",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("test_result_id", sa.Integer, nullable=False),
        sa.Column("question_index", sa.Integer, nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("correct_answer", sa.Text, nullable=True),
        sa.Column("user_answer", sa.Text, nullable=True),
        sa.Column("attempts_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("time_spent", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_correct", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("overtime", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["test_result_id"],
            ["test_results.id"],
            name="fk_question_answers_test_result_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("test_result_id", "question_index", name="uq_test_result_question"),
    )

    sa.Table(
        "auto_messages",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("message_text", sa.Text, nullable=False),
        sa.Column("send_time", sa.String(64), nullable=False),
        sa.Column("target_chat_id", sa.BigInteger, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    sa.Table(
        "notifications",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("admin_chat_id", sa.BigInteger, nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("message_text", sa.Text, nullable=False),
        sa.Column("is_sent", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    sa.Table(
        "bot_message_logs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("candidate_tg_id", sa.BigInteger, nullable=True),
        sa.Column("message_type", sa.String(50), nullable=False),
        sa.Column("slot_id", sa.Integer, nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def upgrade(conn):
    metadata = sa.MetaData()
    _define_tables(metadata)
    metadata.create_all(conn)


def downgrade(conn):  # pragma: no cover - provided for completeness
    metadata = sa.MetaData()
    _define_tables(metadata)
    metadata.drop_all(conn)
