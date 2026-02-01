import logging
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from sqlalchemy import func, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.timezones import tz_display, DEFAULT_TZ
from backend.apps.admin_ui.services.candidates import (
    INTERVIEW_FIELD_TYPES,
    INTERVIEW_RECOMMENDATION_VALUES,
    candidate_filter_options,
    STATUS_DEFINITIONS,
    delete_candidate,
    delete_all_candidates,
    generate_candidate_invite_token,
    get_candidate_detail,
    list_candidates,
    save_interview_notes,
    toggle_candidate_activity,
    update_candidate,
    update_candidate_status,
    upsert_candidate,
    PIPELINE_DEFINITIONS,
    DEFAULT_PIPELINE,
    DEFAULT_INTRO_DAY_INVITATION_TEMPLATE,
    render_intro_day_invitation,
)
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.security import require_principal, Principal, require_admin
from backend.apps.admin_ui.services.slots import (
    execute_bot_dispatch,
    schedule_manual_candidate_slot,
    schedule_manual_candidate_slot_silent,
    ManualSlotError,
    recruiters_for_slot_form,
    _trigger_test2,
    recruiter_time_to_utc,
)
from backend.apps.bot.services import approve_slot_and_notify
from backend.core.guards import ensure_candidate_scope, ensure_slot_scope
from backend.apps.admin_ui.security import require_csrf_token
from backend.apps.admin_ui.utils import fmt_local
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.core.sanitizers import sanitize_plain_text
from backend.core.time_utils import parse_form_datetime
from backend.core.audit import log_audit_action
from backend.domain.candidates.models import User
from backend.domain.models import (
    Slot,
    City,
    Recruiter,
    SlotStatus,
    OutboxNotification,
    DEFAULT_INTRO_DAY_DURATION_MIN,
)
from backend.domain.repositories import find_city_by_plain_name

router = APIRouter(prefix="/candidates", tags=["candidates"])
logger = logging.getLogger(__name__)


# Module-level wrapper for status service (allows monkeypatching in tests)
async def set_status_interview_declined(tg_id: int) -> bool:
    """Wrapper for domain status service to set interview declined status."""
    from backend.domain.candidates.status_service import (
        set_status_interview_declined as domain_set_status_interview_declined,
    )
    return await domain_set_status_interview_declined(tg_id)


def _parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or value == "":
        return None
    value = value.lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _load_city_with_recruiters(city_name: Optional[str]) -> Optional[City]:
    """Return city with recruiters using case-insensitive matching.

    SQLite's `LOWER()` implementation is ASCII-only which meant cities that
    were stored as `Волгоград` could not be matched against user-provided
    values such as `волгоград`. To keep behaviour consistent across SQLite
    (tests) and PostgreSQL (production) we perform a plain Python casefold
    comparison and fetch the matching city explicitly.
    """

    city = await find_city_by_plain_name(city_name)
    if not city:
        return None
    async with async_session() as session:
        return await session.get(
            City,
            city.id,
            options=(selectinload(City.recruiters),),
        )


async def _list_active_cities() -> List[City]:
    async with async_session() as session:
        rows = await session.scalars(
            select(City).where(City.active.is_(True)).order_by(City.name.asc())
        )
        return list(rows)


def _select_primary_recruiter(city: Optional[City]) -> Optional[Recruiter]:
    if not city or not getattr(city, "recruiters", None):
        return None
    for recruiter in city.recruiters:
        if recruiter is not None and getattr(recruiter, "active", True):
            return recruiter
    return city.recruiters[0]


@router.get("", response_class=HTMLResponse)
async def candidates_list(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=5, le=100),
    q: Optional[str] = Query(None, alias="search"),
    city: Optional[str] = Query(None),
    active: Optional[str] = Query(None),
    rating: Optional[str] = Query(None),
    has_tests: Optional[str] = Query(None),
    has_messages: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    statuses: Optional[List[str]] = Query(None, alias="status"),
    recruiter_id: Optional[str] = Query(None),
    city_ids: Optional[List[int]] = Query(None, alias="city_id"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    test1_status: Optional[str] = Query(None),
    test2_status: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query(None),
    view: str = Query("calendar"),
    calendar_mode: str = Query("day"),
    pipeline: str = Query("interview"),
    principal: Principal = Depends(require_principal),
) -> HTMLResponse:
    target = "/app/candidates"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=302)

@router.get("/detailization", response_class=HTMLResponse)
async def candidates_detailization(
    request: Request,
    status: Optional[str] = Query(default=None, description="hired or not_hired"),
    q: Optional[str] = Query(default=None, alias="search"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=5, le=200),
    principal: Principal = Depends(require_principal),
) -> HTMLResponse:
    target = "/app/candidates"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=302)


