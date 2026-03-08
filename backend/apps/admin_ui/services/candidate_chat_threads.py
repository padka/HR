from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select

from backend.apps.admin_ui.security import (
    Principal,
    normalize_admin_principal_id,
)
from backend.core.db import async_session
from backend.domain.candidates.models import (
    CandidateChatRead,
    ChatMessage,
    ChatMessageDirection,
    User,
)
from backend.domain.candidates.status import get_status_label
from backend.domain.models import recruiter_city_association
from backend.domain.repositories import find_city_by_plain_name


def _normalize_principal(principal: Principal) -> Principal:
    if principal.type == "admin":
        return Principal(type="admin", id=normalize_admin_principal_id(principal.id))
    return principal


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _recruiter_city_ids(principal: Principal) -> set[int]:
    if principal.type != "recruiter":
        return set()
    async with async_session() as session:
        rows = await session.execute(
            select(recruiter_city_association.c.city_id).where(
                recruiter_city_association.c.recruiter_id == principal.id
            )
        )
    return {int(city_id) for city_id in rows.scalars().all() if city_id is not None}


async def _is_accessible_user(
    user: User,
    principal: Principal,
    *,
    recruiter_city_ids: set[int],
    city_cache: dict[str, Optional[int]],
) -> bool:
    if principal.type == "admin":
        return True
    if user.responsible_recruiter_id == principal.id:
        return True
    if user.responsible_recruiter_id is not None or not user.city:
        return False

    city_key = user.city.strip().lower()
    if city_key not in city_cache:
        city_record = await find_city_by_plain_name(user.city)
        city_cache[city_key] = int(city_record.id) if city_record is not None else None
    city_id = city_cache.get(city_key)
    return city_id is not None and city_id in recruiter_city_ids


async def _load_thread_rows(principal: Principal) -> tuple[list[tuple[User, str | None, datetime | None, str | None]], dict[int, Optional[datetime]], dict[int, int]]:
    latest_sq = (
        select(
            ChatMessage.candidate_id.label("candidate_id"),
            ChatMessage.text.label("text"),
            ChatMessage.created_at.label("created_at"),
            ChatMessage.direction.label("direction"),
            func.row_number()
            .over(
                partition_by=ChatMessage.candidate_id,
                order_by=(ChatMessage.created_at.desc(), ChatMessage.id.desc()),
            )
            .label("rn"),
        )
    ).subquery()

    async with async_session() as session:
        rows = (
            await session.execute(
                select(
                    User,
                    latest_sq.c.text,
                    latest_sq.c.created_at,
                    latest_sq.c.direction,
                )
                .join(latest_sq, latest_sq.c.candidate_id == User.id)
                .where(latest_sq.c.rn == 1)
                .order_by(latest_sq.c.created_at.desc())
            )
        ).all()

        candidate_ids = [row[0].id for row in rows]
        if not candidate_ids:
            return [], {}, {}

        read_rows = (
            await session.execute(
                select(CandidateChatRead).where(
                    CandidateChatRead.candidate_id.in_(candidate_ids),
                    CandidateChatRead.principal_type == principal.type,
                    CandidateChatRead.principal_id == principal.id,
                )
            )
        ).scalars().all()
        read_map = {
            int(row.candidate_id): _as_utc(row.last_read_at)
            for row in read_rows
        }

        unread_rows = (
            await session.execute(
                select(
                    ChatMessage.candidate_id,
                    func.count(ChatMessage.id),
                )
                .select_from(ChatMessage)
                .outerjoin(
                    CandidateChatRead,
                    and_(
                        CandidateChatRead.candidate_id == ChatMessage.candidate_id,
                        CandidateChatRead.principal_type == principal.type,
                        CandidateChatRead.principal_id == principal.id,
                    ),
                )
                .where(
                    ChatMessage.candidate_id.in_(candidate_ids),
                    ChatMessage.direction == ChatMessageDirection.INBOUND.value,
                    or_(
                        CandidateChatRead.last_read_at.is_(None),
                        ChatMessage.created_at > CandidateChatRead.last_read_at,
                    ),
                )
                .group_by(ChatMessage.candidate_id)
            )
        ).all()
    unread_map = {int(candidate_id): int(total or 0) for candidate_id, total in unread_rows}
    return rows, read_map, unread_map


