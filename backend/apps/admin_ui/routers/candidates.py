import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Form, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.config import templates
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
)
from backend.apps.admin_ui.services.test2_invites import (
    create_test2_invite,
    get_latest_test2_invite,
    revoke_test2_invite,
    summarize_invite,
)
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.slots import (
    execute_bot_dispatch,
    schedule_manual_candidate_slot,
    schedule_manual_candidate_slot_silent,
    ManualSlotError,
    recruiters_for_slot_form,
)
from backend.apps.bot.services import approve_slot_and_notify
from backend.apps.admin_ui.security import require_csrf_token
from backend.apps.admin_ui.utils import fmt_local
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.core.sanitizers import sanitize_plain_text
from backend.core.time_utils import parse_form_datetime
from backend.core.audit import log_audit_action
from backend.domain.candidates.models import User
from backend.domain.models import Slot, City, Recruiter, SlotStatus, OutboxNotification
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


class CandidateStatusPayload(BaseModel):
    status: str


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
) -> HTMLResponse:
    is_active = _parse_bool(active)
    tests_flag = _parse_bool(has_tests)
    messages_flag = _parse_bool(has_messages)

    parsed_date_from = _parse_date(date_from)
    parsed_date_to = _parse_date(date_to)
    parsed_recruiter_id = _parse_int(recruiter_id)
    normalized_calendar_mode = "day"
    active_calendar_mode: Optional[str] = normalized_calendar_mode if view == "calendar" else None
    pipeline_slug = (pipeline or DEFAULT_PIPELINE).strip().lower()
    if pipeline_slug not in PIPELINE_DEFINITIONS:
        pipeline_slug = DEFAULT_PIPELINE

    data = await list_candidates(
        page=page,
        per_page=per_page,
        search=q,
        city=city,
        is_active=is_active,
        rating=rating,
        has_tests=tests_flag,
        has_messages=messages_flag,
        stage=stage,
        statuses=statuses,
        recruiter_id=parsed_recruiter_id,
        city_ids=city_ids,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        test1_status=test1_status,
        test2_status=test2_status,
        sort=sort,
        sort_dir=sort_dir,
        calendar_mode=active_calendar_mode,
        pipeline=pipeline_slug,
    )

    filter_options = await candidate_filter_options()
    pipeline_statuses = set(PIPELINE_DEFINITIONS[pipeline_slug]["statuses"])
    filter_options["statuses"] = [
        option
        for option in (filter_options.get("statuses") or [])
        if option["slug"] in pipeline_statuses
    ]
    pipeline_options = [
        {"slug": slug, "label": cfg["label"]}
        for slug, cfg in PIPELINE_DEFINITIONS.items()
    ]

    filters_state = data.get("filters", {})
    filter_chips = []

    search_term = filters_state.get("search")
    if search_term:
        filter_chips.append({
            "label": "Поиск",
            "value": search_term,
            "icon": "🔍",
            "tone": "primary",
        })

    status_lookup = {item["slug"]: item for item in filter_options.get("statuses", [])}
    for slug in filters_state.get("statuses", []) or []:
        meta = status_lookup.get(slug)
        if not meta:
            continue
        filter_chips.append({
            "label": meta.get("label", slug),
            "icon": meta.get("icon"),
            "tone": meta.get("tone", "info"),
        })

    recruiter_lookup = {item["id"]: item for item in filter_options.get("recruiters", [])}
    recruiter_id_value = filters_state.get("recruiter_id")
    if recruiter_id_value and recruiter_lookup.get(recruiter_id_value):
        recruiter_meta = recruiter_lookup[recruiter_id_value]
        filter_chips.append({
            "label": "Рекрутёр",
            "value": recruiter_meta.get("name"),
            "icon": "👤",
            "tone": "info",
        })

    city_lookup = {item["id"]: item for item in filter_options.get("city_choices", [])}
    for city_id_value in filters_state.get("city_ids", []) or []:
        city_meta = city_lookup.get(city_id_value)
        if not city_meta:
            continue
        filter_chips.append({
            "label": "Город",
            "value": city_meta.get("name"),
            "icon": "🏙️",
            "tone": "muted",
        })

    date_from_state = filters_state.get("date_from")
    date_to_state = filters_state.get("date_to")
    if date_from_state:
        filter_chips.append({
            "label": "С",
            "value": date_from_state.strftime("%d.%m.%Y"),
            "icon": "📅",
            "tone": "muted",
        })
    if date_to_state:
        filter_chips.append({
            "label": "По",
            "value": date_to_state.strftime("%d.%m.%Y"),
            "icon": "📅",
            "tone": "muted",
        })

    test_status_lookup = {item["slug"]: item for item in filter_options.get("test_statuses", [])}
    test1_value = filters_state.get("test1_status")
    if test1_value:
        meta = test_status_lookup.get(test1_value)
        filter_chips.append({
            "label": "Тест 1",
            "value": meta.get("label") if meta else test1_value,
            "icon": meta.get("icon") if meta else "📋",
            "tone": "info",
        })
    test2_value = filters_state.get("test2_status")
    if test2_value:
        meta = test_status_lookup.get(test2_value)
        filter_chips.append({
            "label": "Тест 2",
            "value": meta.get("label") if meta else test2_value,
            "icon": meta.get("icon") if meta else "📋",
            "tone": "info",
        })

    sort_value = filters_state.get("sort")
    sort_dir_value = filters_state.get("sort_dir")
    if sort_value and (sort_value != "event" or sort_dir_value != "asc"):
        sort_labels = {
            "event": "Ближайшее событие",
            "activity": "Активность",
            "name": "Имя",
            "status": "Статус",
        }
        label = sort_labels.get(sort_value, sort_value)
        if sort_dir_value and sort_dir_value.lower() == "desc":
            label = f"{label} ↓"
        else:
            label = f"{label} ↑"
        filter_chips.append({
            "label": "Сортировка",
            "value": label,
            "icon": "↕️",
            "tone": "primary",
        })

    status_labels = {
        item["slug"]: item.get("label", item["slug"])
        for item in filter_options.get("statuses", [])
    }

    context = {
        "request": request,
        **data,
        "filter_options": filter_options,
        "filter_chips": filter_chips,
        "selected_view": view.lower(),
        "calendar_mode": normalized_calendar_mode,
        "status_labels": status_labels,
        "selected_pipeline": pipeline_slug,
        "pipeline_options": pipeline_options,
    }
    return templates.TemplateResponse(request, "candidates_list.html", context)

