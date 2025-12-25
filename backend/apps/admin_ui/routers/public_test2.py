import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.security import get_client_ip, limiter
from backend.apps.admin_ui.services.test2_invites import (
    complete_test2_invite,
    fetch_test2_invite_by_token,
    has_passed_test2,
    is_invite_expired,
    mark_test2_invite_opened,
    mark_test2_invite_expired,
)
from backend.domain.test_questions import load_test_questions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/t/test2", tags=["public-test2"])


async def _load_test2_questions() -> list[dict]:
    return await asyncio.to_thread(load_test_questions, "test2")


def _parse_answers(form: Dict[str, str], total: int) -> Dict[int, int]:
    answers: Dict[int, int] = {}
    for idx in range(1, total + 1):
        raw = form.get(f"q_{idx}")
        if raw is None:
            continue
        try:
            answers[idx] = int(raw)
        except ValueError:
            continue
    return answers


@router.get("/{token}", response_class=HTMLResponse)
@limiter.limit("120/minute", key_func=get_client_ip)
async def test2_public_form(request: Request, token: str) -> HTMLResponse:
    invite = await fetch_test2_invite_by_token(token, with_user=True)
    now = datetime.now(timezone.utc)
    status = "active"
    if not invite:
        status = "invalid"
    elif invite.status in {"completed", "revoked"}:
        status = invite.status
    elif is_invite_expired(invite, now):
        status = "expired"
        await mark_test2_invite_expired(invite.id)
        invite.status = "expired"
    elif invite.status == "created":
        await mark_test2_invite_opened(invite.id)
        invite.status = "opened"
        invite.opened_at = now

    questions = []
    if status == "active":
        try:
            questions = await _load_test2_questions()
        except Exception as exc:
            logger.warning("Failed to load Test2 questions: %s", exc)
            status = "error"

        if not questions:
            status = "no_questions"

    context = {
        "request": request,
        "invite": invite,
        "candidate": invite.user if invite else None,
        "questions": questions,
        "status": status,
    }
    return templates.TemplateResponse(request, "test2_public.html", context)


@router.post("/{token}", response_class=HTMLResponse)
@limiter.limit("20/minute", key_func=get_client_ip)
async def test2_public_submit(request: Request, token: str) -> HTMLResponse:
    try:
        questions = await _load_test2_questions()
    except Exception as exc:
        logger.warning("Failed to load Test2 questions: %s", exc)
        return templates.TemplateResponse(
            request,
            "test2_public_result.html",
            {
                "request": request,
                "status": "error",
            },
        )

    form = dict(await request.form())
    answers = _parse_answers(form, len(questions))
    if len(answers) < len(questions):
        invite = await fetch_test2_invite_by_token(token, with_user=True)
        return templates.TemplateResponse(
            request,
            "test2_public.html",
            {
                "request": request,
                "invite": invite,
                "candidate": invite.user if invite else None,
                "questions": questions,
                "status": "active",
                "form_error": "Ответьте на все вопросы перед отправкой.",
            },
        )

    status, test_result, candidate = await complete_test2_invite(
        token, questions=questions, answers=answers
    )
    passed = False
    if test_result:
        passed = has_passed_test2(test_result.raw_score, len(questions))

    context = {
        "request": request,
        "status": status,
        "candidate": candidate,
        "result": test_result,
        "passed": passed,
        "total_questions": len(questions),
    }
    return templates.TemplateResponse("test2_public_result.html", context)


__all__ = ["router"]
