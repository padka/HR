"""FastAPI routers for Recruiter Telegram Mini App.

Secured with Telegram initData validation + recruiter check.
Endpoints are mounted under /api/webapp/recruiter/.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.apps.admin_api.webapp.auth import TelegramUser, get_telegram_webapp_auth
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webapp-recruiter"])


# ---------------------------------------------------------------------------
# Auth dependency: validates initData + ensures user is a recruiter
# ---------------------------------------------------------------------------


async def _get_recruiter_for_tg_user(tg_user: TelegramUser) -> Any:
    """Look up the recruiter record by Telegram user_id."""
    from backend.apps.bot.services import get_recruiter_by_chat_id

    recruiter = await get_recruiter_by_chat_id(tg_user.user_id)
    if recruiter is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ваш Telegram не привязан к рекрутёру. Используйте /iam в боте.",
        )
    return recruiter


async def get_recruiter_webapp_auth(
    tg_user: TelegramUser = Depends(get_telegram_webapp_auth()),
) -> Dict[str, Any]:
    """Combined dependency: validate initData + resolve recruiter."""
    recruiter = await _get_recruiter_for_tg_user(tg_user)
    return {"tg_user": tg_user, "recruiter": recruiter}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class DashboardResponse(BaseModel):
    waiting_candidates_total: int = 0
    scheduled_today: int = 0
    free_slots: int = 0
    recruiter_name: str = ""


class CandidateItem(BaseModel):
    id: int
    fio: str
    city: Optional[str] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    waiting_hours: Optional[float] = None
    telegram_id: Optional[int] = None


class IncomingResponse(BaseModel):
    candidates: List[CandidateItem] = []
    total: int = 0


class CandidateDetailResponse(BaseModel):
    id: int
    fio: str
    city: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    telegram_id: Optional[int] = None
    transitions: List[Dict[str, str]] = []


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status slug")


class MessageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class NoteRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class SuccessResponse(BaseModel):
    ok: bool = True
    message: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardResponse)
async def recruiter_dashboard(
    auth: Dict[str, Any] = Depends(get_recruiter_webapp_auth),
) -> DashboardResponse:
    """KPI dashboard for the recruiter Mini App."""
    recruiter = auth["recruiter"]

    from backend.apps.admin_ui.services.dashboard import dashboard_counts
    from backend.apps.admin_ui.security import Principal

    principal = Principal(type="recruiter", id=recruiter.id)
    counts = await dashboard_counts(principal=principal)

    return DashboardResponse(
        waiting_candidates_total=int(counts.get("waiting_candidates_total", 0)),
        scheduled_today=int(counts.get("scheduled_today", 0)),
        free_slots=int(counts.get("free_slots_total", 0)),
        recruiter_name=getattr(recruiter, "name", ""),
    )


@router.get("/incoming", response_model=IncomingResponse)
async def recruiter_incoming(
    limit: int = Query(20, ge=1, le=100),
    auth: Dict[str, Any] = Depends(get_recruiter_webapp_auth),
) -> IncomingResponse:
    """Incoming candidates waiting for slot assignment."""
    recruiter = auth["recruiter"]

    from backend.apps.admin_ui.services.dashboard import get_waiting_candidates
    from backend.domain.candidates.status import STATUS_LABELS, CandidateStatus
    from backend.apps.admin_ui.security import Principal

    principal = Principal(type="recruiter", id=recruiter.id)
    raw = await get_waiting_candidates(limit=limit, principal=principal)

    items = []
    for c in raw:
        status_slug = c.get("status", "")
        label = ""
        try:
            label = STATUS_LABELS.get(CandidateStatus(status_slug), status_slug) if status_slug else ""
        except (ValueError, KeyError):
            label = status_slug

        items.append(CandidateItem(
            id=c.get("id", 0),
            fio=c.get("name", c.get("fio", "—")),
            city=c.get("city"),
            status=status_slug,
            status_label=label,
            waiting_hours=c.get("waiting_hours"),
            telegram_id=c.get("telegram_id"),
        ))

    return IncomingResponse(candidates=items, total=len(items))


@router.get("/candidates/{candidate_id}", response_model=CandidateDetailResponse)
async def recruiter_candidate_detail(
    candidate_id: int,
    auth: Dict[str, Any] = Depends(get_recruiter_webapp_auth),
) -> CandidateDetailResponse:
    """Full candidate detail for the Mini App."""
    recruiter = auth["recruiter"]
    from backend.core.db import async_session
    from backend.apps.admin_ui.services.recruiter_access import get_candidate_for_recruiter
    from backend.domain.candidates.status import (
        STATUS_LABELS,
        CandidateStatus,
        get_next_statuses,
    )

    async with async_session() as session:
        candidate = await get_candidate_for_recruiter(candidate_id, recruiter, session=session, detach=True)

    if candidate is None:
        raise HTTPException(status_code=404, detail="Кандидат не найден")

    current = candidate.candidate_status
    current_label = STATUS_LABELS.get(current, str(current)) if current else "Нет статуса"

    transitions = []
    for target, label in get_next_statuses(current):
        transitions.append({"status": target.value, "label": label})

    return CandidateDetailResponse(
        id=candidate.id,
        fio=candidate.fio,
        city=candidate.city,
        phone=candidate.phone,
        status=current.value if current else None,
        status_label=current_label,
        telegram_id=candidate.telegram_id,
        transitions=transitions,
    )


@router.post("/candidates/{candidate_id}/status", response_model=SuccessResponse)
async def recruiter_update_status(
    candidate_id: int,
    body: StatusUpdateRequest,
    auth: Dict[str, Any] = Depends(get_recruiter_webapp_auth),
) -> SuccessResponse:
    """Update candidate status from the Mini App."""
    recruiter = auth["recruiter"]
    from backend.core.db import async_session
    from backend.apps.admin_ui.services.recruiter_access import get_candidate_for_recruiter
    from backend.domain.candidate_status_service import (
        CandidateStatusService,
        CandidateStatusTransitionError,
    )
    from backend.domain.candidates.status import CandidateStatus, STATUS_LABELS

    try:
        target_status = CandidateStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неизвестный статус")

    async with async_session() as session:
        candidate = await get_candidate_for_recruiter(candidate_id, recruiter, session=session)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Кандидат не найден")

        svc = CandidateStatusService()
        try:
            await svc.advance(candidate, target_status)
        except CandidateStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        await session.commit()

    new_label = STATUS_LABELS.get(target_status, body.status)
    return SuccessResponse(message=f"Статус обновлён: {new_label}")


@router.post("/candidates/{candidate_id}/message", response_model=SuccessResponse)
async def recruiter_send_message(
    candidate_id: int,
    body: MessageRequest,
    auth: Dict[str, Any] = Depends(get_recruiter_webapp_auth),
    bot_service: BotService = Depends(provide_bot_service),
) -> SuccessResponse:
    """Send a candidate message from the Mini App using the candidate's active channel."""
    recruiter = auth["recruiter"]
    from backend.apps.admin_ui.services.recruiter_access import get_candidate_for_recruiter
    from backend.apps.admin_ui.services.chat import send_chat_message

    candidate = await get_candidate_for_recruiter(candidate_id, recruiter, detach=True)

    if candidate is None:
        raise HTTPException(status_code=404, detail="Кандидат не найден")

    result = await send_chat_message(
        candidate.id,
        text=body.text,
        client_request_id=None,
        author_label=getattr(recruiter, "name", None) or "Рекрутер",
        bot_service=bot_service,
    )
    if str(result.get("status") or "").lower() == "failed":
        raise HTTPException(status_code=502, detail="Не удалось отправить сообщение")

    return SuccessResponse(message="Сообщение отправлено")


