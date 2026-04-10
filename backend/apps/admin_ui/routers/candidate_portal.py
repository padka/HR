"""Public candidate portal API."""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.apps.admin_ui.security import get_client_ip, limiter
from backend.apps.admin_ui.services.candidate_shared_access import (
    CandidateSharedAccessError,
    start_candidate_shared_access_challenge,
    verify_candidate_shared_access_code,
)
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain import analytics
from backend.domain.candidates.portal_service import (
    PORTAL_SESSION_KEY,
    build_candidate_portal_journey,
    build_candidate_entry_options,
    build_candidate_hh_entry_url,
    build_candidate_portal_session_payload,
    cancel_candidate_portal_slot,
    complete_screening,
    confirm_candidate_portal_slot,
    create_candidate_portal_message,
    ensure_candidate_portal_session,
    ensure_candidate_portal_session_for_access,
    get_latest_test1_result_for_journey,
    get_candidate_portal_user,
    is_candidate_portal_session_valid,
    parse_candidate_portal_hh_entry_token,
    resolve_candidate_portal_access_token,
    reserve_candidate_portal_slot,
    record_candidate_entry_selection,
    reschedule_candidate_portal_slot,
    resolve_candidate_portal_user,
    save_candidate_profile,
    save_screening_draft,
    sign_candidate_portal_token,
    touch_candidate_portal_session,
    validate_candidate_portal_session_payload,
    CandidatePortalAuthError,
    CandidatePortalError,
)

router = APIRouter(prefix="/api/candidate", tags=["candidate-portal"])
PUBLIC_PORTAL_MUTATION_LIMIT = "5/minute"
PUBLIC_PORTAL_SHARED_ACCESS_CHALLENGE_LIMIT = "20/minute"
PUBLIC_PORTAL_SHARED_ACCESS_VERIFY_LIMIT = "30/minute"
PORTAL_TOKEN_HEADERS = (
    "x-candidate-portal-token",
    "x-candidate-portal-access-token",
    "x-candidate-portal-session-token",
)
PORTAL_RESUME_COOKIE = "candidate_portal_resume"
PORTAL_RESUME_COOKIE_PATH = "/api/candidate"
PORTAL_RESUME_COOKIE_MAX_AGE_SECONDS = 24 * 60 * 60
PORTAL_RECOVERY_STATE_RECOVERABLE = "recoverable"
PORTAL_RECOVERY_STATE_NEEDS_NEW_LINK = "needs_new_link"
PORTAL_RECOVERY_STATE_BLOCKED = "blocked"


class CandidatePortalExchangePayload(BaseModel):
    token: str = Field(min_length=8)


class CandidateSharedAccessChallengePayload(BaseModel):
    phone: str = Field(min_length=10, max_length=32)

    model_config = ConfigDict(str_strip_whitespace=True)


class CandidateSharedAccessVerifyPayload(BaseModel):
    challenge_token: str = Field(min_length=8)
    code: str = Field(min_length=4, max_length=8)

    model_config = ConfigDict(str_strip_whitespace=True)


class CandidateEntrySelectPayload(BaseModel):
    entry_token: str = Field(min_length=8)
    channel: Literal["web", "max", "telegram"]


class CandidateEntrySwitchPayload(BaseModel):
    channel: Literal["web", "max", "telegram"]


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


