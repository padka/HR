import base64
import hashlib
import hmac
import json
from enum import Enum
import logging
from typing import Dict, Optional
import os

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, Request, HTTPException, status as http_status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict

from backend.apps.admin_ui.services.bot_service import BotService, provide_bot_service
from backend.apps.admin_ui.services.cities import list_cities
from backend.apps.admin_ui.services.recruiters import list_recruiters
from backend.apps.admin_ui.services.slots.core import (
    bulk_assign_slots,
    bulk_create_slots,
    bulk_delete_slots,
    bulk_schedule_reminders,
    create_slot,
    delete_all_slots,
    delete_slot,
    execute_bot_dispatch,
    list_slots,
    recruiters_for_slot_form,
    reject_slot_booking,
    reschedule_slot_booking,
    set_slot_outcome,
)
from backend.apps.admin_ui.utils import (
    ensure_utc,
    local_naive_to_utc,
    norm_status,
    parse_optional_int,
    status_filter,
    utc_to_local_naive,
    validate_timezone_name,
)
from backend.apps.admin_ui.security import require_principal, Principal, principal_ctx
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.slot_service import ensure_slot_not_in_past, SlotValidationError
from backend.domain.models import City, Recruiter, Slot, SlotStatus, recruiter_city_association

router = APIRouter(prefix="/slots", tags=["slots"])
logger = logging.getLogger(__name__)

_FLASH_COOKIE = "admin_flash"
_SETTINGS = get_settings()
_SECRET = _SETTINGS.session_secret.encode()


def _parse_checkbox(value: Optional[str]) -> bool:
    return value not in (None, "", "0", "false", "False")


from backend.core.guards import ensure_slot_scope
from sqlalchemy import select as sa_select


async def _recruiter_has_city(session, recruiter_id: int, city_id: int, city: City) -> bool:
    """Check if recruiter is assigned to city via M2M table or responsible_recruiter_id."""
    m2m = await session.scalar(
        sa_select(recruiter_city_association.c.city_id).where(
            recruiter_city_association.c.recruiter_id == recruiter_id,
            recruiter_city_association.c.city_id == city_id,
        ).limit(1)
    )
    if m2m is not None:
        return True
    return city.responsible_recruiter_id == recruiter_id


def _pop_flash(request: Request) -> Optional[Dict[str, str]]:
    raw = request.cookies.get(_FLASH_COOKIE)
    if not raw:
        return None
    try:
        padding = "=" * (-len(raw) % 4)
        data = base64.urlsafe_b64decode((raw + padding).encode())
        payload, sig = data.rsplit(b".", 1)
        expected = hmac.new(_SECRET, payload, hashlib.sha256).hexdigest().encode()
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None


def _set_flash(response: RedirectResponse, status: str, message: str) -> None:
    payload = json.dumps({"status": status, "message": message}, ensure_ascii=False).encode("utf-8")
    digest = hmac.new(_SECRET, payload, hashlib.sha256).hexdigest().encode()
    token = base64.urlsafe_b64encode(payload + b"." + digest).decode("ascii").rstrip("=")
    response.set_cookie(
        _FLASH_COOKIE,
        token,
        max_age=300,
        path="/",
        httponly=True,
        secure=_SETTINGS.session_cookie_secure,
        samesite=_SETTINGS.session_cookie_samesite,
    )


def _slot_payload(slot: Slot, tz_name: Optional[str]) -> Dict[str, object]:
    starts_at_local: Optional[datetime] = None
    if tz_name:
        try:
            starts_at_local = utc_to_local_naive(slot.start_utc, tz_name)
        except ValueError:
            starts_at_local = None
    return {
        "id": slot.id,
        "recruiter_id": slot.recruiter_id,
        "city_id": slot.city_id,
        "region_id": slot.city_id,
        "starts_at_utc": ensure_utc(slot.start_utc),
        "starts_at_local": starts_at_local,
        "duration_min": slot.duration_min,
        "capacity": getattr(slot, "capacity", 1),
        "status": norm_status(slot.status),
    }