@router.get("/detailization", response_class=HTMLResponse)
async def candidates_detailization(
    request: Request,
    status: Optional[str] = Query(default=None, description="hired or not_hired"),
    q: Optional[str] = Query(default=None, alias="search"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=5, le=200),
) -> HTMLResponse:
    status_filter = status if status in {"hired", "not_hired"} else None
    statuses = [status_filter] if status_filter else ["hired", "not_hired"]
    result = await list_candidates(
        page=page,
        per_page=per_page,
        search=q,
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        stage=None,
        statuses=statuses,
        recruiter_id=None,
        city_ids=None,
        date_from=None,
        date_to=None,
        test1_status=None,
        test2_status=None,
        sort=None,
        sort_dir=None,
        calendar_mode=None,
        pipeline="interview",
    )
    views = result.get("views")
    list_groups = {}
    if views:
        list_groups = getattr(views, "list", None) or (views.get("list") if isinstance(views, dict) else {}) or {}
    summary_block = result.get("summary", {}) if result else {}
    status_totals = summary_block.get("status_totals", {}) if isinstance(summary_block, dict) else {}
    status_labels = STATUS_DEFINITIONS
    context = {
        "request": request,
        "list_groups": list_groups,
        "selected_status": status_filter or "all",
        "search_query": (q or "").strip(),
        "total": result.get("total", 0) if result else 0,
        "status_totals": status_totals,
        "status_labels": status_labels,
        "page": result.get("page", page),
        "pages_total": result.get("pages_total", 1),
    }
    return templates.TemplateResponse(request, "candidates_detailization.html", context)


@router.get("/new", response_class=HTMLResponse)
async def candidates_new(request: Request) -> HTMLResponse:
    options = await candidate_filter_options()
    context = {
        "request": request,
        "cities": options.get("cities", []),
        "city_choices": options.get("city_choices", []),
        "recruiters": options.get("recruiters", []),
    }
    return templates.TemplateResponse(request, "candidates_new.html", context)


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
):
    active_flag = _parse_bool(is_active)
    interview_dt = None
    interview_tz = None
    interview_city = None
    interview_recruiter = None
    recruiter_id_value = _parse_int(responsible_recruiter_id)
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
async def candidates_invite_token(candidate_id: int) -> RedirectResponse:
    token = await generate_candidate_invite_token(candidate_id)
    if not token:
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?error=invite_token",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/candidates/{candidate_id}?invite_token={quote_plus(token)}",
        status_code=303,
    )


