"""Unify legacy test_questions with tests/questions/answer_options schema.

Adds missing columns required by the admin UI (title/is_active) and introduces
deterministic ordering for answer options (sort_order). If legacy test_questions
data exists, it is migrated into the new tables (upserting by test slug and
question_index).
"""

from __future__ import annotations

import json
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, table_exists

revision = "0073_unify_test_question_sources"
down_revision = "0072_add_bot_runtime_configs"
branch_labels = None
depends_on = None


_TEST_TITLES = {
    "test1": "Анкета кандидата",
    "test2": "Инфо-тест",
}


def _bool_default(conn: Connection, *, value: bool) -> str:
    if conn.dialect.name == "postgresql":
        return "TRUE" if value else "FALSE"
    # SQLite uses integer affinity for BOOLEAN
    return "1" if value else "0"


def _parse_payload(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def upgrade(conn: Connection) -> None:
    if table_exists(conn, "questions"):
        if not column_exists(conn, "questions", "title"):
            conn.execute(
                sa.text("ALTER TABLE questions ADD COLUMN title VARCHAR(255) NOT NULL DEFAULT ''")
            )
        if not column_exists(conn, "questions", "is_active"):
            conn.execute(
                sa.text(
                    "ALTER TABLE questions ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT "
                    + _bool_default(conn, value=True)
                )
            )
        # Backfill title for existing rows created before the column existed.
        conn.execute(
            sa.text(
                "UPDATE questions SET title = COALESCE(NULLIF(title, ''), text) "
                "WHERE title = '' OR title IS NULL"
            )
        )

    if table_exists(conn, "answer_options") and not column_exists(conn, "answer_options", "sort_order"):
        conn.execute(
            sa.text(
                "ALTER TABLE answer_options ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
            )
        )

        # Deterministic ordering for existing options: order by id within question_id.
        rows = conn.execute(
            sa.text("SELECT id, question_id FROM answer_options ORDER BY question_id, id")
        ).fetchall()
        current_qid: Optional[int] = None
        sort_order = -1
        for row_id, question_id in rows:
            if question_id != current_qid:
                current_qid = question_id
                sort_order = -1
            sort_order += 1
            conn.execute(
                sa.text("UPDATE answer_options SET sort_order = :sort_order WHERE id = :id"),
                {"sort_order": int(sort_order), "id": int(row_id)},
            )

    # Migrate legacy data if present.
    if not (table_exists(conn, "test_questions") and table_exists(conn, "tests") and table_exists(conn, "questions")):
        return

    meta = sa.MetaData()
    tests_t = sa.Table("tests", meta, autoload_with=conn)
    questions_t = sa.Table("questions", meta, autoload_with=conn)
    answer_t = sa.Table("answer_options", meta, autoload_with=conn)
    legacy_t = sa.Table("test_questions", meta, autoload_with=conn)

    test_id_map: dict[str, int] = {
        str(slug): int(tid)
        for tid, slug in conn.execute(sa.select(tests_t.c.id, tests_t.c.slug)).fetchall()
    }

    legacy_rows = conn.execute(
        sa.select(
            legacy_t.c.test_id,
            legacy_t.c.question_index,
            legacy_t.c.title,
            legacy_t.c.payload,
            legacy_t.c.is_active,
        ).order_by(legacy_t.c.test_id.asc(), legacy_t.c.question_index.asc())
    ).fetchall()

    for test_slug, question_index, legacy_title, legacy_payload, legacy_active in legacy_rows:
        slug = str(test_slug or "").strip()
        if not slug:
            continue

        test_fk = test_id_map.get(slug)
        if test_fk is None:
            conn.execute(
                tests_t.insert().values(
                    slug=slug,
                    title=_TEST_TITLES.get(slug, f"Test {slug}"),
                )
            )
            test_fk = conn.execute(
                sa.select(tests_t.c.id).where(tests_t.c.slug == slug)
            ).scalar_one()
            test_id_map[slug] = int(test_fk)

        payload = _parse_payload(str(legacy_payload or ""))
        q_text = payload.get("prompt") or payload.get("text") or legacy_title or ""
        q_text = str(q_text or "")

        q_key = payload.get("id")
        q_key = str(q_key).strip() if isinstance(q_key, str) and q_key.strip() else None

        options = payload.get("options")
        options_list: list[str] = []
        if isinstance(options, list):
            options_list = [str(item) for item in options if item is not None]

        correct_raw = payload.get("correct")
        correct_idx: Optional[int] = None
        if isinstance(correct_raw, int):
            correct_idx = correct_raw

        q_type = "single_choice" if options_list else "text"

        # Store only "extra" keys in JSON payload; core fields are in columns.
        extra: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"prompt", "text", "id", "options", "correct"}:
                continue
            extra[key] = value

        q_title = str(legacy_title or "").strip() or q_text or f"Вопрос {question_index}"

        idx_value = int(question_index or 1)
        order_value = max(idx_value - 1, 0)

        existing_qid = conn.execute(
            sa.select(questions_t.c.id).where(
                questions_t.c.test_id == int(test_fk),
                questions_t.c.order == order_value,
            )
        ).scalar_one_or_none()

        values = {
            "test_id": int(test_fk),
            "title": q_title,
            "text": q_text,
            "key": q_key,
            "payload": extra or None,
            "type": q_type,
            "order": order_value,
            "is_active": bool(legacy_active) if legacy_active is not None else True,
        }

        if existing_qid is None:
            res = conn.execute(questions_t.insert().values(values))
            qid = res.inserted_primary_key[0]
        else:
            qid = int(existing_qid)
            conn.execute(
                questions_t.update().where(questions_t.c.id == qid).values(values)
            )
            conn.execute(answer_t.delete().where(answer_t.c.question_id == qid))

        if options_list:
            for idx, opt_text in enumerate(options_list):
                is_correct = correct_idx is not None and idx == correct_idx
                conn.execute(
                    answer_t.insert().values(
                        question_id=int(qid),
                        text=str(opt_text),
                        is_correct=bool(is_correct),
                        points=1.0 if is_correct else 0.0,
                        sort_order=int(idx),
                    )
                )


def downgrade(conn: Connection) -> None:
    # Keep downgrade minimal: the legacy table still exists and app can fall back to defaults.
    if table_exists(conn, "answer_options") and column_exists(conn, "answer_options", "sort_order"):
        # SQLite can't drop columns; keep them.
        if conn.dialect.name == "postgresql":
            conn.execute(sa.text("ALTER TABLE answer_options DROP COLUMN sort_order"))
    if table_exists(conn, "questions"):
        if conn.dialect.name == "postgresql":
            if column_exists(conn, "questions", "is_active"):
                conn.execute(sa.text("ALTER TABLE questions DROP COLUMN is_active"))
            if column_exists(conn, "questions", "title"):
                conn.execute(sa.text("ALTER TABLE questions DROP COLUMN title"))

