from __future__ import annotations

from typing import Any

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from backend.apps.admin_ui.security import Principal, require_principal, require_csrf_token
from backend.apps.admin_ui.services.detailization import (
    create_manual_detailization_entry,
    delete_detailization_entry,
    export_detailization_csv,
    list_detailization,
    update_detailization_entry,
)

router = APIRouter(prefix="/api/detailization", tags=["detailization"])
principal_dep = Depends(require_principal)


def _parse_query_datetime(value: str | None, *, end: bool = False) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    try:
        if "T" in raw:
            parsed = datetime.fromisoformat(raw)
        else:
            parsed = datetime.fromisoformat(f"{raw}T{'23:59:59.999999' if end else '00:00:00'}")
    except ValueError as exc:
        raise ValueError("Некорректный формат даты") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class DetailizationUpdatePayload(BaseModel):
    expert_name: str | None = None
    is_attached: bool | None = None
    final_outcome: str | None = None
    final_outcome_reason: str | None = None
    assigned_at: str | None = None
    conducted_at: str | None = None
    recruiter_id: int | None = None
    city_id: int | None = None


class DetailizationCreatePayload(BaseModel):
    candidate_id: int
    recruiter_id: int | None = None
    city_id: int | None = None
    assigned_at: str | None = None
    conducted_at: str | None = None
    expert_name: str | None = None
    is_attached: bool | None = None
    final_outcome: str | None = None
    final_outcome_reason: str | None = None


@router.get("")
async def api_detailization_list(
    principal: Principal = principal_dep,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> JSONResponse:
    try:
        parsed_from = _parse_query_datetime(date_from, end=False)
        parsed_to = _parse_query_datetime(date_to, end=True)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    payload = await list_detailization(principal, date_from=parsed_from, date_to=parsed_to)
    return JSONResponse(payload)


@router.get("/export.csv")
async def api_detailization_export(
    principal: Principal = principal_dep,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> Response:
    try:
        parsed_from = _parse_query_datetime(date_from, end=False)
        parsed_to = _parse_query_datetime(date_to, end=True)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    filename, content = await export_detailization_csv(
        principal,
        date_from=parsed_from,
        date_to=parsed_to,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{entry_id}")
async def api_detailization_update(
    entry_id: int,
    request: Request,
    payload: DetailizationUpdatePayload,
    principal: Principal = principal_dep,
) -> JSONResponse:
    _ = await require_csrf_token(request)
    result = await update_detailization_entry(entry_id, payload.model_dump(), principal=principal)
    return JSONResponse(result)


@router.post("")
async def api_detailization_create(
    request: Request,
    payload: DetailizationCreatePayload,
    principal: Principal = principal_dep,
) -> JSONResponse:
    _ = await require_csrf_token(request)
    result = await create_manual_detailization_entry(payload.model_dump(), principal=principal)
    return JSONResponse(result, status_code=201 if result.get("ok") else 400)


@router.delete("/{entry_id}")
async def api_detailization_delete(
    entry_id: int,
    request: Request,
    principal: Principal = principal_dep,
) -> JSONResponse:
    _ = await require_csrf_token(request)
    result = await delete_detailization_entry(entry_id, principal=principal)
    return JSONResponse(result)
