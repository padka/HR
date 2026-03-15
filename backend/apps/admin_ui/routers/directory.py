from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.apps.admin_ui.security import (
    Principal,
    get_principal_identifier,
    limiter,
    require_admin,
    require_csrf_token,
    require_principal,
)
from backend.apps.admin_ui.services.cities import (
    city_experts_items,
    create_city,
    delete_city,
    get_city,
    list_cities,
    update_city_settings,
)
from backend.apps.admin_ui.services.cities_hh import get_city_hh_vacancy_statuses
from backend.apps.admin_ui.services.city_reminder_policy import (
    delete_city_reminder_policy,
    get_city_reminder_policy,
    upsert_city_reminder_policy,
)
from backend.apps.admin_ui.services.recruiters import (
    api_get_recruiter,
    api_recruiters_payload,
    create_recruiter,
    delete_recruiter,
    reset_recruiter_password,
    update_recruiter,
)
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.errors import CityAlreadyExistsError

router = APIRouter(tags=["directory"])
ADMIN_MUTATION_LIMIT = "10/minute"


@router.get("/recruiters")
async def api_recruiters(principal: Principal = Depends(require_principal)):
    if principal.type == "recruiter":
        payload = await api_get_recruiter(principal.id)
        return JSONResponse([payload] if payload else [])
    return JSONResponse(await api_recruiters_payload())


