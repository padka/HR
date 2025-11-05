from typing import List, Optional

from pathlib import Path

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.candidates import (
    candidate_filter_options,
    delete_candidate,
    get_candidate_detail,
    list_candidates,
    toggle_candidate_activity,
    update_candidate,
    update_candidate_status,
    upsert_candidate,
)
from backend.core.settings import get_settings
from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.slots import execute_bot_dispatch

router = APIRouter(prefix="/candidates", tags=["candidates"])


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
    view: str = Query("list"),
    calendar_mode: str = Query("week"),
) -> HTMLResponse:
    is_active = _parse_bool(active)
    tests_flag = _parse_bool(has_tests)
    messages_flag = _parse_bool(has_messages)

    parsed_date_from = _parse_date(date_from)
    parsed_date_to = _parse_date(date_to)
    parsed_recruiter_id = _parse_int(recruiter_id)

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
    )

    filter_options = await candidate_filter_options()

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

    context = {
        "request": request,
        **data,
        "filter_options": filter_options,
        "filter_chips": filter_chips,
        "selected_view": view.lower(),
        "calendar_mode": calendar_mode.lower(),
    }
    return templates.TemplateResponse("candidates_list.html", context)


@router.get("/new", response_class=HTMLResponse)
async def candidates_new(request: Request) -> HTMLResponse:
    options = await candidate_filter_options()
    context = {
        "request": request,
        "cities": options.get("cities", []),
    }
    return templates.TemplateResponse("candidates_new.html", context)


@router.post("/create")
async def candidates_create(
    telegram_id: int = Form(...),
    fio: str = Form(...),
    city: str = Form(""),
    is_active: Optional[str] = Form("on"),
):
    active_flag = _parse_bool(is_active)
    try:
        user = await upsert_candidate(
            telegram_id=telegram_id,
            fio=fio,
            city=city or None,
            is_active=True if active_flag is None else active_flag,
        )
    except ValueError:
        return RedirectResponse(url="/candidates/new?error=validation", status_code=303)
    except IntegrityError:
        return RedirectResponse(url="/candidates/new?error=duplicate", status_code=303)

    return RedirectResponse(url=f"/candidates/{user.id}", status_code=303)


@router.get("/{candidate_id}", response_class=HTMLResponse)
async def candidates_detail(request: Request, candidate_id: int) -> HTMLResponse:
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return RedirectResponse(url="/candidates", status_code=303)
    context = {
        "request": request,
        **detail,
    }
    return templates.TemplateResponse("candidates_detail.html", context)


@router.post("/{candidate_id}/update")
async def candidates_update(
    candidate_id: int,
    telegram_id: int = Form(...),
    fio: str = Form(...),
    city: str = Form(""),
    is_active: Optional[str] = Form(None),
):
    active_flag = _parse_bool(is_active)
    try:
        success = await update_candidate(
            candidate_id,
            telegram_id=telegram_id,
            fio=fio,
            city=city or None,
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


@router.post("/{candidate_id}/delete")
async def candidates_delete(candidate_id: int):
    await delete_candidate(candidate_id)
    return RedirectResponse(url="/candidates", status_code=303)


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