@router.get("/new", response_class=HTMLResponse)
async def candidates_new(
    request: Request,
    principal: Principal = Depends(require_principal),
) -> HTMLResponse:
    return RedirectResponse(url="/app/candidates/new", status_code=302)


@router.post("/create")
async def candidates_create(
    request: Request,
    fio: str = Form(...),
    city: str = Form(""),
    city_id: Optional[str] = Form(None),
    phone: str = Form(""),
    responsible_recruiter_id: Optional[str] = Form(None),
    interview_date: Optional[str] = Form(None),
    interview_time: Optional[str] = Form(None),
    is_active: Optional[str] = Form("on"),
    principal: Principal = Depends(require_principal),
):
    active_flag = _parse_bool(is_active)
    interview_dt = None
    interview_tz = None
    interview_city = None
    interview_recruiter = None
    recruiter_id_value = _parse_int(responsible_recruiter_id)
    if principal.type == "recruiter":
        recruiter_id_value = principal.id
    city_value = _parse_int(city_id)
    candidate_city = city or None
    if city_value is not None:
        async with async_session() as session:
            interview_city = await session.get(City, city_value)
        if interview_city is None:
            return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
        if hasattr(interview_city, "name_plain"):
            candidate_city = interview_city.name_plain or candidate_city
        elif interview_city.name:
            candidate_city = interview_city.name
    if city_value is None and not candidate_city:
        return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    if recruiter_id_value is not None:
        async with async_session() as session:
            interview_recruiter = await session.get(Recruiter, recruiter_id_value)
        if interview_recruiter is None:
            return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
        if interview_date or interview_time:
            if hasattr(interview_recruiter, "active") and interview_recruiter.active is False:
                return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    else:
        return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    if not (interview_date and interview_time):
        return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    if recruiter_id_value is None or interview_city is None:
        return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    if interview_recruiter is None:
        return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    app_timezone = get_settings().timezone or DEFAULT_TZ
    interview_tz = interview_city.tz or interview_recruiter.tz or app_timezone
    try:
        interview_dt = parse_form_datetime(f"{interview_date}T{interview_time}", interview_tz)
    except ValueError:
        return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    try:
        user = await upsert_candidate(
            telegram_id=None,
            fio=fio,
            city=candidate_city,
            phone=phone or None,
            is_active=True if active_flag is None else active_flag,
            responsible_recruiter_id=recruiter_id_value,
            manual_slot_from=interview_dt,
            manual_slot_to=interview_dt + timedelta(minutes=60) if interview_dt else None,
            manual_slot_timezone=interview_tz,
        )
    except ValueError:
        return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    except IntegrityError:
        return RedirectResponse(url="/candidates/new?error=duplicate", status_code=303)

    admin_username = request.session.get("username", "admin")
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    try:
        await schedule_manual_candidate_slot_silent(
            candidate=user,
            recruiter=interview_recruiter,
            city=interview_city,
            dt_utc=interview_dt,
            slot_tz=interview_tz or DEFAULT_TZ,
            admin_username=admin_username,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return RedirectResponse(
            url=f"/candidates/{user.id}?slot_scheduled=scheduled",
            status_code=303,
        )
    except ManualSlotError:
        await delete_candidate(user.id)
        return RedirectResponse(
            url="/candidates/new?error=slot_conflict",
            status_code=303,
        )


@router.post("/{candidate_id}/invite-token")
async def candidates_invite_token(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> RedirectResponse:
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            return RedirectResponse(url="/candidates?error=candidate_not_found", status_code=303)
        ensure_candidate_scope(user, principal)
    token = await generate_candidate_invite_token(candidate_id, principal=principal)
    if not token:
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?error=invite_token",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/candidates/{candidate_id}?invite_token={quote_plus(token)}",
        status_code=303,
    )


@router.get("/{candidate_id}", response_class=HTMLResponse)
async def candidates_detail(
    request: Request,
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> HTMLResponse:
    return RedirectResponse(url=f"/app/candidates/{candidate_id}", status_code=302)


@router.post("/{candidate_id}/update")
async def candidates_update(
    candidate_id: int,
    telegram_id: Optional[str] = Form(None),
    fio: str = Form(...),
    city: str = Form(""),
    phone: str = Form(""),
    is_active: Optional[str] = Form(None),
    principal: Principal = Depends(require_principal),
):
    active_flag = _parse_bool(is_active)
    telegram_id_value: Optional[int] = None
    if telegram_id and telegram_id.strip():
        try:
            telegram_id_value = int(telegram_id.strip())
        except ValueError:
            return RedirectResponse(url=f"/candidates/{candidate_id}?error=update", status_code=303)
    try:
        success = await update_candidate(
            candidate_id,
            telegram_id=telegram_id_value,
            fio=fio,
            city=city or None,
            phone=phone or None,
            is_active=True if active_flag is None else active_flag,
            principal=principal,
        )
    except ValueError:
        success = False
    except IntegrityError:
        success = False

    if not success:
        return RedirectResponse(url=f"/candidates/{candidate_id}?error=update", status_code=303)
    return RedirectResponse(url=f"/candidates/{candidate_id}?saved=1", status_code=303)


@router.post("/{candidate_id}/toggle")
async def candidates_toggle(candidate_id: int, active: str = Form("true"), principal: Principal = Depends(require_principal)):
    flag = _parse_bool(active)
    if flag is None:
        flag = True
    await toggle_candidate_activity(candidate_id, active=flag, principal=principal)
    return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=303)


@router.post("/{candidate_id}/status", response_model=None)
async def candidates_set_status(
    request: Request,
    candidate_id: int,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    _: None = Depends(require_csrf_token),
    principal: Principal = Depends(require_principal),
) -> Response:
    """Update candidate status via UI or AJAX/kanban board.

    DEPRECATED: Use POST /api/candidates/{id}/actions/{action_key} instead.
    This endpoint is only available when ENABLE_LEGACY_STATUS_API=true.
    """
    settings = get_settings()
    if not settings.enable_legacy_status_api:
        return JSONResponse(
            {"ok": False, "message": "Legacy status endpoint disabled in this environment."},
            status_code=403,
        )

    # Log deprecation warning for monitoring
    logger.warning(
        "legacy_status_api.called",
        extra={
            "candidate_id": candidate_id,
            "user_agent": request.headers.get("user-agent", ""),
            "referer": request.headers.get("referer", ""),
            "deprecation_notice": "Use POST /api/candidates/{id}/actions/{action_key} instead",
        },
    )
    allowed_form_statuses = {
        "hired",
        "not_hired",
        "intro_day_declined_day_of",
        "intro_day_declined_invitation",
        "interview_declined",
        "test2_failed",
    }

    content_type = (request.headers.get("content-type") or "").lower()
    is_json_request = "application/json" in content_type
    status_slug: Optional[str] = None
    reject_reason: Optional[str] = None
    reject_comment: Optional[str] = None
    is_form_submission = not is_json_request

    # Prefer JSON payloads (AJAX actions)
    try:
        raw_body = await request.body()
    except RuntimeError:
        raw_body = getattr(request, "_body", b"") or b""
    if raw_body and is_json_request:
        try:
            parsed = json.loads(raw_body)
            if isinstance(parsed, dict):
                status_slug = parsed.get("status") or None
        except json.JSONDecodeError:
            pass
        # Make body readable again for later form parsing
        request._body = raw_body  # type: ignore[attr-defined]

    # Fallback to form submission (HTML forms)
    if status_slug is None:
        if not is_json_request:
            is_form_submission = True
        form = await request.form()
        status_slug = form.get("status")
        reject_reason = form.get("reject_reason")
        reject_comment = form.get("reject_comment")

    if not status_slug:
        if not is_form_submission:
            return JSONResponse(
                {"ok": False, "message": "Статус обязателен"}, status_code=400
            )
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?error=invalid_status",
            status_code=303,
        )

    status_slug = status_slug.strip()
    normalized_slug = status_slug.lower()

    if is_form_submission and normalized_slug not in allowed_form_statuses:
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?error=invalid_status",
            status_code=303,
        )

    if normalized_slug == "interview_declined":
        async with async_session() as session:
            user = await session.get(User, candidate_id)
        if user and user.telegram_id is not None:
            await set_status_interview_declined(user.telegram_id)

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id, normalized_slug, bot_service=bot_service, principal=principal
    )

    bot_header = "skipped:not_applicable"
    if dispatch is not None:
        bot_header = getattr(dispatch, "status", bot_header)
        plan = getattr(dispatch, "plan", None)
        if plan is not None and ok:
            background_tasks.add_task(
                execute_bot_dispatch, plan, stored_status or "", bot_service
            )

    if is_form_submission:
        if not ok:
            # Map error messages to specific error codes for better UX
            error_key = "status_update_failed"
            msg_lower = (message or "").lower()

            if "не найден" in msg_lower and "кандидат" in msg_lower:
                error_key = "candidate_not_found"
            elif "не найден" in msg_lower and "слот" in msg_lower:
                error_key = "slot_not_found"
            elif "некорректный статус" in msg_lower:
                error_key = "invalid_status"
            elif "telegram" in msg_lower:
                error_key = "missing_telegram"
            elif "нельзя установить вручную" in msg_lower:
                error_key = "status_not_manual"
            elif "не удалось согласовать" in msg_lower:
                error_key = "slot_approval_failed"

            # Log the error for diagnostics
            logger.warning(
                "Status update failed",
                extra={
                    "candidate_id": candidate_id,
                    "requested_status": status_slug,
                    "error_key": error_key,
                    "error_message": message,
                },
            )

            # URL-encode the error message to handle special characters
            encoded_message = quote_plus(message or "")
            return RedirectResponse(
                url=f"/candidates/{candidate_id}?error={error_key}&error_message={encoded_message}",
                status_code=303,
            )

        # Log rejection reason and comment if provided
        if ok and (reject_reason or reject_comment):
            rejection_metadata = {}
            if reject_reason:
                rejection_metadata["rejection_reason"] = reject_reason
            if reject_comment:
                rejection_metadata["rejection_comment"] = reject_comment
            rejection_metadata["status"] = stored_status or normalized_slug

            await log_audit_action(
                "candidate_rejection_detailed",
                "candidate",
                candidate_id,
                changes=rejection_metadata,
            )
            logger.info(
                "Candidate rejected with reason",
                extra={
                    "candidate_id": candidate_id,
                    "status": stored_status or normalized_slug,
                    "reason": reject_reason,
                    "comment": reject_comment,
                },
            )

        return RedirectResponse(url=f"/candidates/{candidate_id}?ok=1", status_code=303)

    status_code = 200 if ok else 400
    payload_response = {
        "ok": ok,
        "message": message or "",
        "status": stored_status,
    }
    response = JSONResponse(payload_response, status_code=status_code)
    response.headers["X-Bot"] = bot_header
    return response