async def list_threads(
    principal: Principal,
    *,
    search: Optional[str] = None,
    unread_only: bool = False,
    limit: int = 100,
) -> dict[str, object]:
    principal = _normalize_principal(principal)
    recruiter_city_ids = await _recruiter_city_ids(principal)
    city_cache: dict[str, Optional[int]] = {}
    rows, read_map, unread_map = await _load_thread_rows(principal)

    query = (search or "").strip().lower()
    threads: list[dict[str, object]] = []
    latest_event_at: Optional[datetime] = None

    for user, last_text, last_created_at, last_direction in rows:
        if not await _is_accessible_user(
            user,
            principal,
            recruiter_city_ids=recruiter_city_ids,
            city_cache=city_cache,
        ):
            continue

        unread_count = unread_map.get(int(user.id), 0)
        if unread_only and unread_count <= 0:
            continue

        haystack = " ".join(
            value
            for value in [
                user.fio,
                user.city,
                user.telegram_username,
                str(user.telegram_id) if user.telegram_id is not None else "",
            ]
            if value
        ).lower()
        if query and query not in haystack:
            continue

        last_message_at = _as_utc(last_created_at)
        last_read_at = read_map.get(int(user.id))
        event_at = max(
            [value for value in [last_message_at, last_read_at] if value is not None],
            default=last_message_at,
        )
        if event_at and (latest_event_at is None or event_at > latest_event_at):
            latest_event_at = event_at

        threads.append(
            {
                "id": int(user.id),
                "candidate_id": int(user.id),
                "type": "candidate",
                "title": user.fio or f"Кандидат #{user.id}",
                "city": user.city or "Не указан",
                "status_label": get_status_label(user.candidate_status),
                "profile_url": f"/app/candidates/{user.id}",
                "telegram_username": user.telegram_username or user.username,
                "created_at": (event_at or datetime.now(timezone.utc)).isoformat(),
                "last_message_at": last_message_at.isoformat() if last_message_at else None,
                "last_message": {
                    "text": (last_text or "").strip() or "Сообщение",
                    "created_at": last_message_at.isoformat() if last_message_at else None,
                    "direction": last_direction,
                },
                "unread_count": unread_count,
            }
        )

    threads.sort(
        key=lambda item: (
            item.get("last_message", {}).get("created_at")
            or item.get("created_at")
            or ""
        ),
        reverse=True,
    )
    return {
        "threads": threads[: max(1, min(limit, 200))],
        "latest_event_at": latest_event_at.isoformat() if latest_event_at else None,
    }


async def wait_for_thread_updates(
    principal: Principal,
    *,
    since: Optional[datetime],
    timeout: int = 25,
    limit: int = 100,
) -> dict[str, object]:
    deadline = datetime.now(timezone.utc) + timedelta(seconds=max(timeout, 5))
    since_utc = _as_utc(since)

    while True:
        payload = await list_threads(principal, limit=limit)
        latest_event_at = payload.get("latest_event_at")
        latest_dt = _as_utc(datetime.fromisoformat(latest_event_at)) if latest_event_at else None
        if since_utc is None or (latest_dt and latest_dt > since_utc):
            payload["updated"] = True
            return payload
        if datetime.now(timezone.utc) >= deadline:
            return {
                "threads": [],
                "latest_event_at": latest_event_at,
                "updated": False,
            }
        await asyncio.sleep(1.0)


async def mark_read(candidate_id: int, principal: Principal) -> None:
    principal = _normalize_principal(principal)
    recruiter_city_ids = await _recruiter_city_ids(principal)
    city_cache: dict[str, Optional[int]] = {}

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Кандидат не найден"},
            )
        if not await _is_accessible_user(
            user,
            principal,
            recruiter_city_ids=recruiter_city_ids,
            city_cache=city_cache,
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Кандидат не найден"},
            )

        state = await session.scalar(
            select(CandidateChatRead).where(
                CandidateChatRead.candidate_id == candidate_id,
                CandidateChatRead.principal_type == principal.type,
                CandidateChatRead.principal_id == principal.id,
            )
        )
        now = datetime.now(timezone.utc)
        if state is None:
            state = CandidateChatRead(
                candidate_id=candidate_id,
                principal_type=principal.type,
                principal_id=principal.id,
                last_read_at=now,
            )
            session.add(state)
        else:
            state.last_read_at = now
        await session.commit()


__all__ = ["list_threads", "mark_read", "wait_for_thread_updates"]
