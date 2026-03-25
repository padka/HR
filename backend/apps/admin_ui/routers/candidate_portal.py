"""Public candidate portal API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from backend.apps.admin_ui.security import get_client_ip, limiter
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.domain import analytics
from backend.domain.candidates.portal_service import (
    PORTAL_SESSION_KEY,
    build_candidate_portal_journey,
    build_candidate_portal_session_payload,
    cancel_candidate_portal_slot,
    complete_screening,
    confirm_candidate_portal_slot,
    create_candidate_portal_message,
    ensure_candidate_portal_session,
    get_candidate_portal_user,
    get_latest_test1_result,
    is_candidate_portal_session_valid,
    resolve_candidate_portal_access_token,
    reserve_candidate_portal_slot,
    reschedule_candidate_portal_slot,
    resolve_candidate_portal_user,
    save_candidate_profile,
    save_screening_draft,
    touch_candidate_portal_session,
    validate_candidate_portal_session_payload,
    CandidatePortalAuthError,
    CandidatePortalError,
)

router = APIRouter(prefix="/api/candidate", tags=["candidate-portal"])
PUBLIC_PORTAL_MUTATION_LIMIT = "5/minute"
PORTAL_TOKEN_HEADERS = (
    "x-candidate-portal-token",
    "x-candidate-portal-access-token",
    "x-candidate-portal-session-token",
)


class CandidatePortalExchangePayload(BaseModel):
    token: str = Field(min_length=8)


class CandidatePortalProfilePayload(BaseModel):
    fio: str
    phone: str
    city_id: int = Field(gt=0)

    model_config = ConfigDict(str_strip_whitespace=True)


class CandidatePortalScreeningPayload(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class CandidatePortalReservePayload(BaseModel):
    slot_id: int = Field(gt=0)


class CandidatePortalReschedulePayload(BaseModel):
    new_slot_id: int = Field(gt=0)


class CandidatePortalMessagePayload(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

    model_config = ConfigDict(str_strip_whitespace=True)


def _request_portal_token(request: Request) -> str:
    for header in PORTAL_TOKEN_HEADERS:
        value = (request.headers.get(header) or "").strip()
        if value:
            return value
    return ""


async def _candidate_session_payload(request: Request) -> dict[str, Any]:
    payload = request.session.get(PORTAL_SESSION_KEY)
    if not is_candidate_portal_session_valid(payload):
        request.session.pop(PORTAL_SESSION_KEY, None)
        portal_token = _request_portal_token(request)
        if not portal_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "Сессия портала истекла. Откройте ссылку заново."},
            )

        async with async_session() as session:
            async with session.begin():
                try:
                    access = await resolve_candidate_portal_access_token(session, portal_token)
                except CandidatePortalAuthError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"message": str(exc)},
                    ) from exc
                candidate = await resolve_candidate_portal_user(session, access)
                if candidate is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"message": "Кандидатская сессия не найдена."},
                    )
                journey = await ensure_candidate_portal_session(
                    session,
                    candidate,
                    entry_channel=access.entry_channel,
                )
                if (
                    access.journey_session_id is not None
                    and access.journey_session_id != int(journey.id)
                ) or (
                    access.session_version is not None
                    and access.session_version != int(journey.session_version or 1)
                ):
                    await log_audit_action(
                        "portal_session_rejected_version_mismatch",
                        "candidate",
                        candidate.id,
                        changes={
                            "token_session_id": access.journey_session_id,
                            "token_session_version": access.session_version,
                            "actual_session_id": int(journey.id),
                            "actual_session_version": int(journey.session_version or 1),
                        },
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"message": "Сессия портала устарела. Откройте новую ссылку."},
                    )
                next_payload = build_candidate_portal_session_payload(
                    candidate_id=int(candidate.id),
                    entry_channel=access.entry_channel,
                    journey=journey,
                    last_seen_at=candidate.last_activity,
                )
        request.session[PORTAL_SESSION_KEY] = next_payload
        return next_payload
    async with async_session() as session:
        async with session.begin():
            if not await validate_candidate_portal_session_payload(session, dict(payload)):
                request.session.pop(PORTAL_SESSION_KEY, None)
                await log_audit_action(
                    "portal_session_rejected_version_mismatch",
                    "candidate",
                    payload.get("candidate_id"),
                    changes={
                        "journey_session_id": payload.get("journey_session_id"),
                        "session_version": payload.get("session_version"),
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"message": "Сессия портала устарела. Откройте новую ссылку."},
                )
    next_payload = touch_candidate_portal_session(dict(payload))
    request.session[PORTAL_SESSION_KEY] = next_payload
    return next_payload


async def _load_candidate(request: Request):
    payload = await _candidate_session_payload(request)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(payload["candidate_id"]))
        if candidate is None:
            request.session.pop(PORTAL_SESSION_KEY, None)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "Кандидатская сессия не найдена."},
            )
        return candidate, payload


def _portal_error(exc: CandidatePortalError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": str(exc)},
    )


@router.post("/session/exchange")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def exchange_candidate_portal_session(
    request: Request,
    payload: CandidatePortalExchangePayload,
):
    async with async_session() as session:
        async with session.begin():
            try:
                access = await resolve_candidate_portal_access_token(session, payload.token)
            except CandidatePortalAuthError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"message": str(exc)},
                ) from exc
            candidate = await resolve_candidate_portal_user(session, access)
            journey = await ensure_candidate_portal_session(
                session,
                candidate,
                entry_channel=access.entry_channel,
            )
            test1_result = await get_latest_test1_result(session, candidate.id)
            journey_meta = dict(journey.payload_json or {})
            if test1_result is None and not journey_meta.get("screening_started_logged_at"):
                await analytics.log_funnel_event(
                    analytics.FunnelEvent.TEST1_STARTED,
                    user_id=candidate.telegram_id or candidate.telegram_user_id,
                    candidate_id=candidate.id,
                    metadata={"channel": access.entry_channel or "candidate_portal"},
                    session=session,
                )
                journey_meta["screening_started_logged_at"] = candidate.last_activity.isoformat() if candidate.last_activity else None
                journey.payload_json = journey_meta

            response_payload = await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=access.entry_channel,
            )

        request.session[PORTAL_SESSION_KEY] = {
            **build_candidate_portal_session_payload(
                candidate_id=int(candidate.id),
                entry_channel=access.entry_channel,
                journey=journey,
                last_seen_at=candidate.last_activity,
            )
        }
        return response_payload


@router.post("/session/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def logout_candidate_portal_session(request: Request) -> Response:
    request.session.pop(PORTAL_SESSION_KEY, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/journey")
async def get_candidate_portal_journey(request: Request):
    payload = await _candidate_session_payload(request)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(payload["candidate_id"]))
            if candidate is None:
                request.session.pop(PORTAL_SESSION_KEY, None)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"message": "Кандидатская сессия не найдена."},
                )
            return await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(payload.get("entry_channel") or "web"),
            )


@router.post("/profile")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def save_candidate_portal_profile(
    request: Request,
    payload: CandidatePortalProfilePayload,
):
    session_payload = await _candidate_session_payload(request)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
            journey = await ensure_candidate_portal_session(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            try:
                await save_candidate_profile(
                    session,
                    candidate,
                    journey,
                    fio=payload.fio,
                    phone=payload.phone,
                    city_id=payload.city_id,
                )
            except CandidatePortalError as exc:
                raise _portal_error(exc) from exc
            return await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )


@router.post("/screening/save")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def save_candidate_portal_screening_draft(
    request: Request,
    payload: CandidatePortalScreeningPayload,
):
    session_payload = await _candidate_session_payload(request)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
            journey = await ensure_candidate_portal_session(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            await save_screening_draft(
                session,
                journey,
                answers=payload.answers,
            )
            return await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )


@router.post("/screening/complete")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def complete_candidate_portal_screening(
    request: Request,
    payload: CandidatePortalScreeningPayload,
):
    session_payload = await _candidate_session_payload(request)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
            journey = await ensure_candidate_portal_session(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            try:
                await complete_screening(
                    session,
                    candidate,
                    journey,
                    answers=payload.answers,
                )
            except CandidatePortalError as exc:
                raise _portal_error(exc) from exc
            return await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )


@router.post("/slots/reserve")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def reserve_candidate_portal_slot_route(
    request: Request,
    payload: CandidatePortalReservePayload,
):
    session_payload = await _candidate_session_payload(request)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()

        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        try:
            await reserve_candidate_portal_slot(
                session,
                candidate,
                journey,
                slot_id=payload.slot_id,
            )
        except CandidatePortalError as exc:
            raise _portal_error(exc) from exc
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        response_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        return response_payload


@router.post("/slots/confirm")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def confirm_candidate_portal_slot_route(request: Request):
    session_payload = await _candidate_session_payload(request)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        try:
            await confirm_candidate_portal_slot(
                session,
                candidate,
                journey,
            )
        except CandidatePortalError as exc:
            raise _portal_error(exc) from exc
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        response_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        return response_payload


@router.post("/slots/cancel")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def cancel_candidate_portal_slot_route(request: Request):
    session_payload = await _candidate_session_payload(request)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        try:
            await cancel_candidate_portal_slot(
                session,
                candidate,
                journey,
            )
        except CandidatePortalError as exc:
            raise _portal_error(exc) from exc
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        response_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        return response_payload


@router.post("/slots/reschedule")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def reschedule_candidate_portal_slot_route(
    request: Request,
    payload: CandidatePortalReschedulePayload,
):
    session_payload = await _candidate_session_payload(request)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        try:
            await reschedule_candidate_portal_slot(
                session,
                candidate,
                journey,
                new_slot_id=payload.new_slot_id,
            )
        except CandidatePortalError as exc:
            raise _portal_error(exc) from exc
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
        response_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        return response_payload


@router.post("/messages")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def send_candidate_portal_message_route(
    request: Request,
    payload: CandidatePortalMessagePayload,
):
    session_payload = await _candidate_session_payload(request)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Сессия портала недействительна."})
            try:
                await create_candidate_portal_message(
                    session,
                    candidate,
                    text=payload.text,
                )
            except CandidatePortalError as exc:
                raise _portal_error(exc) from exc
            return await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