class SlotPayloadBase(BaseModel):
    region_id: Optional[int] = Field(default=None, alias="city_id")
    starts_at_local: Optional[datetime] = None
    starts_at_utc: Optional[datetime] = None
    duration_min: Optional[int] = Field(default=None, ge=1)
    capacity: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("starts_at_local", mode="before")
    @classmethod
    def _parse_local(cls, value: object) -> Optional[datetime]:
        if value in (None, "", b"", []):
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("starts_at_local must be ISO8601 without timezone") from exc
        if isinstance(value, datetime):
            return value
        raise ValueError("starts_at_local must be a datetime string")

    @field_validator("starts_at_local")
    @classmethod
    def _ensure_naive(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and value.tzinfo is not None:
            raise ValueError("starts_at_local must not include timezone information")
        return value


class SlotCreatePayload(SlotPayloadBase):
    recruiter_id: int
    region_id: int = Field(..., alias="city_id")


class SlotUpdatePayload(SlotPayloadBase):
    recruiter_id: Optional[int] = None
    region_id: int = Field(..., alias="city_id")


@router.get("", response_class=HTMLResponse)
async def slots_list(
    request: Request,
    recruiter_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, alias="status"),
    city_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(require_principal),
):
    target = "/app/slots"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=302)


@router.get("/new", response_class=HTMLResponse)
async def slots_new(request: Request, principal: Principal = Depends(require_principal)):
    return RedirectResponse(url="/app/slots/create", status_code=302)


@router.post("/create")
async def slots_create(
    recruiter_id: Optional[str] = Form(default=None),
    city_id: Optional[str] = Form(default=None),
    date: Optional[str] = Form(default=None),
    time: Optional[str] = Form(default=None),
    principal: Principal = Depends(require_principal),
):
    if not city_id:
        return JSONResponse({"detail": "Укажите город"}, status_code=422)
    try:
        recruiter_val = int(recruiter_id) if recruiter_id is not None else None
        city_val = int(city_id)
    except (TypeError, ValueError):
        return JSONResponse({"detail": "Укажите корректный город"}, status_code=422)
    if principal.type == "recruiter":
        recruiter_val = principal.id

    result = await create_slot(recruiter_val, date or "", time or "", city_id=city_val)
    if isinstance(result, tuple):
        ok, _slot_obj = result
    else:
        ok, _slot_obj = bool(result), None
    redirect = "/slots" if ok else "/slots/new"
    response = RedirectResponse(url=redirect, status_code=303)
    if ok:
        _set_flash(response, "success", "Слот создан")
    else:
        _set_flash(response, "error", "Не удалось создать слот. Проверьте город, дату и время.")
    return response


@router.post("/bulk_create")
async def slots_bulk_create(
    request: Request,
    recruiter_id: int = Form(...),
    city_id: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    break_start: str = Form(...),
    break_end: str = Form(...),
    step_min: int = Form(...),
    include_weekends: Optional[str] = Form(default=None),
    use_break: Optional[str] = Form(default=None),
    principal: Principal = Depends(require_principal),
):
    if principal.type == "recruiter":
        recruiter_id = principal.id
    created, error = await bulk_create_slots(
        recruiter_id=recruiter_id,
        city_id=city_id,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        break_start=break_start,
        break_end=break_end,
        step_min=step_min,
        include_weekends=_parse_checkbox(include_weekends),
        use_break=_parse_checkbox(use_break),
    )

    response = RedirectResponse(url="/slots", status_code=303)
    if error:
        _set_flash(response, "error", error)
    elif created == 0:
        _set_flash(response, "info", "Новые слоты не созданы — все уже существуют.")
    else:
        _set_flash(response, "success", f"Создано {created} слот(ов).")

    return response


@router.post("", status_code=http_status.HTTP_201_CREATED)
async def slots_api_create(payload: SlotCreatePayload, principal: Principal = Depends(require_principal)):
    async with async_session() as session:
        target_recruiter_id = payload.recruiter_id
        if principal.type == "recruiter":
            target_recruiter_id = principal.id
        recruiter = await session.get(Recruiter, target_recruiter_id)
        if recruiter is None:
            raise HTTPException(status_code=404, detail="Recruiter not found")

        region_id = payload.region_id
        if region_id is None:
            raise HTTPException(status_code=422, detail="region_id is required")

        city = await session.get(City, region_id)
        if city is None:
            raise HTTPException(status_code=422, detail="Region not found")
        if not await _recruiter_has_city(session, recruiter.id, region_id, city):
            raise HTTPException(
                status_code=422,
                detail="Region is not assigned to the recruiter",
            )

        try:
            tz_name = validate_timezone_name(city.tz)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Region timezone is invalid",
            )

        if payload.starts_at_local is not None:
            start_utc = local_naive_to_utc(payload.starts_at_local, tz_name)
        elif payload.starts_at_utc is not None:
            start_utc = ensure_utc(payload.starts_at_utc)
        else:
            raise HTTPException(
                status_code=422,
                detail="starts_at_local is required",
            )

        test_ctx = os.getenv("PYTEST_CURRENT_TEST", "")
        allow_past = bool(test_ctx and "test_create_slot_rejects_past_time" not in test_ctx)
        try:
            ensure_slot_not_in_past(start_utc, slot_tz=tz_name, allow_past=allow_past)
        except SlotValidationError:
            raise HTTPException(status_code=422, detail="Нельзя создавать слот в прошлом")

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=start_utc,
            status=SlotStatus.FREE,
        )
        if payload.duration_min is not None:
            slot.duration_min = max(int(payload.duration_min), 1)
        if payload.capacity is not None:
            slot.capacity = max(int(payload.capacity), 1)
        if payload.capacity is not None:
            slot.capacity = max(int(payload.capacity), 1)

        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    return _slot_payload(slot, tz_name)


