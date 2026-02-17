from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.db import async_session
from backend.core.content_updates import (
    KIND_QUESTIONS_CHANGED,
    publish_content_update,
)
from backend.domain.tests.models import AnswerOption, Question, Test

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


@dataclass(frozen=True)
class QuestionRecord:
    id: int
    title: str
    test_id: str
    question_index: int
    is_active: bool


def _parse_question_payload(payload: str) -> Dict[str, Any]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _question_kind(options_count: int) -> str:
    return "choice" if options_count > 0 else "text"


def _sorted_options(options: List[AnswerOption]) -> List[AnswerOption]:
    return sorted(
        options,
        key=lambda opt: (getattr(opt, "sort_order", 0), getattr(opt, "id", 0)),
    )


def _correct_option_label(options: List[AnswerOption]) -> Optional[str]:
    for opt in _sorted_options(options):
        if getattr(opt, "is_correct", False):
            return str(getattr(opt, "text", ""))
    return None


def _payload_from_question(question: Question, options: List[AnswerOption]) -> Dict[str, Any]:
    data: Dict[str, Any] = dict(getattr(question, "payload", None) or {})

    key = getattr(question, "key", None)
    if key:
        data["id"] = key
        data["prompt"] = getattr(question, "text", "") or ""
    else:
        data["text"] = getattr(question, "text", "") or ""

    if options:
        sorted_opts = _sorted_options(options)
        data["options"] = [str(opt.text or "") for opt in sorted_opts]
        correct_idx = next((idx for idx, opt in enumerate(sorted_opts) if opt.is_correct), None)
        if correct_idx is not None:
            data["correct"] = int(correct_idx)

    return data


async def _ensure_test(session, slug: str) -> Test:
    test = await session.scalar(select(Test).where(Test.slug == slug))
    if test is not None:
        return test
    test = Test(slug=slug, title=TEST_LABELS.get(slug, f"Test {slug}"))
    session.add(test)
    await session.flush()
    return test