@router.get("/{candidate_id}/resend-test2")
async def candidates_resend_test2(
    request: Request,
    candidate_id: int,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
) -> Response:
    """Resend Test 2 invite to a candidate via bot."""

    accept_json = "application/json" in (request.headers.get("accept") or "").lower()
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            payload = {"ok": False, "message": "Кандидат не найден"}
            if accept_json:
                return JSONResponse(payload, status_code=404)
            return RedirectResponse(
                url="/candidates?error=candidate_not_found",
                status_code=303,
            )

        ensure_candidate_scope(user, principal)

        telegram_id = user.telegram_user_id or user.telegram_id
        if not telegram_id:
            payload = {"ok": False, "message": "У кандидата нет Telegram ID"}
            if accept_json:
                return JSONResponse(payload, status_code=400)
            return RedirectResponse(
                url=f"/candidates/{candidate_id}?error=missing_telegram",
                status_code=303,
            )

        slot = await session.scalar(
            select(Slot)
            .where(
                or_(
                    Slot.candidate_id == user.candidate_id,
                    Slot.candidate_tg_id == telegram_id,
                )
            )
            .order_by(Slot.start_utc.desc(), Slot.id.desc())
        )

        candidate_city_id = (
            getattr(slot, "candidate_city_id", None)
            or getattr(slot, "city_id", None)
            or getattr(user, "city_id", None)
        )
        candidate_tz = (
            getattr(slot, "candidate_tz", None)
            or getattr(user, "tz_name", None)
            or DEFAULT_TZ
        )
        scheduled_at = datetime.now(timezone.utc)
        if slot:
            slot.test2_sent_at = scheduled_at
            await session.commit()

    result = await _trigger_test2(
        int(telegram_id),
        candidate_tz,
        candidate_city_id,
        user.fio or getattr(user, "name", "") or "Кандидат",
        bot_service=bot_service,
        required=get_settings().test2_required,
        slot_id=slot.id if slot else None,
    )

    # Ensure status reflects the resend attempt
    if result.ok:
        await update_candidate_status(
            candidate_id, "test2_sent", bot_service=bot_service
        )

    payload = {
        "ok": result.ok,
        "status": result.status,
        "message": result.message or result.error or "",
    }
    status_code = 200 if result.ok else 400

    if accept_json:
        return JSONResponse(payload, status_code=status_code)

    query = f"?test2_resend={result.status}"
    if result.error:
        query += f"&error_message={quote_plus(result.error)}"
    return RedirectResponse(
        url=f"/candidates/{candidate_id}{query}",
        status_code=303,
    )


