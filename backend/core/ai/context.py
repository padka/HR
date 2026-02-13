from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text as sql_text

from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.domain.candidates.models import (
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    QuestionAnswer,
    TestResult,
    User,
)
from backend.domain.models import City, Slot, recruiter_city_association
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

        candidate_fio_for_redaction = user.fio

        city_profile: Optional[dict[str, Any]] = None
        city_record: Optional[City] = None
        if user.city:
            city_record = await find_city_by_plain_name(user.city)
        if city_record is not None:
            from .redaction import redact_text

            criteria_raw = city_record.criteria or ""
            criteria_redaction = redact_text(criteria_raw, candidate_fio=candidate_fio_for_redaction, max_len=2000)
            criteria_value = None
            if criteria_raw and criteria_redaction.safe_to_send and criteria_redaction.text.strip():
                criteria_value = criteria_redaction.text

            city_profile = {
                "id": int(city_record.id),
                "name": html.unescape(city_record.name or "") or None,
                "tz": city_record.tz or None,
                "active": bool(city_record.active),
                # Used for AI vacancy fit assessment. Best-effort redaction is applied.
                "criteria": criteria_value,
                "plan_week": city_record.plan_week,
                "plan_month": city_record.plan_month,
            }

        # Latest tests summary (+ best-effort redacted answers for the latest attempt)
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
        latest_result_ids: dict[str, int] = {}
        for item in rows:
            rating = (item.rating or "").strip().upper()
            if rating in {"TEST1", "TEST2"} and rating not in tests["latest"]:
                tests["latest"][rating] = {
                    "test_result_id": int(item.id),
                    "final_score": item.final_score,
                    "raw_score": item.raw_score,
                    "total_time_sec": item.total_time,
                    "created_at": _iso(item.created_at),
                }
                latest_result_ids[rating] = int(item.id)

        # Add question-level answers for latest test results (best-effort, redacted, optional).
        if latest_result_ids:
            from .redaction import redact_text

            ans_rows = (
                await session.execute(
                    select(QuestionAnswer)
                    .where(QuestionAnswer.test_result_id.in_(set(latest_result_ids.values())))
                    .order_by(QuestionAnswer.test_result_id.asc(), QuestionAnswer.question_index.asc())
                )
            ).scalars().all()
            by_result: dict[int, list[dict[str, Any]]] = {}
            for ans in ans_rows:
                q_text = redact_text(ans.question_text or "", candidate_fio=candidate_fio_for_redaction, max_len=400)
                u_text = redact_text(ans.user_answer or "", candidate_fio=candidate_fio_for_redaction, max_len=200)
                c_text = redact_text(ans.correct_answer or "", candidate_fio=candidate_fio_for_redaction, max_len=200)

                by_result.setdefault(int(ans.test_result_id), []).append(
                    {
                        "question_index": int(ans.question_index),
                        "question_text": q_text.text if q_text.safe_to_send and q_text.text.strip() else None,
                        "user_answer": u_text.text if u_text.safe_to_send and u_text.text.strip() else None,
                        "correct_answer": c_text.text if c_text.safe_to_send and c_text.text.strip() else None,
                        "is_correct": bool(ans.is_correct),
                        "attempts_count": int(ans.attempts_count or 0),
                        "time_spent_sec": int(ans.time_spent or 0),
                        "overtime": bool(ans.overtime),
                    }
                )

            for rating, rid in latest_result_ids.items():
                if rating in tests["latest"]:
                    tests["latest"][rating]["answers"] = by_result.get(rid, [])

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
            "desired_position": getattr(user, "desired_position", None),
            "responsible_recruiter_id": getattr(user, "responsible_recruiter_id", None),
            "telegram_linked": bool(user.telegram_id or user.telegram_user_id),
        },
        "city_profile": city_profile,
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


async def build_city_candidate_recommendations_context(
    city_id: int,
    *,
    principal: Principal,
    limit: int = 30,
) -> dict[str, Any]:
    """Build anonymized context for AI candidate recommendations within a city."""

    async with async_session() as session:
        city = await session.get(City, city_id)
        if city is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")

        if principal.type != "admin":
            allowed = await session.scalar(
                select(func.count())
                .select_from(recruiter_city_association)
                .where(
                    recruiter_city_association.c.recruiter_id == principal.id,
                    recruiter_city_association.c.city_id == city_id,
                )
            )
            if not allowed:
                # Hide existence to avoid info leaks.
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")

        from .redaction import redact_text

        city_name_plain = html.unescape(city.name or "") or ""
        criteria_raw = city.criteria or ""
        criteria_redaction = redact_text(criteria_raw, max_len=2000)
        criteria_value = None
        if criteria_raw and criteria_redaction.safe_to_send and criteria_redaction.text.strip():
            criteria_value = criteria_redaction.text

        # Candidate list (no PII fields)
        users = (
            await session.execute(
                select(User)
                .where(
                    User.is_active.is_(True),
                    func.lower(User.city) == func.lower(city_name_plain),
                )
                .order_by(User.last_activity.desc(), User.id.desc())
                .limit(int(limit))
            )
        ).scalars().all()

        candidate_ids = [int(u.id) for u in users]

        latest_tests: dict[int, dict[str, Any]] = {cid: {} for cid in candidate_ids}
        if candidate_ids:
            tr_rows = await session.execute(
                select(
                    TestResult.user_id,
                    TestResult.rating,
                    TestResult.final_score,
                    TestResult.raw_score,
                    TestResult.total_time,
                    TestResult.created_at,
                    TestResult.id,
                )
                .where(TestResult.user_id.in_(candidate_ids))
                .order_by(TestResult.created_at.desc(), TestResult.id.desc())
            )
            for uid, rating, final_score, raw_score, total_time, created_at, tr_id in tr_rows.fetchall():
                key = (rating or "").strip().upper()
                if key not in {"TEST1", "TEST2"}:
                    continue
                cid = int(uid)
                if cid not in latest_tests:
                    continue
                if key in latest_tests[cid]:
                    continue
                latest_tests[cid][key] = {
                    "test_result_id": int(tr_id),
                    "final_score": float(final_score) if final_score is not None else None,
                    "raw_score": int(raw_score) if raw_score is not None else None,
                    "total_time_sec": int(total_time) if total_time is not None else None,
                    "created_at": _iso(created_at),
                }

        candidates = []
        for u in users:
            candidate_status = getattr(u, "candidate_status", None)
            status_slug = getattr(candidate_status, "value", None) if candidate_status is not None else None
            status_slug = status_slug or getattr(u, "candidate_status", None)
            candidates.append(
                {
                    "id": int(u.id),
                    "is_active": bool(u.is_active),
                    "status": status_slug,
                    "workflow_status": getattr(u, "workflow_status", None),
                    "status_changed_at": _iso(getattr(u, "status_changed_at", None)),
                    "last_activity": _iso(getattr(u, "last_activity", None)),
                    "source": getattr(u, "source", None),
                    "desired_position": getattr(u, "desired_position", None),
                    "tests": {"latest": latest_tests.get(int(u.id), {})},
                }
            )

    return {
        "city": {
            "id": int(city.id),
            "name": city_name_plain or None,
            "tz": city.tz or None,
            "criteria": criteria_value,
            "criteria_present": bool(criteria_value),
        },
        "candidates": {
            "items": candidates,
            "total": len(candidates),
            "limit": int(limit),
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