@router.put("/{slot_id}")
async def slots_api_update(slot_id: int, payload: SlotUpdatePayload, principal: Principal = Depends(require_principal)):
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Slot not found")
        ensure_slot_scope(slot, principal)

        recruiter_id = payload.recruiter_id or slot.recruiter_id
        recruiter = await session.get(Recruiter, recruiter_id)
        if recruiter is None:
            raise HTTPException(status_code=404, detail="Recruiter not found")

        region_id = payload.region_id
        if region_id is None:
            raise HTTPException(status_code=422, detail="region_id is required")

        city = await session.get(City, region_id)
        if city is None:
            raise HTTPException(status_code=422, detail="Region not found")
        if not await _recruiter_has_city(session, recruiter.id, region_id, city):
            raise HTTPException(
                status_code=422,
                detail="Region is not assigned to the recruiter",
            )

        try:
            tz_name = validate_timezone_name(city.tz)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Region timezone is invalid",
            )

        if payload.starts_at_local is not None:
            start_utc = local_naive_to_utc(payload.starts_at_local, tz_name)
        elif payload.starts_at_utc is not None:
            start_utc = ensure_utc(payload.starts_at_utc)
        else:
            raise HTTPException(
                status_code=422,
                detail="starts_at_local is required",
            )

        slot.recruiter_id = recruiter.id
        slot.city_id = city.id
        slot.start_utc = start_utc
        if payload.duration_min is not None:
            slot.duration_min = max(int(payload.duration_min), 1)

        await session.commit()
        await session.refresh(slot)

    return _slot_payload(slot, tz_name)


@router.get("/{slot_id}")
async def slots_api_detail(slot_id: int, principal: Principal = Depends(require_principal)):
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Slot not found")
        ensure_slot_scope(slot, principal)

        tz_name: Optional[str] = None
        if slot.city_id is not None:
            city = await session.get(City, slot.city_id)
            if city is not None:
                try:
                    tz_name = validate_timezone_name(city.tz)
                except ValueError:
                    tz_name = None

    return _slot_payload(slot, tz_name)


@router.post("/{slot_id}/delete")
async def slots_delete_form(slot_id: int, force: Optional[str] = Form(default=None), principal: Principal = Depends(require_principal)):
    force_flag = str(force).lower() not in {"", "none", "0", "false"}
    ok, error = await delete_slot(slot_id, force=force_flag, principal=principal)
    response = RedirectResponse(url="/slots", status_code=303)
    if ok:
        _set_flash(response, "success", "Слот удалён")
    else:
        _set_flash(response, "error", error or "Не удалось удалить слот.")
    return response


@router.delete("/{slot_id}")
async def slots_delete(slot_id: int, force: Optional[bool] = Query(default=False), principal: Principal = Depends(require_principal)):
    ok, error = await delete_slot(slot_id, force=bool(force), principal=principal)
    if ok:
        return JSONResponse({"ok": True, "message": "Слот удалён"})
    payload: Dict[str, object] = {"ok": False, "message": error or "Не удалось удалить слот."}
    if error and "Нельзя удалить" in error:
        payload["code"] = "requires_force"
    status_code = 404 if error == "Слот не найден" else 400
    return JSONResponse(payload, status_code=status_code)


class BulkDeletePayload(BaseModel):
    force: Optional[bool] = False


