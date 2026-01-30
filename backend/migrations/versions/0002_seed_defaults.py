"""Seed default cities, recruiters and test questions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

import sqlalchemy as sa

from backend.domain.default_data import DEFAULT_CITIES, default_recruiters
# from backend.domain.default_questions import DEFAULT_TEST_QUESTIONS  # DEPRECATED

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
    # test_questions table is deprecated and replaced by tests/questions/answer_options tables

    city_rows = [dict(row, active=row.get("active", True)) for row in DEFAULT_CITIES]
    _ensure_entries(conn, cities, unique_field="name", rows=city_rows)
    recruiter_rows = default_recruiters()
    if recruiter_rows:
        _ensure_entries(conn, recruiters, unique_field="name", rows=recruiter_rows)

    # Legacy test_questions seeding removed.
    # New installs will have empty test_questions table, which is fine as we use new tables.


def downgrade(conn):  # pragma: no cover - provided for completeness
    pass

