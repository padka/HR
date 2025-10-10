"""Seed default cities, recruiters and test questions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

import sqlalchemy as sa

from backend.domain.default_data import DEFAULT_CITIES, default_recruiters
from backend.domain.default_questions import DEFAULT_TEST_QUESTIONS

revision = "0002_seed_defaults"
down_revision = "0001_initial_schema"


def _table(name: str, *columns: sa.Column) -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(name, metadata, *columns)


def _ensure_entries(conn: sa.Connection, table: sa.Table, *, unique_field: str, rows: Iterable[Dict[str, Any]]) -> None:
    for row in rows:
        exists = conn.execute(
            sa.select(sa.literal(1)).select_from(table).where(table.c[unique_field] == row[unique_field])
        ).scalar()
        if exists:
            continue
        conn.execute(sa.insert(table).values(**row))


def upgrade(conn):
    cities = _table(
        "cities",
        sa.Column("id", sa.Integer),
        sa.Column("name", sa.String),
        sa.Column("tz", sa.String),
        sa.Column("active", sa.Boolean),
    )
    recruiters = _table(
        "recruiters",
        sa.Column("id", sa.Integer),
        sa.Column("name", sa.String),
        sa.Column("tz", sa.String),
        sa.Column("telemost_url", sa.String),
        sa.Column("active", sa.Boolean),
    )
    test_questions = _table(
        "test_questions",
        sa.Column("id", sa.Integer),
        sa.Column("test_id", sa.String),
        sa.Column("question_index", sa.Integer),
        sa.Column("title", sa.String),
        sa.Column("payload", sa.Text),
        sa.Column("is_active", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    _ensure_entries(conn, cities, unique_field="name", rows=DEFAULT_CITIES)
    recruiter_rows = default_recruiters()
    if recruiter_rows:
        _ensure_entries(conn, recruiters, unique_field="name", rows=recruiter_rows)

    existing_questions = conn.execute(sa.select(sa.func.count()).select_from(test_questions)).scalar()
    if existing_questions:
        return

    for test_id, questions in DEFAULT_TEST_QUESTIONS.items():
        for idx, question in enumerate(questions, start=1):
            title = question.get("prompt") or question.get("text") or f"Вопрос {idx}"
            conn.execute(
                sa.insert(test_questions).values(
                    test_id=test_id,
                    question_index=idx,
                    title=title,
                    payload=json.dumps(question, ensure_ascii=False),
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )


def downgrade(conn):  # pragma: no cover - provided for completeness
    test_questions = _table(
        "test_questions",
        sa.Column("test_id", sa.String),
    )
    conn.execute(
        sa.delete(test_questions).where(test_questions.c.test_id.in_(list(DEFAULT_TEST_QUESTIONS.keys())))
    )