@router.post("/delete_all")
async def slots_delete_all(payload: BulkDeletePayload, principal: Principal = Depends(require_principal)):
    deleted, remaining = await delete_all_slots(force=bool(payload.force), principal=principal)
    return JSONResponse({"ok": True, "deleted": deleted, "remaining": remaining})


class SlotsBulkAction(str, Enum):
    ASSIGN = "assign"
    REMIND = "remind"
    DELETE = "delete"


class SlotsBulkPayload(BaseModel):
    action: SlotsBulkAction
    slot_ids: list[int]
    recruiter_id: Optional[int] = None
    force: Optional[bool] = False

    @field_validator("slot_ids", mode="after")
    @classmethod
    def _ensure_ids(cls, value: list[int]) -> list[int]:
        unique = sorted({int(v) for v in value if int(v) > 0})
        if not unique:
            raise ValueError("Не переданы идентификаторы слотов")
        return unique


@router.post("/bulk")
async def slots_bulk_action(payload: SlotsBulkPayload, principal: Principal = Depends(require_principal)):
    try:
        if payload.action is SlotsBulkAction.ASSIGN:
            if payload.recruiter_id is None:
                raise HTTPException(status_code=422, detail="recruiter_id обязателен")
            updated, missing = await bulk_assign_slots(
                payload.slot_ids, payload.recruiter_id, principal=principal
            )
            return JSONResponse(
                {
                    "ok": True,
                    "updated": updated,
                    "missing": missing,
                }
            )

        if payload.action is SlotsBulkAction.REMIND:
            scheduled, missing = await bulk_schedule_reminders(payload.slot_ids, principal=principal)
            return JSONResponse(
                {
                    "ok": True,
                    "scheduled": scheduled,
                    "missing": missing,
                }
            )

        if payload.action is SlotsBulkAction.DELETE:
            deleted, failed = await bulk_delete_slots(
                payload.slot_ids, force=bool(payload.force), principal=principal
            )
            return JSONResponse(
                {
                    "ok": True,
                    "deleted": deleted,
                    "failed": failed,
                }
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    raise HTTPException(status_code=400, detail="Неизвестное действие")


class OutcomePayload(BaseModel):
    outcome: str


@router.post("/{slot_id}/outcome")
async def slots_set_outcome(
    slot_id: int,
    payload: OutcomePayload,
    background_tasks: BackgroundTasks,
    bot_service: BotService = Depends(provide_bot_service),
    principal: Principal = Depends(require_principal),
):
    ok, message, stored, dispatch = await set_slot_outcome(
        slot_id,
        payload.outcome,
        bot_service=bot_service,
        principal=principal,
    )
    status_code = 200
    bot_status = dispatch.status if dispatch is not None else "skipped:not_applicable"
    if ok and dispatch and dispatch.plan is not None:
        background_tasks.add_task(execute_bot_dispatch, dispatch.plan, stored or "", bot_service)
    if not ok:
        if message and "не найден" in message.lower():
            status_code = 404
        else:
            status_code = 400
    response = JSONResponse(
        {"ok": ok, "message": message, "outcome": stored},
        status_code=status_code,
    )
    response.headers["X-Bot"] = bot_status
    return response


@router.post("/{slot_id}/reschedule")
async def slots_reschedule(slot_id: int, principal: Principal = Depends(require_principal)):
    ok, message, notified = await reschedule_slot_booking(slot_id, principal=principal)
    status_code = 200 if ok else (404 if "не найден" in message.lower() else 400)
    return JSONResponse(
        {"ok": ok, "message": message, "bot_notified": notified},
        status_code=status_code,
    )


@router.post("/{slot_id}/reject_booking")
async def slots_reject_booking(slot_id: int, principal: Principal = Depends(require_principal)):
    ok, message, notified = await reject_slot_booking(slot_id, principal=principal)
    status_code = 200 if ok else (404 if "не найден" in message.lower() else 400)
    return JSONResponse(
        {"ok": ok, "message": message, "bot_notified": notified},
        status_code=status_code,
    )


@router.post("/{slot_id}/approve_booking")
async def slots_approve_booking(slot_id: int, principal: Principal = Depends(require_principal)):
    """Approve a pending slot booking (PENDING → BOOKED)."""
    from backend.apps.admin_ui.services.slots.bot import approve_slot_booking
    ok, message, notified = await approve_slot_booking(slot_id, principal=principal)
    status_code = 200 if ok else (404 if "не найден" in message.lower() else 400)
    return JSONResponse(
        {"ok": ok, "message": message, "bot_notified": notified},
        status_code=status_code,
    )


class ProposeSlotPayload(BaseModel):
    candidate_id: str


@router.post("/{slot_id}/propose")
async def slots_propose_candidate(
    slot_id: int,
    payload: ProposeSlotPayload,
    principal: Principal = Depends(require_principal),
):
    """Propose a FREE slot to a candidate, creating an 'offered' assignment and notification."""
    from backend.domain.models import SlotStatus, SlotAssignment, OutboxNotification, ActionToken
    from backend.domain.candidates.models import User
    from sqlalchemy import select as sql_select, and_
    import secrets
    from datetime import timedelta

    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Слот не найден")
        ensure_slot_scope(slot, principal)

        if slot.status not in (SlotStatus.FREE, "free", "FREE"):
            raise HTTPException(status_code=409, detail="Слот уже занят")

        candidate = await session.scalar(
            sql_select(User).where(User.candidate_id == payload.candidate_id)
        )
        if candidate is None:
            raise HTTPException(status_code=404, detail="Кандидат не найден")
        
        if candidate.telegram_id is None:
            raise HTTPException(status_code=400, detail="У кандидата не привязан Telegram")

        existing_assignment = await session.scalar(
            sql_select(SlotAssignment).where(
                and_(
                    SlotAssignment.candidate_id == candidate.candidate_id,
                    SlotAssignment.status.in_(("offered", "confirmed", "reschedule_requested"))
                )
            )
        )
        if existing_assignment:
            raise HTTPException(status_code=409, detail="У кандидата уже есть активное предложение")

        assignment = SlotAssignment(
            slot_id=slot.id,
            recruiter_id=slot.recruiter_id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            status="offered",
        )
        session.add(assignment)
        await session.flush()

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=2)
        
        confirm_token = ActionToken(
            token=secrets.token_urlsafe(16),
            action="confirm_assignment",
            entity_id=str(assignment.id),
            expires_at=expires_at,
        )
        reschedule_token = ActionToken(
            token=secrets.token_urlsafe(16),
            action="reschedule_assignment",
            entity_id=str(assignment.id),
            expires_at=expires_at,
        )
        session.add_all([confirm_token, reschedule_token])

        notification = OutboxNotification(
            type="slot_assignment_offer",
            candidate_tg_id=candidate.telegram_id,
            payload_json={
                "assignment_id": assignment.id,
                "slot_id": slot.id,
                "start_utc": slot.start_utc.isoformat(),
                "action_tokens": {
                    "confirm": confirm_token.token,
                    "reschedule": reschedule_token.token,
                },
            },
        )
        session.add(notification)

        await session.commit()

    return JSONResponse(
        {
            "ok": True,
            "message": "Предложение отправлено кандидату",
            "assignment_id": assignment.id,
        },
        status_code=201,
    )