async def _candidate_entry_select_payload(request: Request) -> CandidateEntrySelectPayload:
    query_data = {
        "entry_token": (request.query_params.get("entry_token") or request.query_params.get("entry") or "").strip(),
        "channel": (request.query_params.get("channel") or "").strip(),
    }
    body_data: dict[str, Any] = {}
    raw_body = await request.body()
    if raw_body:
        content_type = (request.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            try:
                parsed = json.loads(raw_body.decode("utf-8"))
            except Exception:
                parsed = {}
            if isinstance(parsed, dict):
                body_data = parsed
        elif (
            "application/x-www-form-urlencoded" in content_type
            or "multipart/form-data" in content_type
        ):
            try:
                form = await request.form()
            except Exception:
                form = None
            if form is not None:
                body_data = dict(form)
    merged = {
        "entry_token": str(
            body_data.get("entry_token")
            or body_data.get("entry")
            or query_data["entry_token"]
            or ""
        ).strip(),
        "channel": str(body_data.get("channel") or query_data["channel"] or "").strip(),
    }
    try:
        return CandidateEntrySelectPayload.model_validate(merged)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


def _request_portal_token(request: Request) -> str:
    for header in PORTAL_TOKEN_HEADERS:
        value = (request.headers.get(header) or "").strip()
        if value:
            return value
    return ""


def _request_portal_resume_token(request: Request) -> str:
    return (request.cookies.get(PORTAL_RESUME_COOKIE) or "").strip()


def _candidate_portal_resume_cookie_clear_headers() -> dict[str, str]:
    temp_response = Response()
    temp_response.delete_cookie(
        PORTAL_RESUME_COOKIE,
        path=PORTAL_RESUME_COOKIE_PATH,
    )
    header_value = temp_response.headers.get("set-cookie") or ""
    return {"set-cookie": header_value} if header_value else {}


def _candidate_portal_auth_error(
    *,
    message: str,
    code: str,
    state: str,
    clear_resume_cookie: bool = False,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "message": message,
            "code": code,
            "state": state,
            "can_resume": state == PORTAL_RECOVERY_STATE_RECOVERABLE,
            "requires_fresh_link": state == PORTAL_RECOVERY_STATE_NEEDS_NEW_LINK,
        },
        headers=_candidate_portal_resume_cookie_clear_headers() if clear_resume_cookie else None,
    )


def _candidate_portal_resume_cookie_max_age() -> int:
    settings = get_settings()
    return max(
        300,
        min(
            int(settings.candidate_portal_token_ttl_seconds),
            int(settings.candidate_portal_session_ttl_seconds),
            PORTAL_RESUME_COOKIE_MAX_AGE_SECONDS,
        ),
    )


def _clear_candidate_portal_resume_cookie(response: Response | None) -> None:
    if response is None:
        return
    response.delete_cookie(
        PORTAL_RESUME_COOKIE,
        path=PORTAL_RESUME_COOKIE_PATH,
    )


def _set_candidate_portal_resume_cookie(
    response: Response | None,
    *,
    token: str,
) -> None:
    if response is None:
        return
    settings = get_settings()
    response.set_cookie(
        PORTAL_RESUME_COOKIE,
        token,
        max_age=_candidate_portal_resume_cookie_max_age(),
        path=PORTAL_RESUME_COOKIE_PATH,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


def _issue_candidate_portal_resume_cookie(
    response: Response | None,
    *,
    candidate,
    journey,
    entry_channel: str,
) -> None:
    token = sign_candidate_portal_token(
        candidate_uuid=str(candidate.candidate_id),
        entry_channel=entry_channel,
        source_channel="portal",
        journey_session_id=int(journey.id),
        session_version=int(journey.session_version or 1),
    )
    _set_candidate_portal_resume_cookie(response, token=token)


def _candidate_portal_not_found_error(
    response: Response | None,
    *,
    message: str,
    clear_resume_cookie: bool = False,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "message": message,
            "code": "portal_candidate_not_found",
            "state": PORTAL_RECOVERY_STATE_BLOCKED,
            "can_resume": False,
            "requires_fresh_link": False,
        },
        headers=_candidate_portal_resume_cookie_clear_headers() if clear_resume_cookie else None,
    )


def _candidate_shared_access_error(exc: CandidateSharedAccessError) -> HTTPException:
    status_code = status.HTTP_401_UNAUTHORIZED
    state = PORTAL_RECOVERY_STATE_RECOVERABLE
    can_resume = True
    if exc.code == "candidate_shared_access_temporarily_unavailable":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        state = PORTAL_RECOVERY_STATE_BLOCKED
        can_resume = False
    return HTTPException(
        status_code=status_code,
        detail={
            "message": str(exc),
            "code": exc.code,
            "state": state,
            "can_resume": can_resume,
            "requires_fresh_link": False,
        },
    )


