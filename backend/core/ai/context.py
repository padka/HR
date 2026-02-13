from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text as sql_text

from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.domain.candidates.models import ChatMessage, ChatMessageDirection, ChatMessageStatus, TestResult, User
from backend.domain.models import Slot, recruiter_city_association
from backend.domain.repositories import find_city_by_plain_name


def compute_input_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _iso(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


async def _ensure_candidate_scope(user: User, principal: Principal) -> None:
    if principal.type == "admin":
        return
    if user.responsible_recruiter_id == principal.id:
        return

    # Allow recruiter access if the candidate belongs to one of their cities
    allowed = False
    if user.city:
        city_record = await find_city_by_plain_name(user.city)
        if city_record:
            async with async_session() as session:
                rows = await session.execute(
                    select(recruiter_city_association.c.city_id)
                    .where(recruiter_city_association.c.recruiter_id == principal.id)
                )
                allowed_city_ids = {row[0] for row in rows}
                if city_record.id in allowed_city_ids:
                    allowed = True

    if not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")


async def build_candidate_ai_context(candidate_id: int, *, principal: Principal) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
        await _ensure_candidate_scope(user, principal)

        # Latest tests summary (no question texts, no answers)
        tests: dict[str, Any] = {"latest": {}, "total": 0}
        rows = (
            await session.execute(
                select(TestResult)
                .where(TestResult.user_id == user.id)
                .order_by(TestResult.created_at.desc(), TestResult.id.desc())
                .limit(50)
            )
        ).scalars().all()
        tests["total"] = len(rows)
        for item in rows:
            rating = (item.rating or "").strip().upper()
            if rating in {"TEST1", "TEST2"} and rating not in tests["latest"]:
                tests["latest"][rating] = {
                    "final_score": item.final_score,
                    "raw_score": item.raw_score,
                    "total_time_sec": item.total_time,
                    "created_at": _iso(item.created_at),
                }

        # Slots summary
        slot_filters = [Slot.candidate_id == user.candidate_id]
        candidate_tg = user.telegram_user_id or user.telegram_id
        if candidate_tg is not None:
            slot_filters.append(Slot.candidate_tg_id == candidate_tg)
        slot_rows = await session.execute(
            select(
                Slot.id,
                Slot.status,
                Slot.purpose,
                Slot.start_utc,
                Slot.recruiter_id,
                Slot.city_id,
                Slot.tz_name,
                Slot.candidate_tz,
            )
            .where(or_(*slot_filters))
            .order_by(Slot.start_utc.desc(), Slot.id.desc())
            .limit(30)
        )
        slots = []
        upcoming: Optional[dict[str, Any]] = None
        upcoming_dt: Optional[datetime] = None
        for row in slot_rows:
            start_utc = row.start_utc
            if start_utc and start_utc.tzinfo is None:
                start_utc = start_utc.replace(tzinfo=timezone.utc)
            item = {
                "id": row.id,
                "status": (row.status or "").lower() or None,
                "purpose": (row.purpose or "").lower() or "interview",
                "start_utc": _iso(start_utc),
                "recruiter_id": row.recruiter_id,
                "city_id": row.city_id,
                "slot_tz": row.tz_name,
                "candidate_tz": row.candidate_tz,
            }
            slots.append(item)
            if start_utc and start_utc >= now:
                if upcoming_dt is None or start_utc < upcoming_dt:
                    upcoming_dt = start_utc
                    upcoming = item

        # Chat summary (metadata only)
        since = now - timedelta(days=7)
        counts = await session.execute(
            select(ChatMessage.direction, func.count(ChatMessage.id))
            .where(ChatMessage.candidate_id == user.id, ChatMessage.created_at >= since)
            .group_by(ChatMessage.direction)
        )
        by_dir = {row[0]: int(row[1] or 0) for row in counts}
        last_inbound = await session.scalar(
            select(ChatMessage.created_at)
            .where(
                ChatMessage.candidate_id == user.id,
                ChatMessage.direction == ChatMessageDirection.INBOUND.value,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        last_outbound = await session.scalar(
            select(ChatMessage.created_at)
            .where(
                ChatMessage.candidate_id == user.id,
                ChatMessage.direction == ChatMessageDirection.OUTBOUND.value,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        failed_outbound = await session.scalar(
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.candidate_id == user.id,
                ChatMessage.direction == ChatMessageDirection.OUTBOUND.value,
                ChatMessage.status == ChatMessageStatus.FAILED.value,
                ChatMessage.created_at >= since,
            )
        )

        # Funnel events summary (no metadata by default)
        try:
            ev_rows = await session.execute(
                sql_text(
                    """
                    SELECT event_name, created_at
                    FROM analytics_events
                    WHERE candidate_id = :cid
                    ORDER BY created_at DESC, id DESC
                    LIMIT 50
                    """
                ),
                {"cid": user.id},
            )
            events = [
                {"event": str(name), "at": _iso(dt)}
                for (name, dt) in ev_rows.fetchall()
            ]
        except Exception:
            events = []

    candidate_status = getattr(user, "candidate_status", None)
    status_slug = getattr(candidate_status, "value", None) if candidate_status is not None else None
    status_slug = status_slug or getattr(user, "candidate_status", None)

    return {
        "candidate": {
            "id": user.id,
            "is_active": bool(user.is_active),
            "status": status_slug,
            "workflow_status": getattr(user, "workflow_status", None),
            "status_changed_at": _iso(getattr(user, "status_changed_at", None)),
            "last_activity": _iso(getattr(user, "last_activity", None)),
            "source": getattr(user, "source", None),
            "city": user.city or None,
            "responsible_recruiter_id": getattr(user, "responsible_recruiter_id", None),
            "telegram_linked": bool(user.telegram_id or user.telegram_user_id),
        },
        "tests": tests,
        "slots": {
            "upcoming": upcoming,
            "items": slots,
            "total": len(slots),
        },
        "chat": {
            "window_days": 7,
            "inbound_count": int(by_dir.get(ChatMessageDirection.INBOUND.value, 0) or 0),
            "outbound_count": int(by_dir.get(ChatMessageDirection.OUTBOUND.value, 0) or 0),
            "failed_outbound_count": int(failed_outbound or 0),
            "last_inbound_at": _iso(last_inbound),
            "last_outbound_at": _iso(last_outbound),
        },
        "funnel_events": {
            "items": events,
            "total": len(events),
        },
    }


async def get_last_inbound_message_text(candidate_id: int, *, principal: Principal) -> Optional[str]:
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
        await _ensure_candidate_scope(user, principal)
        msg = await session.scalar(
            select(ChatMessage.text)
            .where(
                ChatMessage.candidate_id == user.id,
                ChatMessage.direction == ChatMessageDirection.INBOUND.value,
                ChatMessage.text.is_not(None),
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        if msg is None:
            return None
        return str(msg)