@router.post("/{candidate_id}/test2/invite", response_class=JSONResponse)
async def candidates_test2_invite(
    request: Request,
    candidate_id: int,
    csrf_ok: None = Depends(require_csrf_token),
) -> JSONResponse:
    _ = csrf_ok
    admin_username = getattr(request.state, "admin_username", None)
    result = await create_test2_invite(candidate_id, created_by=admin_username)
    if not result:
        raise HTTPException(status_code=404, detail="Candidate not found")
    token, invite = result
    base_url = str(request.base_url).rstrip("/")
    link = f"{base_url}/t/test2/{token}"
    payload = summarize_invite(invite) or {}
    payload["expires_at_local"] = (
        fmt_local(invite.expires_at, DEFAULT_TZ) if invite.expires_at else None
    )
    response_payload = {"ok": True, "link": link, "invite": payload}
    return JSONResponse(content=jsonable_encoder(response_payload))


@router.post("/{candidate_id}/test2/invite/{invite_id}/revoke", response_class=JSONResponse)
async def candidates_test2_invite_revoke(
    request: Request,
    candidate_id: int,
    invite_id: int,
    csrf_ok: None = Depends(require_csrf_token),
) -> JSONResponse:
    _ = csrf_ok
    ok = await revoke_test2_invite(candidate_id, invite_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite = await get_latest_test2_invite(candidate_id)
    payload = summarize_invite(invite) if invite else None
    if invite and payload is not None:
        payload["expires_at_local"] = (
            fmt_local(invite.expires_at, DEFAULT_TZ) if invite.expires_at else None
        )
    response_payload = {"ok": True, "invite": payload}
    return JSONResponse(content=jsonable_encoder(response_payload))


@router.get("/{candidate_id}", response_class=HTMLResponse)
async def candidates_detail(request: Request, candidate_id: int) -> HTMLResponse:
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return RedirectResponse(url="/candidates", status_code=303)
    context = {
        "request": request,
        "invite_token": request.query_params.get("invite_token"),
        **detail,
    }
    return templates.TemplateResponse(request, "candidates_detail.html", context)


@router.post("/{candidate_id}/update")
async def candidates_update(
    candidate_id: int,
    telegram_id: Optional[str] = Form(None),
    fio: str = Form(...),
    city: str = Form(""),
    phone: str = Form(""),
    is_active: Optional[str] = Form(None),
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
        )
    except ValueError:
        success = False
    except IntegrityError:
        success = False

    if not success:
        return RedirectResponse(url=f"/candidates/{candidate_id}?error=update", status_code=303)
    return RedirectResponse(url=f"/candidates/{candidate_id}?saved=1", status_code=303)


@router.post("/{candidate_id}/toggle")
async def candidates_toggle(candidate_id: int, active: str = Form("true")):
    flag = _parse_bool(active)
    if flag is None:
        flag = True
    await toggle_candidate_activity(candidate_id, active=flag)
    return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=303)


@router.post("/{candidate_id}/status", response_model=None)
async def candidates_set_status(
    request: Request,
    candidate_id: int,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    payload: Optional[CandidateStatusPayload] = Body(None),
    status: Optional[str] = Form(None),
    reject_reason: Optional[str] = Form(None),
    reject_comment: Optional[str] = Form(None),
    _: None = Depends(require_csrf_token),
) -> RedirectResponse | JSONResponse:
    """Update candidate status via UI or AJAX/kanban board."""
    allowed_form_statuses = {
        "hired",
        "not_hired",
        "intro_day_declined_day_of",
        "intro_day_declined_invitation",
        "interview_declined",
        "test2_failed",
    }

    status_slug = None
    if payload and payload.status:
        status_slug = payload.status
    elif status:
        status_slug = status

    if not status_slug:
        if payload:
            return JSONResponse(
                {"ok": False, "message": "Статус обязателен"}, status_code=400
            )
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?error=invalid_status",
            status_code=303,
        )

    status_slug = status_slug.strip()
    normalized_slug = status_slug.lower()
    is_form_submission = payload is None

    if is_form_submission and normalized_slug not in allowed_form_statuses:
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?error=invalid_status",
            status_code=303,
        )

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id, normalized_slug, bot_service=bot_service
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

        return RedirectResponse(url=f"/candidates/{candidate_id}?status_updated=1", status_code=303)

    status_code = 200 if ok else 400
    payload_response = {
        "ok": ok,
        "message": message or "",
        "status": stored_status,
    }
    response = JSONResponse(payload_response, status_code=status_code)
    response.headers["X-Bot"] = bot_header
    return response