async def _candidate_session_payload(
    request: Request,
    response: Response | None = None,
) -> dict[str, Any]:
    payload = request.session.get(PORTAL_SESSION_KEY)
    if not is_candidate_portal_session_valid(payload):
        request.session.pop(PORTAL_SESSION_KEY, None)
        portal_token = _request_portal_token(request)
        portal_token_from_resume_cookie = False
        if not portal_token:
            portal_token = _request_portal_resume_token(request)
            portal_token_from_resume_cookie = bool(portal_token)
        if not portal_token:
            raise _candidate_portal_auth_error(
                message="Сессия портала истекла. Попробуйте открыть кабинет заново.",
                code="portal_session_expired",
                state=PORTAL_RECOVERY_STATE_RECOVERABLE,
            )

        async with async_session() as session:
            async with session.begin():
                try:
                    access = await resolve_candidate_portal_access_token(session, portal_token)
                except CandidatePortalAuthError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={
                            "message": str(exc),
                            "code": "portal_link_invalid",
                            "state": PORTAL_RECOVERY_STATE_NEEDS_NEW_LINK,
                            "can_resume": False,
                            "requires_fresh_link": True,
                        },
                        headers=_candidate_portal_resume_cookie_clear_headers()
                        if portal_token_from_resume_cookie
                        else None,
                    ) from exc
                candidate = await resolve_candidate_portal_user(session, access)
                if candidate is None:
                    raise _candidate_portal_not_found_error(
                        response,
                        message="Кандидатская сессия не найдена.",
                        clear_resume_cookie=portal_token_from_resume_cookie,
                    )
                journey, mismatch = await ensure_candidate_portal_session_for_access(
                    session,
                    candidate,
                    access,
                )
                if mismatch is not None:
                    await _log_portal_session_mismatch(
                        candidate_id=int(candidate.id),
                        mismatch=mismatch,
                    )
                    raise _portal_session_mismatch_error(
                        clear_resume_cookie=portal_token_from_resume_cookie,
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
                raise _portal_session_mismatch_error()
    next_payload = touch_candidate_portal_session(dict(payload))
    request.session[PORTAL_SESSION_KEY] = next_payload
    return next_payload


async def _load_candidate(request: Request, response: Response | None = None):
    payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(payload["candidate_id"]))
        if candidate is None:
            request.session.pop(PORTAL_SESSION_KEY, None)
            raise _candidate_portal_not_found_error(
                response,
                message="Кандидатская сессия не найдена.",
            )
        return candidate, payload


def _portal_error(exc: CandidatePortalError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": str(exc)},
    )


async def _log_portal_session_mismatch(
    *,
    candidate_id: int,
    mismatch: dict[str, int | None],
) -> None:
    await log_audit_action(
        "portal_session_rejected_version_mismatch",
        "candidate",
        candidate_id,
        changes=mismatch,
    )


def _portal_session_mismatch_error(
    *,
    clear_resume_cookie: bool = False,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "message": "Сессия портала устарела. Откройте новую ссылку.",
            "code": "portal_session_version_mismatch",
            "state": PORTAL_RECOVERY_STATE_NEEDS_NEW_LINK,
            "can_resume": False,
            "requires_fresh_link": True,
        },
        headers=_candidate_portal_resume_cookie_clear_headers()
        if clear_resume_cookie
        else None,
    )


def _candidate_entry_option_or_error(
    *,
    channel: Literal["web", "max", "telegram"],
    options: dict[str, Any],
) -> dict[str, Any]:
    option = options.get(channel)
    if option and option.get("enabled") and option.get("launch_url"):
        return dict(option)
    reason = (
        str(option.get("reason_if_blocked") or "channel_entry_blocked")
        if isinstance(option, dict)
        else "channel_entry_blocked"
    )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": f"Канал {channel} сейчас недоступен.",
            "code": reason,
            "state": PORTAL_RECOVERY_STATE_BLOCKED,
            "can_resume": False,
            "requires_fresh_link": False,
        },
    )