@router.post("/{candidate_id}/interview-notes")
async def candidates_save_interview_notes(
    request: Request,
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> RedirectResponse:
    form = await request.form()
    payload: Dict[str, Any] = {}

    for field, field_type in INTERVIEW_FIELD_TYPES.items():
        raw_value = form.get(field)
        if field_type == "checkbox":
            payload[field] = bool(_parse_bool(raw_value))
        elif field_type == "radio":
            value = (raw_value or "undecided").strip()
            if value not in INTERVIEW_RECOMMENDATION_VALUES:
                value = "undecided"
            payload[field] = value
        elif field_type == "datetime":
            payload[field] = raw_value or ""
        else:  # text / textarea
            payload[field] = (raw_value or "").strip()

    interviewer_name = payload.get("interviewer_name", "")
    payload["interviewer_name"] = interviewer_name
    payload["script_version"] = "smart_service_v1"

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            return RedirectResponse(
                url="/candidates?error=candidate_not_found",
                status_code=303,
            )
        ensure_candidate_scope(user, principal)

    success = await save_interview_notes(
        candidate_id,
        interviewer_name=interviewer_name,
        data=payload,
        principal=principal,
    )
    if not success:
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?interview_error=1",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/candidates/{candidate_id}?interview_saved=1",
        status_code=303,
    )