@router.post("/{candidate_id}/interview-notes")
async def candidates_save_interview_notes(
    request: Request,
    candidate_id: int,
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

    success = await save_interview_notes(
        candidate_id,
        interviewer_name=interviewer_name,
        data=payload,
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
async def candidates_download_interview_notes(candidate_id: int) -> PlainTextResponse:
    detail = await get_candidate_detail(candidate_id)
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
async def candidates_approve_slot(candidate_id: int, slot_id: int):
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
        if user.telegram_id is None:
            return _redirect("telegram_missing", "Для кандидата не указан Telegram ID.")
        slot = await session.get(Slot, slot_id)
        if not slot:
            return _redirect("slot_missing", "Слот не найден или уже удалён.")
        if slot.candidate_tg_id != user.telegram_id:
            return _redirect("invalid_candidate", "Слот относится к другому кандидату.")

    result = await approve_slot_and_notify(slot_id, force_notify=True)
    return _redirect(result.status, result.message)


@router.post("/{candidate_id}/delete")
async def candidates_delete(candidate_id: int):
    await delete_candidate(candidate_id)
    return RedirectResponse(url="/candidates", status_code=303)


@router.post("/delete-all")
async def candidates_delete_all():
    deleted = await delete_all_candidates()
    return RedirectResponse(
        url=f"/candidates?bulk_deleted={deleted}",
        status_code=303,
    )


@router.post("/{candidate_id}/status")
async def candidates_set_status(
    candidate_id: int,
    payload: CandidateStatusPayload,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
):
    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate_id,
        payload.status,
        bot_service=bot_service,
    )
    status_code = 200 if ok else 400
    if not ok and "не найден" in (message or "").lower():
        status_code = 404

    bot_header = "skipped:not_applicable"
    if dispatch is not None:
        bot_header = getattr(dispatch, "status", "skipped:not_applicable")
        plan = getattr(dispatch, "plan", None)
        if ok and plan is not None:
            background_tasks.add_task(execute_bot_dispatch, plan, stored_status or "", bot_service)

    response = JSONResponse(
        {
            "ok": ok,
            "message": message,
            "status": stored_status,
        },
        status_code=status_code,
    )
    response.headers["X-Bot"] = bot_header
    return response


@router.get("/{candidate_id}/reports/{report_key}")
async def candidates_download_report(candidate_id: int, report_key: str):
    if report_key not in {"test1", "test2"}:
        raise HTTPException(status_code=404)
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        raise HTTPException(status_code=404)
    user = detail["user"]
    field = "test1_report_url" if report_key == "test1" else "test2_report_url"
    rel_path = getattr(user, field, None)
    if not rel_path:
        raise HTTPException(status_code=404)
    settings = get_settings()
    file_path = Path(settings.data_dir) / rel_path
    if not file_path.is_file():
        raise HTTPException(status_code=404)
    media_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "text/plain"
    return FileResponse(file_path, filename=file_path.name, media_type=media_type)


@router.get("/{candidate_id}/schedule-slot", response_class=HTMLResponse)
async def candidates_schedule_slot_form(request: Request, candidate_id: int) -> HTMLResponse:
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return RedirectResponse(url="/candidates", status_code=303)

    candidate = detail["user"]
    if not candidate.telegram_id:
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?slot_scheduled=missing_telegram",
            status_code=303,
        )

    recruiters = await recruiters_for_slot_form()
    cities = await _list_active_cities()
    default_city_id = None
    if candidate.city:
        city_record = await find_city_by_plain_name(candidate.city)
        if city_record:
            default_city_id = city_record.id

    context = {
        "request": request,
        "candidate": candidate,
        "recruiters": recruiters,
        "cities": cities,
        "errors": [],
        "form_values": {
            "recruiter_id": None,
            "city_id": default_city_id,
            "date": "",
            "time": "10:00",
        },
    }
    return templates.TemplateResponse(request, "schedule_manual_slot.html", context)


