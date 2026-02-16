from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.apps.admin_ui.security import Principal, require_principal, require_csrf_token
from backend.apps.admin_ui.services.detailization import (
    create_manual_detailization_entry,
    list_detailization,
    update_detailization_entry,
)

router = APIRouter(prefix="/api/detailization", tags=["detailization"])
principal_dep = Depends(require_principal)


class DetailizationUpdatePayload(BaseModel):
    expert_name: str | None = None
    column_9: str | None = None
    is_attached: bool | None = None
    conducted_at: str | None = None
    recruiter_id: int | None = None
    city_id: int | None = None


class DetailizationCreatePayload(BaseModel):
    candidate_id: int
    recruiter_id: int | None = None
    city_id: int | None = None
    conducted_at: str | None = None
    expert_name: str | None = None
    column_9: str | None = None
    is_attached: bool | None = None


@router.get("")
async def api_detailization_list(principal: Principal = principal_dep) -> JSONResponse:
    payload = await list_detailization(principal)
    return JSONResponse(payload)


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