@router.get("/{candidate_id}/interview-notes/download")
async def candidates_download_interview_notes(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> PlainTextResponse:
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail or not detail.get("user"):
        raise HTTPException(status_code=404)

    interview_record = detail.get("interview_notes") or {}
    data = interview_record.get("data") or {}
    if not data:
        raise HTTPException(status_code=404, detail="Анкета ещё не заполнена.")

    sections = detail.get("interview_form_sections") or []
    content = _format_interview_notes(detail["user"], data, sections)
    filename = f"interview_{detail['user'].id}.txt"
    headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}
    return PlainTextResponse(content, headers=headers)


def _format_interview_notes(user: User, data: Dict[str, Any], sections: List[Dict[str, Any]]) -> str:
    lines = [
        f"Кандидат: {user.fio}",
        f"Telegram ID: {user.telegram_id}",
        f"Интервьюер: {data.get('interviewer_name') or '—'}",
        f"Дата интервью: {data.get('interviewed_at') or '—'}",
        f"Решение: {data.get('recommendation') or 'undecided'}",
        "",
    ]

    for section in sections or []:
        lines.append(section.get("title", ""))
        if section.get("description"):
            lines.append(section["description"])
        for question in section.get("questions", []):
            key = question.get("key")
            label = question.get("label", key)
            q_type = question.get("type")
            value = data.get(key)
            if q_type == "checkbox":
                lines.append(f"- {label}: {'Да' if value else 'Нет'}")
            elif q_type == "radio":
                lines.append(f"- {label}: {value or 'Не выбрано'}")
            else:
                if value:
                    lines.append(f"- {label}: {value}")
        lines.append("")
    return "\n".join(lines).strip()


@router.post("/{candidate_id}/slots/{slot_id}/approve")
async def candidates_approve_slot(
    candidate_id: int,
    slot_id: int,
    principal: Principal = Depends(require_principal),
):
    redirect_base = f"/candidates/{candidate_id}"

    def _redirect(status: str, message: str) -> RedirectResponse:
        encoded = quote_plus(message or "")
        return RedirectResponse(
            url=f"{redirect_base}?approval={status}&approval_message={encoded}",
            status_code=303,
        )

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            return _redirect("candidate_missing", "Кандидат не найден.")
        ensure_candidate_scope(user, principal)
        if user.telegram_id is None:
            return _redirect("telegram_missing", "Для кандидата не указан Telegram ID.")
        slot = await session.get(Slot, slot_id)
        if not slot:
            return _redirect("slot_missing", "Слот не найден или уже удалён.")
        ensure_slot_scope(slot, principal)
        if slot.candidate_tg_id != user.telegram_id:
            return _redirect("invalid_candidate", "Слот относится к другому кандидату.")

    result = await approve_slot_and_notify(slot_id, force_notify=True)
    return _redirect(result.status, result.message)


@router.post("/{candidate_id}/actions/approve_upcoming_slot")
async def candidates_approve_upcoming_slot(
    candidate_id: int,
    principal: Principal = Depends(require_principal),
):
    """Approve the first upcoming pending slot for the candidate."""
    redirect_base = f"/candidates/{candidate_id}"

    def _redirect(status: str, message: str) -> RedirectResponse:
        encoded = quote_plus(message or "")
        return RedirectResponse(
            url=f"{redirect_base}?approval={status}&approval_message={encoded}",
            status_code=303,
        )

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            return _redirect("candidate_missing", "Кандидат не найден.")
        ensure_candidate_scope(user, principal)
        
        # Find pending slot
        slot = await session.scalar(
            select(Slot)
            .where(
                or_(
                    Slot.candidate_id == user.candidate_id,
                    Slot.candidate_tg_id == user.telegram_id,
                ),
                func.lower(Slot.status) == SlotStatus.PENDING,
                Slot.start_utc >= datetime.now(timezone.utc)
            )
            .order_by(Slot.start_utc.asc())
            .limit(1)
        )
        
        if not slot:
            return _redirect("no_pending_slot", "Нет слотов, ожидающих подтверждения.")
            
        slot_id = slot.id

    result = await approve_slot_and_notify(slot_id, force_notify=True)
    return _redirect(result.status, result.message)


