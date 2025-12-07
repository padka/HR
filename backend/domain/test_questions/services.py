"""Synchronous helpers for reading question bank entries."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Dict, List, Set

from sqlalchemy import select

from backend.core.db import sync_session
from backend.domain.default_questions import DEFAULT_TEST_QUESTIONS
from backend.domain.models import TestQuestion


def _parse_payload(payload: str) -> Dict[str, object]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def load_test_questions(test_id: str, *, include_inactive: bool = False) -> List[Dict[str, object]]:
    """Return question definitions for the given test id."""

    with sync_session() as session:
        query = select(TestQuestion).where(TestQuestion.test_id == test_id)
        if not include_inactive:
            query = query.where(TestQuestion.is_active.is_(True))
        query = query.order_by(TestQuestion.question_index.asc())
        rows = session.execute(query).scalars().all()

        # Detect if this test id exists in DB at all to decide on fallback.
        has_any = session.execute(
            select(TestQuestion.id).where(TestQuestion.test_id == test_id)
        ).first() is not None

    if not rows and not has_any:
        return deepcopy(DEFAULT_TEST_QUESTIONS.get(test_id, []))

    result: List[Dict[str, object]] = []
    for row in rows:
        data = _parse_payload(row.payload)
        if data:
            data = dict(data)
            data.setdefault("id", f"{row.test_id}_{row.question_index}")
            result.append(data)

    return result


def load_all_test_questions(*, include_inactive: bool = False) -> Dict[str, List[Dict[str, object]]]:
    """Return questions grouped by test id with defaults as fallback."""

    with sync_session() as session:
        query = select(TestQuestion)
        if not include_inactive:
            query = query.where(TestQuestion.is_active.is_(True))
        query = query.order_by(TestQuestion.test_id.asc(), TestQuestion.question_index.asc())
        rows = session.execute(query).scalars().all()

        # Track which tests exist in DB regardless of active flag.
        db_test_ids: Set[str] = set(
            id_row[0] for id_row in session.execute(select(TestQuestion.test_id).distinct()).all()
        )

    grouped: Dict[str, List[Dict[str, object]]] = {}
    for row in rows:
        data = _parse_payload(row.payload)
        if not data:
            continue
        data = dict(data)
        data.setdefault("id", f"{row.test_id}_{row.question_index}")
        grouped.setdefault(row.test_id, []).append(data)

    for test_id, defaults in DEFAULT_TEST_QUESTIONS.items():
        # Only fallback to defaults if the test is entirely absent from DB.
        if test_id not in db_test_ids and not grouped.get(test_id):
            grouped[test_id] = deepcopy(defaults)

    return grouped


__all__ = ["load_all_test_questions", "load_test_questions"]