def _candidate_entry_launch_response(
    *,
    channel: Literal["web", "max", "telegram"],
    option: dict[str, Any],
    cabinet_url: str | None,
    source: str,
) -> dict[str, Any]:
    return {
        "channel": channel,
        "recorded": True,
        "launch": {
            "type": option.get("type") or ("cabinet" if channel == "web" else "external"),
            "url": option.get("launch_url"),
            "requires_bot_start": bool(option.get("requires_bot_start")),
        },
        "cabinet_url": cabinet_url,
        "delivery_status": {
            "status": "launcher_ready",
            "source": source,
            "blocked_reason": None,
        },
    }


async def _resolve_candidate_entry_gateway(
    *,
    entry_token: str,
) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    async with async_session() as session:
        async with session.begin():
            access = parse_candidate_portal_hh_entry_token(entry_token)
            candidate = await resolve_candidate_portal_user(session, access)
            if candidate is None:
                raise CandidatePortalAuthError("Кандидатская сессия не найдена.")
            journey = await ensure_candidate_portal_session(
                session,
                candidate,
                entry_channel=access.entry_channel,
            )
            journey_payload = await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(journey.entry_channel or access.entry_channel or "web"),
                journey=journey,
            )
            options = await build_candidate_entry_options(
                session,
                candidate=candidate,
                journey=journey,
                source_channel="hh",
            )
            return candidate, journey, journey_payload, options


@router.get("/entry/resolve")
async def resolve_candidate_entry_gateway(entry: str) -> dict[str, Any]:
    try:
        candidate, journey, journey_payload, options = await _resolve_candidate_entry_gateway(entry_token=entry)
    except CandidatePortalAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": str(exc),
                "code": "hh_entry_invalid",
                "state": PORTAL_RECOVERY_STATE_NEEDS_NEW_LINK,
                "can_resume": False,
                "requires_fresh_link": True,
            },
        ) from exc

    return {
        "candidate": {
            "id": int(candidate.id),
            "candidate_id": str(candidate.candidate_id or ""),
            "fio": candidate.fio,
            "city": candidate.city,
            "vacancy_label": journey_payload["candidate"].get("vacancy_label"),
            "company": journey_payload.get("company", {}).get("name"),
        },
        "journey": {
            "session_id": int(journey.id),
            "current_step": journey_payload["journey"].get("current_step"),
            "current_step_label": journey_payload["journey"].get("current_step_label"),
            "status": journey_payload["candidate"].get("status"),
            "status_label": journey_payload["candidate"].get("status_label"),
            "next_action": journey_payload["journey"].get("next_action"),
            "last_entry_channel": journey_payload["journey"].get("last_entry_channel"),
            "available_channels": journey_payload["journey"].get("available_channels") or ["web"],
        },
        "options": options,
        "company_preview": {
            "summary": journey_payload.get("company", {}).get("summary"),
            "highlights": journey_payload.get("company", {}).get("highlights") or [],
        },
        "suggested_channel": "web",
        "fallback_policy": "web_always_available_when_portal_public_ready",
    }


