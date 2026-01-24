from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.domain.models import TestQuestion

__all__ = [
    "list_test_questions",
    "get_test_question_detail",
    "update_test_question",
    "create_test_question",
    "clone_test_question",
]


TEST_LABELS = {
    "test1": "Анкета кандидата",
    "test2": "Инфо-тест",
}


def _parse_question_payload(payload: str) -> Dict[str, object]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _question_kind(data: Dict[str, object]) -> str:
    options = data.get("options")
    if isinstance(options, list) and options:
        return "choice"
    return "text"


def _correct_option_label(data: Dict[str, object]) -> Optional[str]:
    options = data.get("options")
    correct = data.get("correct")
    if isinstance(options, list) and isinstance(correct, int):
        if 0 <= correct < len(options):
            return str(options[correct])
    return None


async def list_test_questions() -> List[Dict[str, object]]:
    async with async_session() as session:
        items = (
            await session.scalars(
                select(TestQuestion).order_by(TestQuestion.test_id.asc(), TestQuestion.question_index.asc())
            )
        ).all()

    grouped: Dict[str, Dict[str, object]] = {}
    for item in items:
        data = _parse_question_payload(item.payload)
        grouped.setdefault(
            item.test_id,
            {
                "test_id": item.test_id,
                "title": TEST_LABELS.get(item.test_id, item.test_id),
                "questions": [],
            },
        )["questions"].append(
            {
                "id": item.id,
                "index": item.question_index,
                "title": item.title,
                "prompt": data.get("prompt") or data.get("text") or item.title,
                "kind": _question_kind(data),
                "options_count": len(data.get("options") or []),
                "correct_label": _correct_option_label(data),
                "is_active": item.is_active,
                "updated_at": item.updated_at,
            }
        )

    ordered: List[Dict[str, object]] = []
    known_order = list(TEST_LABELS.keys())
    extra_ids = [tid for tid in grouped.keys() if tid not in known_order]
    for test_id in [*known_order, *sorted(extra_ids)]:
        if test_id not in grouped:
            continue
        questions = sorted(grouped[test_id]["questions"], key=lambda q: q["index"])
        grouped[test_id]["questions"] = questions
        ordered.append(grouped[test_id])

    return ordered


async def get_test_question_detail(question_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        question = await session.get(TestQuestion, question_id)
        if not question:
            return None

    data = _parse_question_payload(question.payload)
    pretty = json.dumps(data or {}, ensure_ascii=False, indent=2, sort_keys=True)
    return {
        "question": question,
        "payload_json": pretty,
        "test_choices": list(TEST_LABELS.items()),
    }


async def update_test_question(
    question_id: int,
    *,
    title: str,
    test_id: str,
    question_index: int,
    payload: str,
    is_active: bool,
) -> Tuple[bool, Optional[str]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return False, "invalid_json"

    if not isinstance(data, dict):
        return False, "invalid_json"

    normalized_payload = json.dumps(data, ensure_ascii=False)
    resolved_title = title.strip() or data.get("prompt") or data.get("text")
    if not resolved_title:
        resolved_title = f"Вопрос {question_index}"

    clean_test_id = test_id.strip()
    if not clean_test_id:
        return False, "test_required"

    async with async_session() as session:
        question = await session.get(TestQuestion, question_id)
        if not question:
            return False, "not_found"

        question.title = resolved_title
        question.test_id = clean_test_id
        question.question_index = question_index
        question.payload = normalized_payload
        question.is_active = is_active
        question.updated_at = datetime.now(timezone.utc)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False, "duplicate_index"

    # Keep the in-process bot question bank in sync with admin edits.
    try:
        from backend.apps.bot.config import refresh_questions_bank

        refresh_questions_bank()
    except Exception:
        # Best-effort: the bot will fall back to defaults if refresh fails.
        pass

    return True, None


async def create_test_question(
    *,
    title: str,
    test_id: str,
    question_index: Optional[int],
    payload: str,
    is_active: bool,
) -> Tuple[bool, Optional[int], Optional[str]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return False, None, "invalid_json"

    if not isinstance(data, dict):
        return False, None, "invalid_json"

    clean_test_id = test_id.strip()
    if not clean_test_id:
        return False, None, "test_required"

    resolved_index = question_index
    if resolved_index is not None and resolved_index < 1:
        return False, None, "index_required"

    resolved_title = title.strip() or data.get("prompt") or data.get("text")

    async with async_session() as session:
        if resolved_index is None:
            max_index = await session.scalar(
                select(func.max(TestQuestion.question_index)).where(TestQuestion.test_id == clean_test_id)
            )
            resolved_index = (max_index or 0) + 1
        if not resolved_title:
            resolved_title = f"Вопрос {resolved_index}"

        normalized_payload = json.dumps(data, ensure_ascii=False)
        question = TestQuestion(
            title=resolved_title,
            test_id=clean_test_id,
            question_index=resolved_index,
            payload=normalized_payload,
            is_active=is_active,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(question)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False, None, "duplicate_index"

    try:
        from backend.apps.bot.config import refresh_questions_bank

        refresh_questions_bank()
    except Exception:
        pass

    return True, question.id, None


async def clone_test_question(question_id: int) -> Tuple[bool, Optional[int], Optional[str]]:
    async with async_session() as session:
        original = await session.get(TestQuestion, question_id)
        if not original:
            return False, None, "not_found"

        max_index = await session.scalar(
            select(func.max(TestQuestion.question_index)).where(TestQuestion.test_id == original.test_id)
        )
        new_index = (max_index or 0) + 1
        title = f"{original.title} (копия)"
        clone = TestQuestion(
            title=title,
            test_id=original.test_id,
            question_index=new_index,
            payload=original.payload,
            is_active=original.is_active,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(clone)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False, None, "duplicate_index"

    try:
        from backend.apps.bot.config import refresh_questions_bank

        refresh_questions_bank()
    except Exception:
        pass

    return True, clone.id, None