@router.post("/candidates/{candidate_id}/notes", response_model=SuccessResponse)
async def recruiter_save_note(
    candidate_id: int,
    body: NoteRequest,
    auth: Dict[str, Any] = Depends(get_recruiter_webapp_auth),
) -> SuccessResponse:
    """Persist a recruiter quick note for a candidate."""
    recruiter = auth["recruiter"]
    from backend.apps.admin_ui.services.recruiter_access import get_candidate_for_recruiter
    from backend.core.db import async_session
    from backend.domain.candidates.models import InterviewNote

    candidate = await get_candidate_for_recruiter(candidate_id, recruiter, detach=True)

    if candidate is None:
        raise HTTPException(status_code=404, detail="Кандидат не найден")

    now = datetime.now(timezone.utc)
    author = (getattr(recruiter, "name", None) or "").strip() or None
    async with async_session() as session:
        note = (
            await session.execute(
                select(InterviewNote).where(InterviewNote.user_id == candidate.id)
            )
        ).scalar_one_or_none()

        payload = dict(note.data or {}) if note else {}
        quick_notes = list(payload.get("recruiter_quick_notes") or [])
        quick_notes.append(
            {
                "text": body.text,
                "author": author,
                "created_at": now.isoformat(),
            }
        )
        payload["recruiter_quick_notes"] = quick_notes[-20:]

        if note is None:
            note = InterviewNote(
                user_id=candidate.id,
                interviewer_name=author,
                data=payload,
                created_at=now,
                updated_at=now,
            )
            session.add(note)
        else:
            if author:
                note.interviewer_name = author
            note.data = payload
            note.updated_at = now

        await session.commit()

    return SuccessResponse(message="Заметка сохранена")