@router.post("/entry/select")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def select_candidate_entry_channel(request: Request) -> dict[str, Any]:
    payload = await _candidate_entry_select_payload(request)
    try:
        async with async_session() as session:
            async with session.begin():
                access = parse_candidate_portal_hh_entry_token(payload.entry_token)
                candidate = await resolve_candidate_portal_user(session, access)
                if candidate is None:
                    raise CandidatePortalAuthError("Кандидатская сессия не найдена.")
                journey = await ensure_candidate_portal_session(
                    session,
                    candidate,
                    entry_channel=access.entry_channel,
                )
                options = await build_candidate_entry_options(
                    session,
                    candidate=candidate,
                    journey=journey,
                    source_channel="hh",
                )
                option = _candidate_entry_option_or_error(
                    channel=payload.channel,
                    options=options,
                )
                await record_candidate_entry_selection(
                    session,
                    journey=journey,
                    channel=payload.channel,
                    source="hh",
                    options_snapshot=[key for key, item in options.items() if bool(item.get("enabled"))],
                )
                cabinet_url = options.get("web", {}).get("launch_url")
                return _candidate_entry_launch_response(
                    channel=payload.channel,
                    option=option,
                    cabinet_url=str(cabinet_url) if cabinet_url else None,
                    source="hh_gateway",
                )
    except CandidatePortalAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": str(exc),
                "code": "hh_entry_invalid",
                "state": PORTAL_RECOVERY_STATE_NEEDS_NEW_LINK,
                "can_resume": False,
                "requires_fresh_link": True,
            },
        ) from exc


@router.post("/entry/switch")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def switch_candidate_entry_channel(
    request: Request,
    response: Response,
    payload: CandidateEntrySwitchPayload,
) -> dict[str, Any]:
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                request.session.pop(PORTAL_SESSION_KEY, None)
                raise _candidate_portal_not_found_error(
                    response,
                    message="Кандидатская сессия не найдена.",
                )
            journey = await ensure_candidate_portal_session(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            if (
                int(journey.id) != int(session_payload.get("journey_session_id") or 0)
                or int(journey.session_version or 1) != int(session_payload.get("session_version") or 0)
            ):
                request.session.pop(PORTAL_SESSION_KEY, None)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "message": "Сессия портала устарела. Откройте новую ссылку.",
                        "code": "portal_session_version_mismatch",
                        "state": PORTAL_RECOVERY_STATE_NEEDS_NEW_LINK,
                        "can_resume": False,
                        "requires_fresh_link": True,
                    },
                )
            options = await build_candidate_entry_options(
                session,
                candidate=candidate,
                journey=journey,
                source_channel="cabinet",
            )
            option = _candidate_entry_option_or_error(
                channel=payload.channel,
                options=options,
            )
            await record_candidate_entry_selection(
                session,
                journey=journey,
                channel=payload.channel,
                source="cabinet",
                options_snapshot=[key for key, item in options.items() if bool(item.get("enabled"))],
            )
            request.session[PORTAL_SESSION_KEY] = build_candidate_portal_session_payload(
                candidate_id=int(candidate.id),
                entry_channel=payload.channel,
                journey=journey,
                last_seen_at=journey.last_activity_at or candidate.last_activity,
            )
            _issue_candidate_portal_resume_cookie(
                response,
                candidate=candidate,
                journey=journey,
                entry_channel=payload.channel,
            )
            cabinet_url = options.get("web", {}).get("launch_url")
            return _candidate_entry_launch_response(
                channel=payload.channel,
                option=option,
                cabinet_url=str(cabinet_url) if cabinet_url else None,
                source="cabinet",
            )


@router.post("/access/challenge")
@limiter.limit(PUBLIC_PORTAL_SHARED_ACCESS_CHALLENGE_LIMIT, key_func=get_client_ip)
async def start_candidate_shared_access(
    request: Request,
    payload: CandidateSharedAccessChallengePayload,
) -> dict[str, Any]:
    del request
    try:
        async with async_session() as session:
            async with session.begin():
                challenge = await start_candidate_shared_access_challenge(
                    session,
                    phone=payload.phone,
                )
    except CandidateSharedAccessError as exc:
        raise _candidate_shared_access_error(exc) from exc
    return {
        "ok": True,
        "challenge_token": challenge.token,
        "expires_in_seconds": challenge.expires_in_seconds,
        "retry_after_seconds": challenge.retry_after_seconds,
        "message": "Если номер найден, мы отправили код в связанный канал кандидата.",
        "delivery_hint": "Проверьте HH, Telegram или MAX, если один из каналов уже связан с откликом.",
    }


