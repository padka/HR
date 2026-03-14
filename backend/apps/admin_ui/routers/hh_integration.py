"""Admin endpoints for direct HH integration management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.apps.admin_ui.security import Principal, require_admin
from backend.core.ai.service import schedule_warm_candidates_ai_outputs
from backend.core.dependencies import AsyncSessionDep
from backend.core.settings import get_settings
from backend.domain.hh_integration import (
    HHApiClient,
    HHApiError,
    apply_refreshed_tokens,
    build_connection_summary,
    build_hh_authorize_url,
    build_webhook_target_url,
    decrypt_access_token,
    decrypt_refresh_token,
    get_connection_for_principal,
    parse_hh_oauth_state,
    upsert_hh_connection,
)
from backend.domain.hh_integration.contracts import DEFAULT_HH_WEBHOOK_ACTIONS
from backend.domain.hh_integration.importer import (
    import_hh_negotiations,
    import_hh_vacancies,
    serialize_import_result,
)
from backend.domain.hh_integration.jobs import (
    enqueue_hh_sync_job,
    list_hh_sync_jobs,
    retry_hh_sync_job,
    serialize_hh_sync_job,
)
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    HHNegotiation,
)

router = APIRouter(prefix="/api/integrations/hh", tags=["hh-integration"])
callback_router = APIRouter(tags=["hh-integration"])
AdminPrincipalDep = Depends(require_admin)


class HHActionExecuteRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


def _iter_hh_actions(actions_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    actions = actions_snapshot.get("actions")
    if not isinstance(actions, list):
        return []
    return [item for item in actions if isinstance(item, dict)]


def _serialize_hh_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": action.get("id"),
        "name": action.get("name"),
        "method": action.get("method"),
        "url": action.get("url"),
        "enabled": bool(action.get("enabled", True)),
        "hidden": bool(action.get("hidden", False)),
        "arguments": action.get("arguments") or [],
        "resulting_employer_state": action.get("resulting_employer_state") or {},
        "sub_actions": [
            {
                "id": sub_action.get("id"),
                "name": sub_action.get("name"),
                "method": sub_action.get("method"),
                "url": sub_action.get("url"),
            }
            for sub_action in action.get("sub_actions") or []
            if isinstance(sub_action, dict)
        ],
    }


def _find_hh_action(actions_snapshot: dict[str, Any], action_id: str) -> dict[str, Any] | None:
    for action in _iter_hh_actions(actions_snapshot):
        if str(action.get("id") or "") == action_id:
            return action
        for sub_action in action.get("sub_actions") or []:
            if isinstance(sub_action, dict) and str(sub_action.get("id") or "") == action_id:
                merged = dict(sub_action)
                merged.setdefault("arguments", action.get("arguments") or [])
                merged.setdefault("resulting_employer_state", action.get("resulting_employer_state") or {})
                return merged
    return None


async def _get_candidate_hh_context(session, candidate_id: int) -> tuple[CandidateExternalIdentity, HHNegotiation]:
    identity = (
        await session.execute(
            select(CandidateExternalIdentity).where(
                CandidateExternalIdentity.candidate_id == candidate_id,
                CandidateExternalIdentity.source == "hh",
            )
        )
    ).scalar_one_or_none()
    if identity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH identity is not linked")

    negotiation = (
        await session.execute(
            select(HHNegotiation)
            .where(HHNegotiation.candidate_identity_id == identity.id)
            .order_by(HHNegotiation.updated_at.desc(), HHNegotiation.id.desc())
        )
    ).scalars().first()
    if negotiation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH negotiation is not imported")
    return identity, negotiation


@router.get("/connection")
async def get_hh_connection(
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    settings = get_settings()
    connection = await get_connection_for_principal(session, principal)
    return {
        "ok": True,
        "enabled": settings.hh_integration_enabled,
        "connected": connection is not None,
        "connection": build_connection_summary(
            connection,
            webhook_base_url=settings.hh_webhook_base_url,
            redirect_uri=settings.hh_redirect_uri,
        ),
    }


async def _finalize_hh_oauth_callback(
    *,
    code: str | None,
    state: str | None,
    error: str | None,
    session,
    current_principal: Principal | None,
    allow_redirect: bool,
):
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"HH OAuth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code or state")

    try:
        parsed = parse_hh_oauth_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if current_principal is not None and (
        parsed.principal_type != current_principal.type or parsed.principal_id != current_principal.id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HH OAuth state principal mismatch")

    principal = Principal(type=parsed.principal_type, id=parsed.principal_id)
    client = HHApiClient()
    try:
        tokens = await client.exchange_authorization_code(code)
        me_payload = await client.get_me(tokens.access_token)
        manager_accounts_payload = await client.get_manager_accounts(tokens.access_token)
    except HHApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": str(exc),
                "status_code": exc.status_code,
                "payload": exc.payload,
            },
        ) from exc

    connection = await upsert_hh_connection(
        session,
        principal=principal,
        tokens=tokens,
        me_payload=me_payload,
        manager_accounts_payload=manager_accounts_payload,
    )
    await session.commit()

    settings = get_settings()
    payload = {
        "ok": True,
        "connection": build_connection_summary(
            connection,
            webhook_base_url=settings.hh_webhook_base_url,
            redirect_uri=settings.hh_redirect_uri,
        ),
        "return_to": parsed.return_to,
    }
    if allow_redirect and parsed.return_to:
        separator = "&" if "?" in parsed.return_to else "?"
        return RedirectResponse(url=f"{parsed.return_to}{separator}hh=connected", status_code=status.HTTP_302_FOUND)
    return JSONResponse(payload)


@router.get("/oauth/authorize")
async def get_hh_authorize_url(
    principal: Principal = AdminPrincipalDep,
    return_to: str | None = Query(default=None),
):
    try:
        authorize_url, state = build_hh_authorize_url(principal, return_to=return_to)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"ok": True, "authorize_url": authorize_url, "state": state}


@router.get("/oauth/callback")
async def hh_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    return await _finalize_hh_oauth_callback(
        code=code,
        state=state,
        error=error,
        session=session,
        current_principal=principal,
        allow_redirect=False,
    )


@callback_router.get("/rest/oauth2-credential/callback", include_in_schema=False)
async def hh_oauth_callback_compat(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session=AsyncSessionDep,
):
    return await _finalize_hh_oauth_callback(
        code=code,
        state=state,
        error=error,
        session=session,
        current_principal=None,
        allow_redirect=True,
    )


@router.post("/oauth/refresh")
async def refresh_hh_connection_tokens(
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")

    client = HHApiClient()
    try:
        tokens = await client.refresh_access_token(decrypt_refresh_token(connection))
    except HHApiError as exc:
        connection.status = "error"
        connection.last_error = str(exc)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": str(exc), "status_code": exc.status_code, "payload": exc.payload},
        ) from exc

    apply_refreshed_tokens(connection, tokens)
    await session.commit()
    settings = get_settings()
    return {
        "ok": True,
        "connection": build_connection_summary(
            connection,
            webhook_base_url=settings.hh_webhook_base_url,
            redirect_uri=settings.hh_redirect_uri,
        ),
    }


@router.get("/webhooks")
async def list_hh_webhooks(
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")

    client = HHApiClient()
    try:
        subscriptions = await client.list_webhook_subscriptions(
            decrypt_access_token(connection),
            manager_account_id=connection.manager_account_id,
        )
    except HHApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": str(exc), "status_code": exc.status_code, "payload": exc.payload},
        ) from exc

    return {"ok": True, "subscriptions": subscriptions}


@router.post("/webhooks/register")
async def register_hh_webhooks(
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")

    settings = get_settings()
    try:
        webhook_url = build_webhook_target_url(
            connection,
            webhook_base_url=settings.hh_webhook_base_url,
            redirect_uri=settings.hh_redirect_uri,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    client = HHApiClient()
    try:
        payload = await client.create_webhook_subscription(
            decrypt_access_token(connection),
            url=webhook_url,
            manager_account_id=connection.manager_account_id,
            action_types=DEFAULT_HH_WEBHOOK_ACTIONS,
        )
    except HHApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": str(exc), "status_code": exc.status_code, "payload": exc.payload},
        ) from exc

    return {
        "ok": True,
        "webhook_url": webhook_url,
        "actions": list(DEFAULT_HH_WEBHOOK_ACTIONS),
        "subscription": payload,
    }


@router.post("/import/vacancies")
async def import_hh_vacancies_route(
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")

    try:
        result = await import_hh_vacancies(
            session,
            connection=connection,
            client=HHApiClient(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except HHApiError as exc:
        connection.last_error = str(exc)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": str(exc), "status_code": exc.status_code, "payload": exc.payload},
        ) from exc

    await session.commit()
    schedule_warm_candidates_ai_outputs(getattr(result, "candidate_ids_touched", []), principal=principal, refresh=True)
    return {"ok": True, "result": serialize_import_result(result)}


@router.post("/import/negotiations")
async def import_hh_negotiations_route(
    vacancy_id: str | None = Query(default=None),
    fetch_resume_details: bool = Query(default=True),
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")

    try:
        result = await import_hh_negotiations(
            session,
            connection=connection,
            client=HHApiClient(),
            vacancy_ids={vacancy_id} if vacancy_id else None,
            fetch_resume_details=fetch_resume_details,
        )
    except HHApiError as exc:
        connection.last_error = str(exc)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": str(exc), "status_code": exc.status_code, "payload": exc.payload},
        ) from exc

    await session.commit()
    schedule_warm_candidates_ai_outputs(getattr(result, "candidate_ids_touched", []), principal=principal, refresh=True)
    return {"ok": True, "result": serialize_import_result(result)}


@router.get("/jobs")
async def get_hh_sync_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")
    jobs = await list_hh_sync_jobs(session, connection_id=connection.id, limit=limit, status=status)
    return {"ok": True, "jobs": [serialize_hh_sync_job(job) for job in jobs]}


@router.post("/jobs/import/vacancies")
async def enqueue_hh_vacancies_import_job(
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")
    job, created = await enqueue_hh_sync_job(
        session,
        connection=connection,
        job_type="import_vacancies",
        entity_type="employer",
        entity_external_id=connection.employer_id,
    )
    await session.commit()
    return {"ok": True, "created": created, "job": serialize_hh_sync_job(job)}


@router.post("/jobs/import/negotiations")
async def enqueue_hh_negotiations_import_job(
    vacancy_id: str | None = Query(default=None),
    fetch_resume_details: bool = Query(default=False),
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")
    job, created = await enqueue_hh_sync_job(
        session,
        connection=connection,
        job_type="import_negotiations",
        entity_type="vacancy" if vacancy_id else "employer",
        entity_external_id=vacancy_id or connection.employer_id,
        payload_json={"fetch_resume_details": fetch_resume_details},
    )
    await session.commit()
    return {"ok": True, "created": created, "job": serialize_hh_sync_job(job)}


@router.post("/jobs/{job_id}/retry")
async def retry_hh_job(
    job_id: int,
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")
    job = await retry_hh_sync_job(session, connection=connection, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH sync job is not found")
    await session.commit()
    return {"ok": True, "job": serialize_hh_sync_job(job)}


@router.get("/candidates/{candidate_id}/actions")
async def get_hh_candidate_actions(
    candidate_id: int,
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")

    identity, negotiation = await _get_candidate_hh_context(session, candidate_id)
    actions = [_serialize_hh_action(action) for action in _iter_hh_actions(negotiation.actions_snapshot)]
    payload = negotiation.payload_snapshot if isinstance(negotiation.payload_snapshot, dict) else {}
    return {
        "ok": True,
        "candidate_id": candidate_id,
        "negotiation_id": negotiation.external_negotiation_id,
        "vacancy_id": identity.external_vacancy_id or negotiation.external_vacancy_id,
        "employer_state": negotiation.employer_state,
        "updated_at": payload.get("updated_at"),
        "actions": actions,
    }


@router.post("/candidates/{candidate_id}/actions/{action_id}")
async def execute_hh_candidate_action(
    candidate_id: int,
    action_id: str,
    request: HHActionExecuteRequest,
    principal: Principal = AdminPrincipalDep,
    session=AsyncSessionDep,
):
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH connection is not configured")

    identity, negotiation = await _get_candidate_hh_context(session, candidate_id)
    action = _find_hh_action(negotiation.actions_snapshot, action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HH action is not available")

    action_url = str(action.get("url") or "").strip()
    method = str(action.get("method") or "").strip().upper()
    if not action_url or not method:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="HH action payload is incomplete")

    client = HHApiClient()
    try:
        provider_payload = await client.execute_negotiation_action(
            decrypt_access_token(connection),
            action_url=action_url,
            method=method,
            manager_account_id=connection.manager_account_id,
            arguments=request.arguments,
        )
        refresh_result = await import_hh_negotiations(
            session,
            connection=connection,
            client=client,
            vacancy_ids={identity.external_vacancy_id} if identity.external_vacancy_id else None,
            fetch_resume_details=False,
        )
    except HHApiError as exc:
        connection.last_error = str(exc)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": str(exc), "status_code": exc.status_code, "payload": exc.payload},
        ) from exc

    await session.commit()
    schedule_warm_candidates_ai_outputs(getattr(refresh_result, "candidate_ids_touched", []), principal=principal, refresh=True)
    return {
        "ok": True,
        "action_id": action_id,
        "resulting_employer_state": action.get("resulting_employer_state") or {},
        "provider_payload": provider_payload,
        "refresh_result": serialize_import_result(refresh_result),
    }
