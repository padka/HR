"""Sync legacy test1 questions with current bot question bank."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0083_sync_test1_question_bank"
down_revision = "0082_add_calendar_tasks"
branch_labels = None
depends_on = None

TEST1_KEYS_BY_ORDER = {
    0: "fio",
    1: "city",
    2: "age",
    3: "status",
    4: "salary",
    5: "format",
    6: "sales_exp",
    7: "about",
    8: "skills",
    9: "expectations",
}

TEST1_OPTIONS_BY_ORDER = {
    3: [
        "Учусь",
        "Работаю",
        "Ищу работу",
        "Предприниматель",
        "Другое",
    ],
    4: [
        "до 60 000 ›",
        "60 000 – 90 000 ›",
        "90 000 – 120 000 ›",
        "120 000+ ›",
        "Обсудим индивидуально",
    ],
    5: [
        "Да, готов",
        "Нужен гибкий график",
        "Пока не готов",
    ],
}


def _load_test1_question_ids(conn: Connection) -> dict[int, int]:
    row = conn.execute(sa.text("SELECT id FROM tests WHERE slug = :slug"), {"slug": "test1"}).first()
    if not row:
        return {}
    test_id = int(row[0])
    rows = conn.execute(
        sa.text(
            'SELECT id, "order" FROM questions WHERE test_id = :test_id ORDER BY "order" ASC, id ASC'
        ),
        {"test_id": test_id},
    ).fetchall()
    return {int(order): int(question_id) for question_id, order in rows}


def _sync_question_key(conn: Connection, question_id: int, key: str) -> None:
    conn.execute(
        sa.text(
            """
            UPDATE questions
               SET key = :key
             WHERE id = :question_id
               AND COALESCE(key, '') <> :key
            """
        ),
        {"question_id": question_id, "key": key},
    )


def _load_option_texts(conn: Connection, question_id: int) -> list[str]:
    rows = conn.execute(
        sa.text(
            """
            SELECT text
              FROM answer_options
             WHERE question_id = :question_id
             ORDER BY sort_order ASC, id ASC
            """
        ),
        {"question_id": question_id},
    ).fetchall()
    return [str(item[0]) for item in rows]


def _replace_options(conn: Connection, question_id: int, options: list[str]) -> None:
    existing = _load_option_texts(conn, question_id)
    if existing == options:
        return

    conn.execute(
        sa.text("DELETE FROM answer_options WHERE question_id = :question_id"),
        {"question_id": question_id},
    )
    for idx, text in enumerate(options):
        conn.execute(
            sa.text(
                """
                INSERT INTO answer_options (question_id, text, is_correct, points, sort_order)
                VALUES (:question_id, :text, :is_correct, :points, :sort_order)
                """
            ),
            {
                "question_id": question_id,
                "text": text,
                "is_correct": False,
                "points": 0.0,
                "sort_order": idx,
            },
        )


def upgrade(conn: Connection) -> None:
    questions_by_order = _load_test1_question_ids(conn)
    if not questions_by_order:
        return

    for order, key in TEST1_KEYS_BY_ORDER.items():
        question_id = questions_by_order.get(order)
        if question_id is None:
            continue
        _sync_question_key(conn, question_id, key)

    for order, options in TEST1_OPTIONS_BY_ORDER.items():
        question_id = questions_by_order.get(order)
        if question_id is None:
            continue
        _replace_options(conn, question_id, options)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    # Data synchronization migration; downgrade is intentionally a no-op.
    return