@router.post("/access/verify")
@limiter.limit(PUBLIC_PORTAL_SHARED_ACCESS_VERIFY_LIMIT, key_func=get_client_ip)
async def verify_candidate_shared_access(
    request: Request,
    response: Response,
    payload: CandidateSharedAccessVerifyPayload,
):
    try:
        async with async_session() as session:
            async with session.begin():
                candidate, journey, response_payload = await verify_candidate_shared_access_code(
                    session,
                    challenge_token=payload.challenge_token,
                    code=payload.code,
                )
    except CandidateSharedAccessError as exc:
        raise _candidate_shared_access_error(exc) from exc

    request.session[PORTAL_SESSION_KEY] = build_candidate_portal_session_payload(
        candidate_id=int(candidate.id),
        entry_channel="web",
        journey=journey,
        last_seen_at=candidate.last_activity,
    )
    _issue_candidate_portal_resume_cookie(
        response,
        candidate=candidate,
        journey=journey,
        entry_channel="web",
    )
    return response_payload


@router.post("/session/exchange")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def exchange_candidate_portal_session(
    request: Request,
    response: Response,
    payload: CandidatePortalExchangePayload,
):
    async with async_session() as session:
        async with session.begin():
            try:
                access = await resolve_candidate_portal_access_token(session, payload.token)
            except CandidatePortalAuthError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "message": str(exc),
                        "code": "portal_link_invalid",
                        "state": PORTAL_RECOVERY_STATE_NEEDS_NEW_LINK,
                        "can_resume": False,
                        "requires_fresh_link": True,
                    },
                ) from exc
            candidate = await resolve_candidate_portal_user(session, access)
            if candidate is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "message": "Кандидатская сессия не найдена.",
                        "code": "portal_candidate_not_found",
                        "state": PORTAL_RECOVERY_STATE_BLOCKED,
                        "can_resume": False,
                        "requires_fresh_link": False,
                    },
                )
            journey, mismatch = await ensure_candidate_portal_session_for_access(
                session,
                candidate,
                access,
            )
            if mismatch is not None:
                await _log_portal_session_mismatch(
                    candidate_id=int(candidate.id),
                    mismatch=mismatch,
                )
                raise _portal_session_mismatch_error()
            test1_result = await get_latest_test1_result_for_journey(
                session,
                candidate_id=int(candidate.id),
                journey=journey,
            )
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
                journey=journey,
            )

        request.session[PORTAL_SESSION_KEY] = {
            **build_candidate_portal_session_payload(
                candidate_id=int(candidate.id),
                entry_channel=access.entry_channel,
                journey=journey,
                last_seen_at=candidate.last_activity,
            )
        }
        _issue_candidate_portal_resume_cookie(
            response,
            candidate=candidate,
            journey=journey,
            entry_channel=access.entry_channel,
        )
        return response_payload


@router.post("/session/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def logout_candidate_portal_session(request: Request, response: Response) -> Response:
    request.session.pop(PORTAL_SESSION_KEY, None)
    _clear_candidate_portal_resume_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/journey")
async def get_candidate_portal_journey(request: Request, response: Response):
    payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(payload["candidate_id"]))
            if candidate is None:
                request.session.pop(PORTAL_SESSION_KEY, None)
                raise _candidate_portal_not_found_error(
                    response,
                    message="Кандидатская сессия не найдена.",
                )
            journey = await ensure_candidate_portal_session(
                session,
                candidate,
                entry_channel=str(payload.get("entry_channel") or "web"),
            )
            response_payload = await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(payload.get("entry_channel") or "web"),
                journey=journey,
            )
            _issue_candidate_portal_resume_cookie(
                response,
                candidate=candidate,
                journey=journey,
                entry_channel=str(payload.get("entry_channel") or "web"),
            )
            return response_payload