async def list_test_questions() -> List[Dict[str, object]]:
    async with async_session() as session:
        tests = (
            await session.scalars(
                select(Test)
                .options(selectinload(Test.questions).selectinload(Question.answer_options))
            )
        ).all()

    grouped: Dict[str, Dict[str, object]] = {}
    for test in tests:
        slug = getattr(test, "slug", None) or ""
        if not slug:
            continue
        group = grouped.setdefault(
            slug,
            {
                "test_id": slug,
                "title": TEST_LABELS.get(slug, getattr(test, "title", None) or slug),
                "questions": [],
            },
        )

        questions = sorted(getattr(test, "questions", []) or [], key=lambda q: getattr(q, "order", 0))
        for q in questions:
            options = list(getattr(q, "answer_options", []) or [])
            index = int(getattr(q, "order", 0)) + 1
            prompt = getattr(q, "text", "") or ""
            title = getattr(q, "title", None) or prompt or f"Вопрос {index}"
            group["questions"].append(
                {
                    "id": q.id,
                    "index": index,
                    "title": title,
                    "prompt": prompt,
                    "kind": _question_kind(len(options)),
                    "options_count": len(options),
                    "correct_label": _correct_option_label(options),
                    "is_active": bool(getattr(q, "is_active", True)),
                    "updated_at": None,
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
        question = await session.scalar(
            select(Question)
            .options(selectinload(Question.answer_options), selectinload(Question.test))
            .where(Question.id == question_id)
        )
        if not question:
            return None
        test = getattr(question, "test", None)
        slug = getattr(test, "slug", None) or ""
        payload = _payload_from_question(question, list(question.answer_options or []))

    pretty = json.dumps(payload or {}, ensure_ascii=False, indent=2, sort_keys=True)
    record = QuestionRecord(
        id=int(question.id),
        title=str(getattr(question, "title", "") or ""),
        test_id=str(slug),
        question_index=int(getattr(question, "order", 0)) + 1,
        is_active=bool(getattr(question, "is_active", True)),
    )
    return {
        "question": record,
        "payload_json": pretty,
        "test_choices": list(TEST_LABELS.items()),
    }


def _normalize_payload_fields(
    data: Dict[str, Any],
    *,
    test_id: str,
) -> Tuple[str, Optional[str], str, List[str], Optional[int], Dict[str, Any]]:
    """Return (resolved_title, key, text, options, correct_idx, extra_payload)."""

    options_raw = data.get("options")
    options: List[str] = []
    if isinstance(options_raw, list):
        options = [str(item) for item in options_raw if item is not None]

    correct_raw = data.get("correct")
    correct_idx: Optional[int] = None
    if isinstance(correct_raw, int):
        correct_idx = correct_raw

    # Question body: accept both keys, prefer the conventional one for the selected test.
    raw_text = ""
    if test_id == "test1":
        raw_text = str(data.get("prompt") or data.get("text") or "")
    else:
        raw_text = str(data.get("text") or data.get("prompt") or "")

    key = data.get("id")
    key_value = None
    if isinstance(key, str) and key.strip():
        key_value = key.strip()

    extra: Dict[str, Any] = {}
    for k, v in data.items():
        if k in {"prompt", "text", "id", "options", "correct"}:
            continue
        extra[k] = v

    return raw_text, key_value, options, correct_idx, extra


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

    clean_test_id = str(test_id or "").strip()
    if not clean_test_id:
        return False, "test_required"
    if int(question_index or 0) < 1:
        return False, "index_required"

    q_text, q_key, options, correct_idx, extra = _normalize_payload_fields(data, test_id=clean_test_id)

    resolved_title = str(title or "").strip() or q_text
    if not resolved_title:
        resolved_title = f"Вопрос {question_index}"
    if not q_text:
        q_text = resolved_title

    order_value = int(question_index) - 1
    q_type = "single_choice" if options else "text"

    async with async_session() as session:
        question = await session.get(Question, question_id)
        if not question:
            return False, "not_found"

        test = await _ensure_test(session, clean_test_id)

        duplicate = await session.scalar(
            select(Question.id).where(
                Question.test_id == test.id,
                Question.order == order_value,
                Question.id != question_id,
            )
        )
        if duplicate:
            return False, "duplicate_index"

        question.test_id = test.id
        question.title = resolved_title
        question.text = q_text
        question.key = q_key
        question.payload = extra or None
        question.type = q_type
        question.order = order_value
        question.is_active = bool(is_active)

        # Replace options for deterministic ordering.
        await session.execute(
            AnswerOption.__table__.delete().where(AnswerOption.question_id == question_id)
        )
        if options:
            for idx, opt_text in enumerate(options):
                is_correct_flag = correct_idx is not None and idx == correct_idx
                session.add(
                    AnswerOption(
                        question_id=question_id,
                        text=str(opt_text),
                        is_correct=bool(is_correct_flag),
                        points=1.0 if is_correct_flag else 0.0,
                        sort_order=int(idx),
                    )
                )

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False, "duplicate_index"

    # Best-effort: notify bot process to refresh question bank without restart.
    await publish_content_update(KIND_QUESTIONS_CHANGED, {"test_id": clean_test_id})

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

    clean_test_id = str(test_id or "").strip()
    if not clean_test_id:
        return False, None, "test_required"

    resolved_index = int(question_index) if question_index is not None else None
    if resolved_index is not None and resolved_index < 1:
        return False, None, "index_required"

    q_text, q_key, options, correct_idx, extra = _normalize_payload_fields(data, test_id=clean_test_id)

    async with async_session() as session:
        test = await _ensure_test(session, clean_test_id)

        if resolved_index is None:
            max_order = await session.scalar(
                select(func.max(Question.order)).where(Question.test_id == test.id)
            )
            new_order = int(max_order or -1) + 1
        else:
            new_order = resolved_index - 1

        duplicate = await session.scalar(
            select(Question.id).where(
                Question.test_id == test.id,
                Question.order == new_order,
            )
        )
        if duplicate:
            return False, None, "duplicate_index"

        resolved_title = str(title or "").strip() or q_text
        if not resolved_title:
            resolved_title = f"Вопрос {new_order + 1}"
        if not q_text:
            q_text = resolved_title

        q_type = "single_choice" if options else "text"

        question = Question(
            test_id=test.id,
            title=resolved_title,
            text=q_text,
            key=q_key,
            payload=extra or None,
            type=q_type,
            order=new_order,
            is_active=bool(is_active),
        )
        session.add(question)
        await session.flush()

        if options:
            for idx, opt_text in enumerate(options):
                is_correct_flag = correct_idx is not None and idx == correct_idx
                session.add(
                    AnswerOption(
                        question_id=question.id,
                        text=str(opt_text),
                        is_correct=bool(is_correct_flag),
                        points=1.0 if is_correct_flag else 0.0,
                        sort_order=int(idx),
                    )
                )

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False, None, "duplicate_index"

    # Best-effort: notify bot process to refresh question bank without restart.
    await publish_content_update(KIND_QUESTIONS_CHANGED, {"test_id": clean_test_id})

    return True, int(question.id), None


async def clone_test_question(question_id: int) -> Tuple[bool, Optional[int], Optional[str]]:
    async with async_session() as session:
        original = await session.scalar(
            select(Question)
            .options(selectinload(Question.answer_options), selectinload(Question.test))
            .where(Question.id == question_id)
        )
        if not original:
            return False, None, "not_found"

        max_order = await session.scalar(
            select(func.max(Question.order)).where(Question.test_id == original.test_id)
        )
        new_order = int(max_order or -1) + 1

        new_title = f"{(original.title or '').strip() or original.text} (копия)"

        new_key = original.key
        if new_key:
            suffix = f"_copy_{new_order + 1}"
            candidate = f"{new_key}{suffix}"
            new_key = candidate[:50]

        clone = Question(
            test_id=original.test_id,
            title=new_title,
            text=original.text,
            key=new_key,
            payload=dict(original.payload or {}) or None,
            type=original.type,
            order=new_order,
            is_active=bool(original.is_active),
        )
        session.add(clone)
        await session.flush()

        original_options = list(getattr(original, "answer_options", []) or [])
        for opt in _sorted_options(original_options):
            session.add(
                AnswerOption(
                    question_id=clone.id,
                    text=str(opt.text or ""),
                    is_correct=bool(opt.is_correct),
                    points=float(opt.points or 0.0),
                    sort_order=int(getattr(opt, "sort_order", 0)),
                )
            )

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False, None, "duplicate_index"

    # Best-effort: notify bot process to refresh question bank without restart.
    await publish_content_update(KIND_QUESTIONS_CHANGED, {"test_id": str(getattr(original.test, "slug", "") or "")})

    return True, int(clone.id), None