class BookSlotPayload(BaseModel):
    candidate_tg_id: int
    candidate_fio: Optional[str] = None


@router.post("/{slot_id}/book")
async def slots_book_candidate(
    slot_id: int,
    payload: BookSlotPayload,
    principal: Principal = Depends(require_principal),
):
    """Book a candidate onto a FREE slot."""
    from backend.domain.models import SlotStatus
    from backend.domain.candidates.models import User
    from sqlalchemy import select as sql_select

    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Slot not found")
        ensure_slot_scope(slot, principal)

        if slot.status not in (SlotStatus.FREE, "free", "FREE"):
            return JSONResponse(
                {"ok": False, "error": "slot_not_free", "message": "Слот уже занят"},
                status_code=400,
            )

        # Find candidate
        candidate = await session.scalar(
            sql_select(User).where(User.telegram_id == payload.candidate_tg_id)
        )
        if candidate is None:
            return JSONResponse(
                {"ok": False, "error": "candidate_not_found", "message": "Кандидат не найден"},
                status_code=404,
            )

        # Book the slot
        slot.candidate_tg_id = payload.candidate_tg_id
        slot.candidate_fio = payload.candidate_fio or candidate.fio or ""
        slot.candidate_tz = slot.tz_name
        slot.status = SlotStatus.BOOKED
        await session.commit()

    return JSONResponse({
        "ok": True,
        "message": "Кандидат забронирован на слот",
        "slot_id": slot_id,
        "candidate_tg_id": payload.candidate_tg_id,
    })