@router.post("/{candidate_id}/schedule-slot", response_class=HTMLResponse)
async def candidates_schedule_slot_submit(
    request: Request,
    candidate_id: int,
    recruiter_id: int = Form(...),
    city_id: int = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    send_custom_message: Optional[str] = Form(None),
    custom_message: Optional[str] = Form(None),
) -> HTMLResponse:
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return RedirectResponse(url="/candidates", status_code=303)

    candidate = detail["user"]
    if not candidate.telegram_id:
        return RedirectResponse(
            url=f"/candidates/{candidate_id}?slot_scheduled=missing_telegram",
            status_code=303,
        )

    recruiters = await recruiters_for_slot_form()
    cities = await _list_active_cities()

    recruiter = next((entry["rec"] for entry in recruiters if entry["rec"].id == recruiter_id), None)
    city = next((entry for entry in cities if entry.id == city_id), None)

    errors: List[str] = []
    if recruiter is None:
        errors.append("Выберите действующего рекрутёра.")
    if city is None:
        errors.append("Выберите город для собеседования.")

    app_timezone = get_settings().timezone or DEFAULT_TZ
    slot_tz = (getattr(city, "tz", None) if city else None) or app_timezone
    dt_utc = None
    if not errors:
        try:
            dt_utc = parse_form_datetime(f"{date}T{time}", slot_tz)
        except ValueError:
            errors.append("Укажите корректные дату и время.")

    if errors:
        context = {
            "request": request,
            "candidate": candidate,
            "recruiters": recruiters,
            "cities": cities,
            "errors": errors,
            "form_values": {
                "recruiter_id": recruiter_id,
                "city_id": city_id,
                "date": date,
                "time": time,
            },
        }
        return templates.TemplateResponse(
            request, "schedule_manual_slot.html", context, status_code=400
        )

    assert recruiter is not None
    assert city is not None

    # Extract audit information
    admin_username = request.session.get("username", "admin")
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    custom_message_sent = bool(send_custom_message)
    custom_message_text = custom_message.strip() if custom_message and custom_message_sent else None

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
            custom_message_sent=custom_message_sent,
            custom_message_text=custom_message_text,
        )
    except ManualSlotError as exc:
        context = {
            "request": request,
            "candidate": candidate,
            "recruiters": recruiters,
            "cities": cities,
            "errors": [str(exc)],
            "form_values": {
                "recruiter_id": recruiter_id,
                "city_id": city_id,
                "date": date,
                "time": time,
            },
        }
        return templates.TemplateResponse(
            request, "schedule_manual_slot.html", context, status_code=400
        )

    status_param = "success"
    if result.status == "notify_failed":
        status_param = "notify_failed"
    elif result.status == "already":
        status_param = "success"

    return RedirectResponse(
        url=f"/candidates/{candidate_id}?slot_scheduled={status_param}",
        status_code=303,
    )


@router.get("/{candidate_id}/schedule-intro-day", response_class=HTMLResponse)
async def candidates_schedule_intro_day_form(
    request: Request,
    candidate_id: int,
) -> HTMLResponse:
    """Show form to schedule an intro day for a candidate"""
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return RedirectResponse(url="/candidates", status_code=303)

    user = detail["user"]

    # Prevent scheduling duplicates if intro day already exists
    if detail.get("has_intro_day_slot", False):
        return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=303)

    city_record = await _load_city_with_recruiters(user.city)
    recruiter = _select_primary_recruiter(city_record)
    city_tz = None
    if city_record:
        city_tz = getattr(city_record, "tz", None)
    if not city_tz and recruiter is not None:
        city_tz = getattr(recruiter, "tz", None)
    city_tz = city_tz or DEFAULT_TZ
    tz_label = tz_display(city_tz)
    cities_list = await _list_active_cities()

    context = {
        "request": request,
        "candidate": user,
        "city": city_record,
        "city_timezone": city_tz,
        "city_timezone_label": tz_label,
        "city_missing": city_record is None,
        "recruiter_missing": city_record is not None and recruiter is None,
        "errors": [],
        "cities": cities_list,
    }
    return templates.TemplateResponse(request, "schedule_intro_day.html", context)


