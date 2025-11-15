from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.apps.admin_ui.config import templates as jinja_templates
from backend.apps.admin_ui.services.questions import (
    get_test_question_detail,
    list_test_questions,
    update_test_question,
)
from backend.apps.admin_ui.utils import parse_optional_int


router = APIRouter(prefix="/questions", tags=["questions"])


ERROR_MESSAGES = {
    "invalid_json": "Не удалось разобрать JSON с данными вопроса.",
    "duplicate_index": "Для выбранного теста уже существует вопрос с таким порядковым номером.",
    "test_required": "Укажите идентификатор теста.",
    "index_required": "Укажите порядковый номер (целое число).",
}


@router.get("", response_class=HTMLResponse)
async def questions_list(request: Request):
    tests = await list_test_questions()
    context = {
        "request": request,
        "tests": tests,
    }
    return jinja_templates.TemplateResponse(request, "questions_list.html", context)


@router.get("/{question_id}/edit", response_class=HTMLResponse)
async def questions_edit(request: Request, question_id: int):
    detail = await get_test_question_detail(question_id)
    if not detail:
        return RedirectResponse(url="/questions", status_code=303)

    error_code = request.query_params.get("err")
    context = {
        "request": request,
        "detail": detail,
        "error_message": ERROR_MESSAGES.get(error_code),
    }
    return jinja_templates.TemplateResponse(request, "questions_edit.html", context)


@router.post("/{question_id}/update")
async def questions_update(
    question_id: int,
    title: str = Form(""),
    test_id: str = Form(...),
    question_index: str = Form(...),
    payload: str = Form(...),
    is_active: Optional[str] = Form(None),
):
    index_value = parse_optional_int(question_index)
    if index_value is None or index_value < 1:
        return RedirectResponse(url=f"/questions/{question_id}/edit?err=index_required", status_code=303)

    success, error = await update_test_question(
        question_id,
        title=title,
        test_id=test_id,
        question_index=index_value,
        payload=payload,
        is_active=bool(is_active),
    )
    if not success:
        return RedirectResponse(url=f"/questions/{question_id}/edit?err={error}", status_code=303)

    return RedirectResponse(url="/questions", status_code=303)


__all__ = ["router"]