@router.post("/{candidate_id}/delete")
async def candidates_delete(candidate_id: int, principal: Principal = Depends(require_principal)):
    await delete_candidate(candidate_id, principal=principal)
    return RedirectResponse(url="/candidates", status_code=303)


@router.post("/delete-all")
async def candidates_delete_all(_: Principal = Depends(require_admin)):
    deleted = await delete_all_candidates()
    return RedirectResponse(
        url=f"/candidates?bulk_deleted={deleted}",
        status_code=303,
    )


@router.get("/{candidate_id}/reports/{report_key}")
async def candidates_download_report(
    candidate_id: int,
    report_key: str,
    principal: Principal = Depends(require_principal),
):
    if report_key not in {"test1", "test2"}:
        raise HTTPException(status_code=404)
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        raise HTTPException(status_code=404)
    user = detail["user"]
    field = "test1_report_url" if report_key == "test1" else "test2_report_url"
    
    settings = get_settings()
    base_dir = Path(settings.data_dir)
    
    # 1. Try path from DB
    rel_path = getattr(user, field, None)
    file_path = (base_dir / rel_path).resolve() if rel_path else None
    
    # 2. Fallback to standard location
    if not file_path or not file_path.is_file():
        fallback_path = base_dir / "reports" / str(user.id) / f"{report_key}.txt"
        if fallback_path.is_file():
            file_path = fallback_path
            
    if not file_path or not file_path.is_file():
        logger.warning(f"Report {report_key} not found for candidate {candidate_id}. DB: {rel_path}")
        raise HTTPException(status_code=404, detail="File not found on server")
        
    media_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "text/plain"
    return FileResponse(file_path, filename=file_path.name, media_type=media_type)


@router.get("/{candidate_id}/schedule-slot", response_class=HTMLResponse)
async def candidates_schedule_slot_form(
    request: Request,
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> HTMLResponse:
    return RedirectResponse(url=f"/app/candidates/{candidate_id}", status_code=302)


@router.post("/{candidate_id}/schedule-slot")
async def candidates_schedule_slot_submit(
    request: Request,
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> Response:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)

    # 1. Resolve Recruiter (Implicit from Session)
    recruiter_raw = payload.get("recruiter_id")
    recruiter_id = _parse_int(str(recruiter_raw)) if recruiter_raw is not None else None
    
    if principal.type == "recruiter":
        recruiter_id = principal.id  # Force implicit ID for recruiters
    
    city_raw = payload.get("city_id")
    date = payload.get("date")
    time = payload.get("time")
    send_custom_message = payload.get("send_custom_message")
    custom_message = payload.get("custom_message")

    city_id = _parse_int(str(city_raw)) if city_raw is not None else None
    
    if not (recruiter_id and city_id and date and time):
        return PlainTextResponse("Заполните город, дату и время", status_code=400)

    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate = detail["user"]

    async with async_session() as session:
        recruiter = await session.scalar(
            select(Recruiter)
            .options(selectinload(Recruiter.cities))
            .where(Recruiter.id == recruiter_id)
        )
        city = await session.get(City, city_id)

        # 2. City Scoping Validation
        if principal.type == "recruiter" and recruiter:
            allowed_cities = {c.id for c in recruiter.cities}
            if city and city.id not in allowed_cities:
                return PlainTextResponse(f"Ошибка доступа: вы не привязаны к городу {city.name}", status_code=403)

    if recruiter is None or city is None:
        return PlainTextResponse("Некорректные рекрутёр или город", status_code=400)

    slot_tz = city.tz or recruiter.tz or DEFAULT_TZ
    dt_utc = recruiter_time_to_utc(str(date), str(time), slot_tz)
    if not dt_utc:
        return PlainTextResponse("Некорректная дата или время", status_code=400)

    send_flag = str(send_custom_message or "").lower() in {"1", "true", "yes", "on"}
    admin_username = request.session.get("username", "admin")
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)

    try:
        result = await schedule_manual_candidate_slot(
            candidate=candidate,
            recruiter=recruiter,
            city=city,
            dt_utc=dt_utc,
            slot_tz=slot_tz,
            admin_username=admin_username,
            ip_address=ip_address,
            user_agent=user_agent,
            custom_message_sent=send_flag,
            custom_message_text=custom_message if send_flag else None,
            principal=principal,
        )
    except ManualSlotError as exc:
        return PlainTextResponse(str(exc), status_code=400)

    slot_id = result.slot.id if result.slot else None
    return JSONResponse({"ok": True, "slot_id": slot_id})