@router.post("/{candidate_id}/assign-city", response_class=HTMLResponse)
async def candidates_assign_city(
    request: Request,
    candidate_id: int,
    city_id: int = Form(...),
) -> HTMLResponse:
    """Assign city to candidate inline to continue intro day scheduling."""

    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return RedirectResponse(url="/candidates", status_code=303)

    user = detail["user"]
    cities_list = await _list_active_cities()

    async with async_session() as session:
        city = await session.get(City, city_id)
        if city is None:
            context = {
                "request": request,
                "candidate": user,
                "city": None,
                "city_timezone": DEFAULT_TZ,
                "city_timezone_label": tz_display(DEFAULT_TZ),
                "city_missing": True,
                "recruiter_missing": False,
                "errors": ["Город не найден. Попробуйте выбрать другой."],
                "cities": cities_list,
            }
            return templates.TemplateResponse(request, "schedule_intro_day.html", context, status_code=400)

        await update_candidate(
            user.id,
            telegram_id=user.telegram_id,
            fio=user.fio,
            city=getattr(city, "name_plain", None) or city.name,
            is_active=user.is_active,
        )

    return RedirectResponse(url=f"/candidates/{candidate_id}/schedule-intro-day", status_code=303)


@router.post("/{candidate_id}/schedule-intro-day")
async def candidates_schedule_intro_day_submit(
    request: Request,
    candidate_id: int,
    date: str = Form(...),
    time: str = Form(...),
    bot_service: BotService = Depends(provide_bot_service),
) -> HTMLResponse:
    """Create intro_day slot and send invitation to candidate"""
    from backend.domain.repositories import reserve_slot
    from backend.apps.admin_ui.services.slots import recruiter_time_to_utc
    from backend.domain.repositories import add_outbox_notification

    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return RedirectResponse(url="/candidates", status_code=303)

    user = detail["user"]
    errors = []
    cities_list = await _list_active_cities()

    city_record = await _load_city_with_recruiters(user.city)
    recruiter = _select_primary_recruiter(city_record)
    slot_tz = (
        getattr(city_record, "tz", None)
        or (getattr(recruiter, "tz", None) if recruiter else None)
        or DEFAULT_TZ
    )
    tz_label = tz_display(slot_tz)

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
        context = {
            "request": request,
            "candidate": user,
            "city": city_record,
            "city_timezone": slot_tz,
            "city_timezone_label": tz_label,
            "city_missing": city_record is None,
            "recruiter_missing": city_record is not None and recruiter is None,
            "errors": errors,
            "cities": cities_list,
        }
        return templates.TemplateResponse(request, "schedule_intro_day.html", context, status_code=400)

    async with async_session() as session:
        city_id = city_record.id
        candidate_tz = slot_tz

        # Check if intro_day slot already exists for this candidate+recruiter
        existing_slot_query = select(Slot).where(
            Slot.candidate_tg_id == user.telegram_id,
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
            context = {
                "request": request,
                "candidate": user,
                "city": city_record,
                "city_timezone": slot_tz,
                "city_timezone_label": tz_label,
                "city_missing": False,
                "recruiter_missing": False,
                "errors": errors,
                "cities": cities_list,
            }
            return templates.TemplateResponse(request, "schedule_intro_day.html", context, status_code=400)

        # Create intro_day slot
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city_id,
            candidate_city_id=city_id,
            purpose="intro_day",
            tz_name=slot_tz,
            start_utc=dt_utc,
            status=SlotStatus.BOOKED,
            candidate_tg_id=user.telegram_id,
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
            await set_status_intro_day_scheduled(user.telegram_id, force=True)
        except Exception:
            logger.exception(
                "Failed to update candidate status to intro_day_scheduled",
                extra={"candidate_id": candidate_id, "telegram_id": user.telegram_id},
            )

        # Send invitation notification
        # First, mark any old intro_day_invitation notifications as stale (to avoid idempotency issues)
        try:
            from sqlalchemy import update
            stale_update = (
                update(OutboxNotification)
                .where(
                    OutboxNotification.candidate_tg_id == user.telegram_id,
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
            await add_outbox_notification(
                notification_type="intro_day_invitation",
                booking_id=slot.id,
                candidate_tg_id=user.telegram_id,
                payload={},
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

    return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=303)
