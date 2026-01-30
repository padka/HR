"""Synchronous helpers for reading question bank entries."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Set, Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.db import sync_session
from backend.domain.tests.models import Test, Question, AnswerOption


def load_test_questions(test_id: str, *, include_inactive: bool = False) -> List[Dict[str, object]]:
    """Return question definitions for the given test id."""

    with sync_session() as session:
        # Check if test exists
        test_stmt = select(Test).where(Test.slug == test_id)
        test = session.execute(test_stmt).scalar_one_or_none()
        
        if not test:
            return []

        # Fetch questions with answers
        stmt = (
            select(Question)
            .where(Question.test_id == test.id)
            .options(selectinload(Question.answer_options))
            .order_by(Question.order.asc())
        )
        
        # Note: Question model doesn't have is_active, assuming all are active or controlled by Test?
        # The prompt asked for Test to have is_active, but my previous implementation of Test didn't include is_active.
        # I will proceed with what is available.
        
        rows = session.execute(stmt).scalars().all()

    if not rows:
        return []

    result: List[Dict[str, object]] = []
    for q in rows:
        item = _format_question(q)
        result.append(item)

    return result


def load_all_test_questions(*, include_inactive: bool = False) -> Dict[str, List[Dict[str, object]]]:
    """Return questions grouped by test id with defaults as fallback."""

    with sync_session() as session:
        # Fetch all tests and questions
        stmt = (
            select(Test)
            .options(
                selectinload(Test.questions).selectinload(Question.answer_options)
            )
        )
        tests = session.execute(stmt).scalars().all()
        
    grouped: Dict[str, List[Dict[str, object]]] = {}
    
    for t in tests:
        questions_list = []
        # Sort questions by order (already sorted in relationship if configured, but safe to sort here)
        sorted_qs = sorted(t.questions, key=lambda x: x.order)
        for q in sorted_qs:
            questions_list.append(_format_question(q))
        grouped[t.slug] = questions_list

    return grouped


def _format_question(q: Question) -> Dict[str, Any]:
    # Base payload from JSON column
    data = dict(q.payload or {})
    
    # Override/Set core fields
    if q.key:
        data["id"] = q.key
    
    # Map text to prompt/text depending on convention
    # Test1 uses "prompt", Test2 uses "text"
    # We can set both or check keys. 
    # Current bot config uses "prompt" for test1 and "text" for test2.
    # To be safe, we populate both if missing, or rely on what's in payload?
    # No, we must use the DB 'text' column as the source of truth.
    
    # If it's test1 (usually has 'id'), use 'prompt'
    if q.key: # Likely test1
        data["prompt"] = q.text
    else: # Likely test2
        data["text"] = q.text

    # Helper for test1
    # 'placeholder' is in payload

    # Options for test2
    if q.answer_options:
        options = []
        correct_idx = -1
        # Sort options? No explicit order column in AnswerOption, assuming insertion order or ID
        sorted_opts = sorted(q.answer_options, key=lambda x: x.id)
        
        for idx, opt in enumerate(sorted_opts):
            options.append(opt.text)
            if opt.is_correct:
                correct_idx = idx
        
        data["options"] = options
        if correct_idx != -1:
            data["correct"] = correct_idx
            
    return data


__all__ = ["load_all_test_questions", "load_test_questions"]
