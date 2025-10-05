from typing import Optional

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError

from backend.apps.admin_ui.config import templates
from backend.apps.admin_ui.services.candidates import (
    candidate_filter_options,
    delete_candidate,
    get_candidate_detail,
    list_candidates,
    toggle_candidate_activity,
    update_candidate,
    upsert_candidate,
)

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
) -> HTMLResponse:
    is_active = _parse_bool(active)
    tests_flag = _parse_bool(has_tests)
    messages_flag = _parse_bool(has_messages)

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
    )

    context = {
        "request": request,
        **data,
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