@router.get("/{candidate_id}/schedule-intro-day", response_class=HTMLResponse)
async def candidates_schedule_intro_day_form(
    request: Request,
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> HTMLResponse:
    return RedirectResponse(url=f"/app/candidates/{candidate_id}", status_code=302)


@router.post("/{candidate_id}/assign-city", response_class=HTMLResponse)
async def candidates_assign_city(
    request: Request,
    candidate_id: int,
    city_id: Optional[int] = Form(None),
    principal: Principal = Depends(require_principal),
) -> HTMLResponse:
    return RedirectResponse(url=f"/app/candidates/{candidate_id}", status_code=303)


@router.post("/{candidate_id}/schedule-intro-day")
async def candidates_schedule_intro_day_submit(
    request: Request,
    candidate_id: int,
    principal: Principal = Depends(require_principal),
) -> Response:
    """Create intro_day slot and send invitation to candidate"""
    from backend.domain.repositories import add_outbox_notification

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)
    date = payload.get("date")
    time = payload.get("time")

    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        raise HTTPException(status_code=404, detail="Candidate not found")

    user = detail["user"]
    candidate_tg_id = user.telegram_user_id or user.telegram_id
    errors = []

    city_record = await _load_city_with_recruiters(user.city)
    latest_slot = None
    if (candidate_tg_id or user.candidate_id) and city_record is None:
        async with async_session() as session:
            latest_slot = await session.scalar(
                select(Slot)
                .where(
                    or_(
                        Slot.candidate_id == user.candidate_id,
                        Slot.candidate_tg_id == candidate_tg_id,
                    )
                )
                .order_by(Slot.start_utc.desc(), Slot.id.desc())
            )
            if latest_slot:
                fallback_city_id = latest_slot.candidate_city_id or latest_slot.city_id
                if fallback_city_id:
                    city_record = await session.get(
                        City,
                        fallback_city_id,
                        options=(selectinload(City.recruiters),),
                    )

    recruiter = _select_primary_recruiter(city_record)
    if recruiter is None:
        async with async_session() as session:
            if user.responsible_recruiter_id:
                recruiter = await session.get(Recruiter, user.responsible_recruiter_id)
            if recruiter is None:
                if latest_slot is None and (candidate_tg_id or user.candidate_id):
                    latest_slot = await session.scalar(
                        select(Slot)
                        .where(
                            or_(
                                Slot.candidate_id == user.candidate_id,
                                Slot.candidate_tg_id == candidate_tg_id,
                            )
                        )
                        .order_by(Slot.start_utc.desc(), Slot.id.desc())
                    )
                if latest_slot and latest_slot.recruiter_id:
                    recruiter = await session.get(Recruiter, latest_slot.recruiter_id)
    slot_tz = (
        getattr(city_record, "tz", None)
        or (getattr(recruiter, "tz", None) if recruiter else None)
        or DEFAULT_TZ
    )
    tz_label = tz_display(slot_tz)

    if principal.type == "recruiter" and recruiter and recruiter.id != principal.id:
        errors.append("Недостаточно прав для назначения ознакомительного дня другому рекрутёру.")
    if not candidate_tg_id:
        errors.append("У кандидата нет Telegram ID")
    if not date or not time:
        errors.append("Укажите дату и время ознакомительного дня")
    if city_record is None:
        errors.append("Не удалось определить город кандидата. Укажите город в карточке кандидата.")
    elif recruiter is None:
        errors.append("К городу не привязан ни один активный рекрутёр. Добавьте рекрутёра на странице города.")

    dt_utc = None
    if not errors:
        dt_utc = recruiter_time_to_utc(date, time, slot_tz)
        if not dt_utc:
            errors.append("Некорректная дата или время")

    if errors:
        return PlainTextResponse("; ".join(errors), status_code=400)

    custom_message = payload.get("custom_message")
    custom_message = str(custom_message).strip() if custom_message else ""
    if not custom_message:
        template_source = (
            getattr(city_record, "intro_day_template", None)
            or DEFAULT_INTRO_DAY_INVITATION_TEMPLATE
        )
        custom_message = render_intro_day_invitation(
            template_source,
            candidate_fio=user.fio or "Кандидат",
            date_str=str(date),
            time_str=str(time),
        )

    async with async_session() as session:
        city_id = city_record.id
        candidate_tz = slot_tz

        # Check if intro_day slot already exists for this candidate+recruiter
        existing_slot_query = select(Slot).where(
            Slot.candidate_tg_id == candidate_tg_id,
            Slot.recruiter_id == recruiter.id,
            Slot.purpose == "intro_day",
        )
        existing_slot_result = await session.execute(existing_slot_query)
        existing_slot = existing_slot_result.scalar_one_or_none()

        if existing_slot:
            errors.append(
                f"Ознакомительный день уже назначен для этого кандидата с рекрутером {recruiter.name}. "
                f"Дата: {existing_slot.start_utc.strftime('%d.%m.%Y %H:%M')} UTC"
            )
            return PlainTextResponse("; ".join(errors), status_code=400)

        # Create intro_day slot
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city_id,
            candidate_city_id=city_id,
            purpose="intro_day",
            tz_name=slot_tz,
            start_utc=dt_utc,
            duration_min=DEFAULT_INTRO_DAY_DURATION_MIN,
            status=SlotStatus.BOOKED,
            candidate_id=user.candidate_id,
            candidate_tg_id=candidate_tg_id,
            candidate_fio=user.fio,
            candidate_tz=candidate_tz,
            intro_address=None,
            intro_contact=None,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        # Mark candidate as приглашён на ОД даже если предыдущие этапы не были сохранены
        try:
            from backend.domain.candidates.status_service import set_status_intro_day_scheduled
            await set_status_intro_day_scheduled(candidate_tg_id, force=True)
        except Exception:
            logger.exception(
                "Failed to update candidate status to intro_day_scheduled",
                extra={"candidate_id": candidate_id, "telegram_id": candidate_tg_id},
            )

        # Send invitation notification
        # First, mark any old intro_day_invitation notifications as stale (to avoid idempotency issues)
        try:
            from sqlalchemy import update
            stale_update = (
                update(OutboxNotification)
                .where(
                    OutboxNotification.candidate_tg_id == candidate_tg_id,
                    OutboxNotification.type == "intro_day_invitation",
                    OutboxNotification.booking_id != slot.id,  # Only old notifications
                )
                .values(status="failed", last_error="stale:replaced_by_new_intro_day")
            )
            await session.execute(stale_update)
            await session.commit()
        except Exception:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Failed to mark old intro_day notifications as stale")

        try:
            outbox_payload = {}
            if custom_message:
                outbox_payload["custom_message"] = custom_message
            await add_outbox_notification(
                notification_type="intro_day_invitation",
                booking_id=slot.id,
                candidate_tg_id=candidate_tg_id,
                payload=outbox_payload,
            )
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Failed to enqueue intro day invitation", extra={"slot_id": slot.id})

        # Schedule reminders
        try:
            from backend.apps.bot.reminders import get_reminder_service
            reminder_service = get_reminder_service()
            await reminder_service.schedule_for_slot(slot.id, skip_confirmation_prompts=False)
        except Exception:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Failed to schedule reminders for intro day", extra={"slot_id": slot.id})

    return JSONResponse({"ok": True, "slot_id": slot.id})