@router.post("/profile")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def save_candidate_portal_profile(
    request: Request,
    response: Response,
    payload: CandidatePortalProfilePayload,
):
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                raise _candidate_portal_not_found_error(
                    response,
                    message="Сессия портала недействительна.",
                )
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
            response_payload = await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
                journey=journey,
            )
            _issue_candidate_portal_resume_cookie(
                response,
                candidate=candidate,
                journey=journey,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            return response_payload


@router.post("/screening/save")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def save_candidate_portal_screening_draft(
    request: Request,
    response: Response,
    payload: CandidatePortalScreeningPayload,
):
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                raise _candidate_portal_not_found_error(
                    response,
                    message="Сессия портала недействительна.",
                )
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
            response_payload = await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
                journey=journey,
            )
            _issue_candidate_portal_resume_cookie(
                response,
                candidate=candidate,
                journey=journey,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            return response_payload


@router.post("/screening/complete")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def complete_candidate_portal_screening(
    request: Request,
    response: Response,
    payload: CandidatePortalScreeningPayload,
):
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                raise _candidate_portal_not_found_error(
                    response,
                    message="Сессия портала недействительна.",
                )
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
            response_payload = await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
                journey=journey,
            )
            _issue_candidate_portal_resume_cookie(
                response,
                candidate=candidate,
                journey=journey,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            return response_payload


@router.post("/slots/reserve")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def reserve_candidate_portal_slot_route(
    request: Request,
    response: Response,
    payload: CandidatePortalReservePayload,
):
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()

        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
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
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
        response_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
            journey=journey,
        )
        await session.commit()
        _issue_candidate_portal_resume_cookie(
            response,
            candidate=candidate,
            journey=journey,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        return response_payload


@router.post("/slots/confirm")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def confirm_candidate_portal_slot_route(request: Request, response: Response):
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
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
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
        response_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
            journey=journey,
        )
        await session.commit()
        _issue_candidate_portal_resume_cookie(
            response,
            candidate=candidate,
            journey=journey,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        return response_payload


@router.post("/slots/cancel")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def cancel_candidate_portal_slot_route(request: Request, response: Response):
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
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
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
        response_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
            journey=journey,
        )
        await session.commit()
        _issue_candidate_portal_resume_cookie(
            response,
            candidate=candidate,
            journey=journey,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        return response_payload


@router.post("/slots/reschedule")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def reschedule_candidate_portal_slot_route(
    request: Request,
    response: Response,
    payload: CandidatePortalReschedulePayload,
):
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
        journey = await ensure_candidate_portal_session(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        await session.commit()
        candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
        if candidate is None:
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
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
            raise _candidate_portal_not_found_error(
                response,
                message="Сессия портала недействительна.",
            )
        response_payload = await build_candidate_portal_journey(
            session,
            candidate,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
            journey=journey,
        )
        await session.commit()
        _issue_candidate_portal_resume_cookie(
            response,
            candidate=candidate,
            journey=journey,
            entry_channel=str(session_payload.get("entry_channel") or "web"),
        )
        return response_payload


@router.post("/messages")
@limiter.limit(PUBLIC_PORTAL_MUTATION_LIMIT, key_func=get_client_ip)
async def send_candidate_portal_message_route(
    request: Request,
    response: Response,
    payload: CandidatePortalMessagePayload,
):
    session_payload = await _candidate_session_payload(request, response=response)
    async with async_session() as session:
        async with session.begin():
            candidate = await get_candidate_portal_user(session, int(session_payload["candidate_id"]))
            if candidate is None:
                raise _candidate_portal_not_found_error(
                    response,
                    message="Сессия портала недействительна.",
                )
            try:
                await create_candidate_portal_message(
                    session,
                    candidate,
                    text=payload.text,
                )
            except CandidatePortalError as exc:
                raise _portal_error(exc) from exc
            journey = await ensure_candidate_portal_session(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            response_payload = await build_candidate_portal_journey(
                session,
                candidate,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
                journey=journey,
            )
            _issue_candidate_portal_resume_cookie(
                response,
                candidate=candidate,
                journey=journey,
                entry_channel=str(session_payload.get("entry_channel") or "web"),
            )
            return response_payload
