from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
import json

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import Connection


revision = "0017_create_interview_feedback_table"
down_revision = "0016_add_slot_interview_feedback"
branch_labels = None
depends_on = None


def _table_exists(conn: Connection, table_name: str) -> bool:
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _normalize_checklist(raw: Any) -> Dict[str, bool]:
    if isinstance(raw, dict):
        return {str(key): bool(value) for key, value in raw.items()}
    return {}


def _normalize_notes(raw: Any) -> str | None:
    if isinstance(raw, str):
        value = raw.strip()
        return value or None
    return None


def _normalize_timestamp(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def upgrade(conn: Connection) -> None:
    if not _table_exists(conn, "interview_feedback"):
        conn.execute(
            sa.text(
                """
                CREATE TABLE interview_feedback (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
                    checklist JSON NOT NULL DEFAULT '{}'::json,
                    notes TEXT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_interview_feedback_slot UNIQUE(slot_id)
                )
                """
            )
        )

    if _column_exists(conn, "slots", "interview_feedback"):
        result = conn.execute(
            sa.text(
                """
                SELECT s.id AS slot_id, u.id AS user_id, s.interview_feedback
                FROM slots AS s
                JOIN users AS u ON u.telegram_id = s.candidate_tg_id
                WHERE s.interview_feedback IS NOT NULL
                """
            )
        )
        rows = result.fetchall()
        for row in rows:
            payload = row.interview_feedback
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except ValueError:
                    payload = None
            if not payload:
                continue
            checklist = _normalize_checklist(payload.get("checklist") if isinstance(payload, dict) else None)
            notes = _normalize_notes(payload.get("notes") if isinstance(payload, dict) else None)
            updated_at = _normalize_timestamp(
                payload.get("updated_at") if isinstance(payload, dict) else None
            )
            conn.execute(
                sa.text(
                    """
                    INSERT INTO interview_feedback (user_id, slot_id, checklist, notes, updated_at)
                    VALUES (:user_id, :slot_id, :checklist, :notes, :updated_at)
                    ON CONFLICT (slot_id) DO UPDATE SET
                        checklist = EXCLUDED.checklist,
                        notes = EXCLUDED.notes,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "user_id": row.user_id,
                    "slot_id": row.slot_id,
                    "checklist": checklist,
                    "notes": notes,
                    "updated_at": updated_at,
                },
            )


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry with upgrade
    if _table_exists(conn, "interview_feedback"):
        conn.execute(sa.text("DROP TABLE interview_feedback"))