@router.post("/{candidate_id}/actions/{action_key}")
async def api_candidate_action(
    candidate_id: int,
    action_key: str,
    request: Request,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    
    # 1. Get candidate and allowed actions
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # 2. Find matching action definition
    actions = detail.get("candidate_actions", [])
    action_def = next((a for a in actions if a.key == action_key), None)
    
    if not action_def:
        # Fallback: check if it's a legacy or special action not in the list but valid?
        # For now, strict validation against allowed actions for current status
        logger.warning(f"Action {action_key} not allowed for candidate {candidate_id}")
        return JSONResponse(
            {"ok": False, "message": "Действие недоступно в текущем статусе"}, 
            status_code=400
        )

    target_status = action_def.target_status
    
    if not target_status:
        # Action without status change (e.g. just logic)
        # Currently not implemented for generic handler
        return JSONResponse({"ok": True, "message": "Action executed"})

    # 3. Execute status change
    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id, 
        target_status, 
        bot_service=bot_service, 
        principal=principal
    )
    
    if not ok:
        return JSONResponse({"ok": False, "message": message}, status_code=400)
        
    # 4. Handle side effects (Bot)
    if dispatch and dispatch.plan:
        background_tasks.add_task(execute_bot_dispatch, dispatch.plan, stored_status or "", bot_service)
        
    return JSONResponse({
        "ok": True, 
        "message": message, 
        "status": stored_status,
        "action": action_key
    })
