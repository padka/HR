from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
import html
import os
import secrets

from sqlalchemy import case, func, select, delete, insert
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.utils import format_optional_local
from backend.core.audit import log_audit_action
from backend.core.passwords import hash_password
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus, recruiter_city_association
from backend.domain.auth_account import AuthAccount
from backend.core.sanitizers import sanitize_plain_text
from markupsafe import Markup

__all__ = [
    "list_recruiters",
    "create_recruiter",
    "get_recruiter_detail",
    "update_recruiter",
    "delete_recruiter",
    "reset_recruiter_password",
    "build_recruiter_payload",
    "api_recruiters_payload",
    "api_get_recruiter",
    "RecruiterValidationError",
]


async def list_recruiters(order_by_name: bool = True) -> List[Dict[str, object]]:
    async with async_session() as session:
        query = select(Recruiter).options(selectinload(Recruiter.cities))
        if order_by_name:
            query = query.order_by(Recruiter.name.asc())
        recs = list((await session.scalars(query)).all())

        stats_map: Dict[int, Dict[str, object]] = {}

        if recs:
            rec_ids = [r.id for r in recs]
            status_lower = func.lower(Slot.status)
            stats_rows = (
                await session.execute(
                    select(
                        Slot.recruiter_id,
                        func.count().label("total"),
                        func.sum(case((status_lower == SlotStatus.FREE, 1), else_=0)).label("free"),
                        func.sum(case((status_lower == SlotStatus.PENDING, 1), else_=0)).label("pending"),
                        func.sum(
                            case(
                                (
                                    status_lower.in_(
                                        [SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE]
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("booked"),
                        func.min(case((status_lower == SlotStatus.FREE, Slot.start_utc), else_=None)).label(
                            "next_free"
                        ),
                    )
                    .where(Slot.recruiter_id.in_(rec_ids))
                    .group_by(Slot.recruiter_id)
                )
            ).all()

            stats_map = {
                row.recruiter_id: {
                    "total": int(row.total or 0),
                    "free": int(row.free or 0),
                    "pending": int(row.pending or 0),
                    "booked": int(row.booked or 0),
                    "next_free": row.next_free,
                }
                for row in stats_rows
            }

    now = datetime.now(timezone.utc)
    out = []
    for rec in recs:
        stats = stats_map.get(
            rec.id,
            {"total": 0, "free": 0, "pending": 0, "booked": 0, "next_free": None},
        )
        next_dt = stats.get("next_free")
        if isinstance(next_dt, datetime) and next_dt.tzinfo is None:
            next_dt = next_dt.replace(tzinfo=timezone.utc)
        if isinstance(next_dt, datetime):
            stats["next_free"] = next_dt
            next_local = format_optional_local(next_dt, getattr(rec, "tz", None))
            next_future = next_dt > now
        else:
            next_local = None
            next_future = False

        sorted_cities = sorted(
            rec.cities,
            key=lambda city: (getattr(city, "name_plain", "") or "").lower(),
        )
        cities_entries: List[Tuple[Markup, str]] = []
        for city in sorted_cities:
            name_markup: Markup
            if hasattr(city, "display_name"):
                name_markup = city.display_name
            else:
                name_markup = Markup(sanitize_plain_text(getattr(city, "name", "") or ""))
            cities_entries.append((name_markup, getattr(city, "tz", "")))
        out.append(
            {
                "rec": rec,
                "stats": stats,
                "next_free_local": next_local,
                "next_is_future": next_future,
                "cities": cities_entries,
                "city_ids": [city.id for city in sorted_cities],
                "cities_text": " ".join(
                    (getattr(city, "name_plain", "") or "").lower() for city in sorted_cities
                ),
                "cities_display": ", ".join(
                    sanitize_plain_text(city.name_plain)
                    for city in sorted_cities
                    if getattr(city, "name_plain", None)
                ),
            }
        )

    return out


async def create_recruiter(
    payload: Dict[str, object], *, cities: Optional[List[str]] = None
) -> Dict[str, object]:
    async with async_session() as session:
        try:
            selected_ids = _parse_city_ids(cities)
            recruiter = Recruiter(**payload)
            session.add(recruiter)

            # Flush to get recruiter.id
            await session.flush()

            # Create recruiter auth account (login = recruiter.id)
            login = str(recruiter.id)
            default_password = os.getenv("RECRUITER_DEFAULT_PASSWORD", "smart123")
            auth_created = False
            temp_password: Optional[str] = None
            existing_account = await session.scalar(
                select(AuthAccount).where(
                    AuthAccount.principal_type == "recruiter",
                    AuthAccount.principal_id == recruiter.id,
                )
            )
            if existing_account:
                if existing_account.username != login:
                    existing_account.username = login
            else:
                username_conflict = await session.scalar(
                    select(AuthAccount).where(AuthAccount.username == login)
                )
                if not username_conflict:
                    session.add(
                        AuthAccount(
                            username=login,
                            password_hash=hash_password(default_password),
                            principal_type="recruiter",
                            principal_id=recruiter.id,
                            is_active=True,
                        )
                    )
                    auth_created = True
                    temp_password = default_password

            if selected_ids:
                # Clear any existing associations (defensive)
                await session.execute(
                    delete(recruiter_city_association).where(
                        recruiter_city_association.c.recruiter_id == recruiter.id
                    )
                )
                # Directly insert into association table
                await session.execute(
                    insert(recruiter_city_association),
                    [{"recruiter_id": recruiter.id, "city_id": city_id} for city_id in selected_ids]
                )

            await session.commit()
            # Refresh with relationship loaded
            await session.refresh(recruiter, ["cities"])
        except IntegrityError as exc:  # pragma: no cover - defensive, regression covered by tests
            await session.rollback()
            return {"ok": False, "error": _integrity_error_payload(exc)}

    await log_audit_action(
        "recruiter_created",
        "recruiter",
        recruiter.id,
        changes={"city_ids": selected_ids},
    )
    return {
        "ok": True,
        "recruiter_id": recruiter.id,
        "login": login,
        "temp_password": temp_password,
        "auth_account_created": auth_created,
    }


async def reset_recruiter_password(recruiter_id: int) -> Dict[str, object]:
    """Reset recruiter password and return temporary credentials.

    The login is the recruiter numeric id (string), consistent with create_recruiter().
    """

    login = str(int(recruiter_id))
    temp_password = secrets.token_urlsafe(12)

    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if recruiter is None:
            return {"ok": False, "error": {"type": "not_found", "message": "Рекрутёр не найден."}}

        account = await session.scalar(
            select(AuthAccount).where(
                AuthAccount.principal_type == "recruiter",
                AuthAccount.principal_id == recruiter_id,
            )
        )
        if account is None:
            # Create a new auth account if missing (defensive).
            account = AuthAccount(
                username=login,
                password_hash=hash_password(temp_password),
                principal_type="recruiter",
                principal_id=recruiter_id,
                is_active=True,
            )
            session.add(account)
        else:
            # Keep username in sync with current policy (id).
            account.username = login
            account.password_hash = hash_password(temp_password)
            account.is_active = True

        await session.commit()

    await log_audit_action(
        "recruiter_password_reset",
        "recruiter",
        recruiter_id,
        changes={"login": login},
    )

    return {"ok": True, "recruiter_id": recruiter_id, "login": login, "temp_password": temp_password}


async def get_recruiter_detail(rec_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        recruiter_result = await session.execute(
            select(Recruiter)
            .options(selectinload(Recruiter.cities))
            .where(Recruiter.id == rec_id)
        )
        recruiter = recruiter_result.scalar_one_or_none()
        if not recruiter:
            return None
        cities = (await session.scalars(select(City).order_by(City.name.asc()))).all()
        selected_ids = {city.id for city in recruiter.cities}
    return {
        "recruiter": recruiter,
        "cities": cities,
        "selected_ids": selected_ids,
    }


async def update_recruiter(
    rec_id: int,
    payload: Dict[str, object],
    *,
    cities: Optional[List[str]] = None,
) -> Dict[str, object]:
    async with async_session() as session:
        recruiter_result = await session.execute(
            select(Recruiter)
            .options(selectinload(Recruiter.cities))
            .where(Recruiter.id == rec_id)
        )
        recruiter = recruiter_result.scalar_one_or_none()
        if not recruiter:
            return {
                "ok": False,
                "error": {"type": "not_found", "message": "Рекрутёр не найден."},
            }

        try:
            for key, value in payload.items():
                setattr(recruiter, key, value)

            selected_ids = _parse_city_ids(cities)

            # Clear all existing associations for this recruiter
            await session.execute(
                delete(recruiter_city_association).where(
                    recruiter_city_association.c.recruiter_id == rec_id
                )
            )

            # Insert new associations
            if selected_ids:
                await session.execute(
                    insert(recruiter_city_association),
                    [{"recruiter_id": rec_id, "city_id": city_id} for city_id in selected_ids]
                )

            await session.commit()
            # Refresh to get updated relationships
            await session.refresh(recruiter, ["cities"])
        except IntegrityError as exc:  # pragma: no cover - defensive, regression covered by tests
            await session.rollback()
            return {"ok": False, "error": _integrity_error_payload(exc)}

    await log_audit_action(
        "recruiter_updated",
        "recruiter",
        rec_id,
        changes={
            "city_ids": selected_ids,
            "active": payload.get("active") if isinstance(payload, dict) else None,
        },
    )
    return {"ok": True, "recruiter_id": rec_id}


async def delete_recruiter(rec_id: int) -> None:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, rec_id)
        if not recruiter:
            return
        await session.execute(
            delete(recruiter_city_association).where(
                recruiter_city_association.c.recruiter_id == rec_id
            )
        )
        await session.delete(recruiter)
        await session.commit()
    await log_audit_action(
        "recruiter_deleted",
        "recruiter",
        rec_id,
        changes=None,
    )


def build_recruiter_payload(
    *,
    name: str,
    tz: str,
    telemost: Optional[str],
    tg_chat_id: Optional[str],
    active: Optional[str],
) -> Dict[str, object]:
    allowed = set(sa_inspect(Recruiter).attrs.keys())
    payload: Dict[str, object] = {"name": name.strip()}

    tz_field = _pick_field(allowed, ["tz", "timezone", "tz_name", "time_zone"])
    if tz_field:
        payload[tz_field] = tz.strip() if tz else "Europe/Moscow"

    telemost_field = _pick_field(
        allowed,
        ["telemost_url", "telemost", "meet_link", "meet_url", "video_link", "video_url", "link", "room_url"],
    )
    if telemost_field:
        link_raw = (telemost or "").strip()
        if link_raw:
            if not _is_valid_url(link_raw):
                raise RecruiterValidationError("telemost", "Ссылка: укажите корректный URL")
            payload[telemost_field] = link_raw
        else:
            payload[telemost_field] = None

    chat_field = _pick_field(allowed, ["tg_chat_id", "telegram_chat_id", "chat_id"])
    if chat_field:
        raw_chat = (tg_chat_id or "").strip()
        if raw_chat:
            if not raw_chat.isdigit():
                raise RecruiterValidationError("tg_chat_id", "chat_id: только цифры")
            payload[chat_field] = int(raw_chat)
        else:
            payload[chat_field] = None

    active_field = _pick_field(allowed, ["active", "is_active", "enabled"])
    if active_field:
        payload[active_field] = True if active else False

    return payload


def _pick_field(allowed: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    for name in candidates:
        if name in allowed:
            return name
    return None


def _integrity_error_payload(exc: IntegrityError) -> Dict[str, object]:
    message = "Не удалось сохранить рекрутёра: проверьте корректность данных."
    field: Optional[str] = None
    detail = str(getattr(exc, "orig", exc)).lower()
    if "tg_chat_id" in detail or "telegram" in detail:
        message = "Рекрутёр с таким Telegram chat ID уже существует."
        field = "tg_chat_id"

    payload: Dict[str, object] = {"type": "integrity_error", "message": message}
    if field:
        payload["field"] = field
    return payload


def _parse_city_ids(raw: Optional[List[str]]) -> List[int]:
    if not raw:
        return []
    seen: set[int] = set()
    result: List[int] = []
    for value in raw:
        if not isinstance(value, str):
            continue
        trimmed = value.strip()
        if not trimmed or not trimmed.isdigit():
            continue
        city_id = int(trimmed)
        if city_id in seen:
            continue
        seen.add(city_id)
        result.append(city_id)
    return result


async def api_recruiters_payload() -> List[Dict[str, object]]:
    rows = await list_recruiters()
    payload: List[Dict[str, object]] = []
    now = datetime.now(timezone.utc)
    for item in rows:
        rec: Recruiter = item["rec"]
        stats = item.get("stats", {}) or {}
        cities = item.get("cities") or []
        last_seen = getattr(rec, "last_seen_at", None)
        if last_seen and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        is_online = False
        if last_seen:
            is_online = (now - last_seen).total_seconds() <= 300
        payload.append(
            {
                "id": rec.id,
                "name": rec.name,
                "tz": getattr(rec, "tz", None),
                "tg_chat_id": getattr(rec, "tg_chat_id", None),
                "telemost_url": getattr(rec, "telemost_url", None),
                "active": getattr(rec, "active", True),
                "last_seen_at": last_seen.isoformat() if last_seen else None,
                "is_online": bool(is_online and getattr(rec, "active", True)),
                "city_ids": item.get("city_ids", []),
                "cities": [{"name": str(name), "tz": tz} for name, tz in cities],
                "stats": {
                    "total": int(stats.get("total", 0) or 0),
                    "free": int(stats.get("free", 0) or 0),
                    "pending": int(stats.get("pending", 0) or 0),
                    "booked": int(stats.get("booked", 0) or 0),
                },
                "next_free_local": item.get("next_free_local"),
                "next_is_future": item.get("next_is_future"),
            }
        )
    return payload


async def api_get_recruiter(recruiter_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        recruiter = await session.scalar(
            select(Recruiter)
            .options(selectinload(Recruiter.cities))
            .where(Recruiter.id == recruiter_id)
        )
    if recruiter is None:
        return None
    return {
        "id": recruiter.id,
        "name": recruiter.name,
        "tz": getattr(recruiter, "tz", None),
        "tg_chat_id": getattr(recruiter, "tg_chat_id", None),
        "telemost_url": getattr(recruiter, "telemost_url", None),
        "active": getattr(recruiter, "active", True),
        "city_ids": sorted(city.id for city in recruiter.cities),
    }


class RecruiterValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def _is_valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    return True