@router.get("/recruiters/{recruiter_id}")
async def api_recruiter_detail(
    recruiter_id: int,
    _: Principal = Depends(require_admin),
):
    payload = await api_get_recruiter(recruiter_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Recruiter not found")
    return JSONResponse(payload)


@router.post("/recruiters", status_code=201)
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_create_recruiter(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    payload = {
        "name": sanitize_plain_text(str(data.get("name") or "")),
        "tz": data.get("tz") or "Europe/Moscow",
        "telemost_url": data.get("telemost") or data.get("telemost_url") or "",
        "tg_chat_id": data.get("tg_chat_id"),
        "active": bool(data.get("active", True)),
    }
    city_ids = data.get("city_ids") or []
    if not isinstance(city_ids, list):
        city_ids = []

    result = await create_recruiter(payload, cities=[str(cid) for cid in city_ids])
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)

    result["city_ids"] = [int(cid) for cid in city_ids]
    recruiter_id = result.get("recruiter_id")
    result["id"] = recruiter_id
    result["name"] = payload["name"]
    result["tz"] = payload["tz"]
    result["tg_chat_id"] = payload["tg_chat_id"]
    result["active"] = payload["active"]
    headers = {}
    if recruiter_id:
        headers["Location"] = f"/api/recruiters/{recruiter_id}"
    return JSONResponse(result, status_code=201, headers=headers)


@router.put("/recruiters/{recruiter_id}")
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_update_recruiter(
    recruiter_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    payload = {
        "name": sanitize_plain_text(str(data.get("name") or "")),
        "tz": data.get("tz") or "Europe/Moscow",
        "telemost_url": data.get("telemost") or data.get("telemost_url") or "",
        "tg_chat_id": data.get("tg_chat_id"),
        "active": bool(data.get("active", True)),
    }
    city_ids = data.get("city_ids") or []
    if not isinstance(city_ids, list):
        city_ids = []

    result = await update_recruiter(recruiter_id, payload, cities=[str(cid) for cid in city_ids])
    if not result.get("ok"):
        status_code = 404 if result.get("error", {}).get("type") == "not_found" else 400
        return JSONResponse(result, status_code=status_code)

    result["city_ids"] = [int(cid) for cid in city_ids]
    result["id"] = recruiter_id
    result["name"] = payload["name"]
    result["tz"] = payload["tz"]
    result["tg_chat_id"] = payload["tg_chat_id"]
    result["active"] = payload["active"]
    return JSONResponse(result, status_code=200)


@router.post("/recruiters/{recruiter_id}/reset-password")
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_reset_recruiter_password(
    recruiter_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    result = await reset_recruiter_password(recruiter_id)
    if not result.get("ok"):
        status_code = 404 if result.get("error", {}).get("type") == "not_found" else 400
        return JSONResponse(result, status_code=status_code)
    return JSONResponse(result, status_code=200)


@router.delete("/recruiters/{recruiter_id}")
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_delete_recruiter(
    recruiter_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    payload = await api_get_recruiter(recruiter_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Recruiter not found")
    await delete_recruiter(recruiter_id)
    return JSONResponse({"ok": True})


@router.get("/cities")
async def api_cities(principal: Principal = Depends(require_principal)):
    cities = await list_cities(principal=principal)
    payload = []
    for city in cities:
        primary = city.recruiters[0] if getattr(city, "recruiters", None) else None
        payload.append(
            {
                "id": city.id,
                "name": getattr(city, "name_plain", city.name),
                "tz": getattr(city, "tz", None),
                "active": getattr(city, "active", True),
                "owner_recruiter_id": primary.id if primary else None,
                "criteria": getattr(city, "criteria", None),
                "experts": getattr(city, "experts", None),
                "experts_items": city_experts_items(city, include_inactive=False),
                "plan_week": getattr(city, "plan_week", None),
                "plan_month": getattr(city, "plan_month", None),
                "intro_address": getattr(city, "intro_address", None),
                "contact_name": getattr(city, "contact_name", None),
                "contact_phone": getattr(city, "contact_phone", None),
                "recruiter_ids": [rec.id for rec in getattr(city, "recruiters", [])],
                "recruiters": [
                    {"id": rec.id, "name": getattr(rec, "name", None) or f"Рекрутер {rec.id}"}
                    for rec in getattr(city, "recruiters", [])
                ],
            }
        )
    return JSONResponse(payload)


@router.get("/cities/{city_id}")
async def api_city_detail(
    city_id: int,
    _: Principal = Depends(require_admin),
):
    city = await get_city(city_id)
    if city is None:
        raise HTTPException(status_code=404, detail="City not found")
    primary = city.recruiters[0] if getattr(city, "recruiters", None) else None
    payload = {
        "id": city.id,
        "name": getattr(city, "name_plain", city.name),
        "tz": getattr(city, "tz", None),
        "active": getattr(city, "active", True),
        "owner_recruiter_id": primary.id if primary else None,
        "criteria": getattr(city, "criteria", None),
        "experts": getattr(city, "experts", None),
        "experts_items": city_experts_items(city, include_inactive=True),
        "plan_week": getattr(city, "plan_week", None),
        "plan_month": getattr(city, "plan_month", None),
        "intro_address": getattr(city, "intro_address", None),
        "contact_name": getattr(city, "contact_name", None),
        "contact_phone": getattr(city, "contact_phone", None),
        "recruiter_ids": [rec.id for rec in getattr(city, "recruiters", [])],
    }
    return JSONResponse(payload)


@router.get("/cities/{city_id}/hh-vacancies")
async def api_city_hh_vacancies(
    city_id: int,
    principal: Principal = Depends(require_admin),
):
    payload = await get_city_hh_vacancy_statuses(city_id, principal=principal)
    if payload is None:
        raise HTTPException(status_code=404, detail="City not found")
    return JSONResponse(payload)


@router.post("/cities", status_code=201)
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_create_city(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    try:
        recruiter_ids_raw = data.get("recruiter_ids")
        recruiter_ids: list[int] | None = None
        if recruiter_ids_raw is not None:
            recruiter_ids = []
            if isinstance(recruiter_ids_raw, list):
                for raw in recruiter_ids_raw:
                    try:
                        recruiter_ids.append(int(raw))
                    except (TypeError, ValueError):
                        continue

        city = await create_city(
            name=str(data.get("name") or ""),
            tz=str(data.get("tz") or "Europe/Moscow"),
            recruiter_ids=recruiter_ids,
        )
        if city is not None:
            error, _, _ = await update_city_settings(
                city.id,
                name=data.get("name"),
                recruiter_ids=recruiter_ids,
                responsible_id=None,
                criteria=data.get("criteria"),
                experts=data.get("experts"),
                experts_items=data.get("experts_items"),
                plan_week=data.get("plan_week"),
                plan_month=data.get("plan_month"),
                tz=data.get("tz"),
                active=data.get("active"),
                intro_address=data.get("intro_address"),
                contact_name=data.get("contact_name"),
                contact_phone=data.get("contact_phone"),
            )
            if error:
                return JSONResponse({"ok": False, "error": error}, status_code=400)
    except CityAlreadyExistsError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True}, status_code=201)


@router.put("/cities/{city_id}")
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_update_city(
    city_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    recruiter_ids = data.get("recruiter_ids")
    if recruiter_ids is not None and not isinstance(recruiter_ids, list):
        recruiter_ids = []
    error, city, recruiter = await update_city_settings(
        city_id,
        name=data.get("name"),
        recruiter_ids=recruiter_ids,
        responsible_id=None,
        criteria=data.get("criteria"),
        experts=data.get("experts"),
        experts_items=data.get("experts_items"),
        plan_week=data.get("plan_week"),
        plan_month=data.get("plan_month"),
        tz=data.get("tz"),
        active=data.get("active"),
        intro_address=data.get("intro_address"),
        contact_name=data.get("contact_name"),
        contact_phone=data.get("contact_phone"),
    )
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse(
        {
            "ok": True,
            "id": city.id if city else None,
            "owner_recruiter_id": recruiter.id if recruiter else None,
        }
    )


@router.delete("/cities/{city_id}")
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_delete_city(
    city_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    ok = await delete_city(city_id)
    if not ok:
        raise HTTPException(status_code=404, detail="City not found")
    return JSONResponse({"ok": True})


@router.get("/cities/{city_id}/reminder-policy")
async def api_get_city_reminder_policy(
    request: Request, city_id: int
) -> JSONResponse:
    _ = await require_principal(request)

    policy = await get_city_reminder_policy(city_id)
    return JSONResponse({
        "ok": True,
        "policy": {
            "city_id": city_id,
            "is_custom": policy.is_custom,
            "confirm_6h_enabled": policy.confirm_6h_enabled,
            "confirm_3h_enabled": policy.confirm_3h_enabled,
            "confirm_2h_enabled": policy.confirm_2h_enabled,
            "intro_remind_3h_enabled": policy.intro_remind_3h_enabled,
            "quiet_hours_start": policy.quiet_hours_start,
            "quiet_hours_end": policy.quiet_hours_end,
        },
    })


@router.put("/cities/{city_id}/reminder-policy")
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_upsert_city_reminder_policy(
    request: Request, city_id: int
) -> JSONResponse:
    _ = await require_csrf_token(request)
    data = await request.json()

    def _bool(key: str, default: bool) -> bool:
        v = data.get(key)
        if v is None:
            return default
        return bool(v)

    def _int(key: str, default: int) -> int:
        v = data.get(key)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    policy = await upsert_city_reminder_policy(
        city_id,
        confirm_6h_enabled=_bool("confirm_6h_enabled", True),
        confirm_3h_enabled=_bool("confirm_3h_enabled", True),
        confirm_2h_enabled=_bool("confirm_2h_enabled", True),
        intro_remind_3h_enabled=_bool("intro_remind_3h_enabled", True),
        quiet_hours_start=_int("quiet_hours_start", 22),
        quiet_hours_end=_int("quiet_hours_end", 8),
    )
    return JSONResponse({
        "ok": True,
        "policy": {
            "city_id": policy.city_id,
            "is_custom": policy.is_custom,
            "confirm_6h_enabled": policy.confirm_6h_enabled,
            "confirm_3h_enabled": policy.confirm_3h_enabled,
            "confirm_2h_enabled": policy.confirm_2h_enabled,
            "intro_remind_3h_enabled": policy.intro_remind_3h_enabled,
            "quiet_hours_start": policy.quiet_hours_start,
            "quiet_hours_end": policy.quiet_hours_end,
        },
    })


@router.delete("/cities/{city_id}/reminder-policy")
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=get_principal_identifier)
async def api_delete_city_reminder_policy(
    request: Request, city_id: int
) -> JSONResponse:
    _ = await require_csrf_token(request)

    deleted = await delete_city_reminder_policy(city_id)
    return JSONResponse({"ok": True, "was_custom": deleted})
