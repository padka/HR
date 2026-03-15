from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from backend.apps.admin_ui.security import (
    Principal,
    normalize_admin_principal_id,
)
from backend.apps.admin_ui.services.chat_meta import compact_chat_preview, derive_chat_message_kind
from backend.core.ai.candidate_scorecard import fit_level_from_score
from backend.core.db import async_session
from backend.domain.ai.models import AIOutput
from backend.domain.candidates.models import (
    CandidateChatRead,
    CandidateChatWorkspace,
    ChatMessage,
    User,
)
from backend.domain.candidates.status import CandidateStatus, get_status_label, is_terminal_status
from backend.domain.models import Recruiter, recruiter_city_association
from backend.domain.repositories import find_city_by_plain_name

_REPLY_SLA_HOURS = 6
_FOLLOW_UP_HOURS = 24
_PRIORITY_BUCKETS = {
    "overdue": 0,
    "needs_reply": 1,
    "blocked": 2,
    "waiting_candidate": 3,
    "follow_up": 4,
    "system": 5,
    "terminal": 6,
}
_BLOCKED_STATUSES = {
    CandidateStatus.SLOT_PENDING,
    CandidateStatus.INTERVIEW_SCHEDULED,
    CandidateStatus.INTRO_DAY_SCHEDULED,
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
}


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


def _iso(value: Optional[datetime]) -> Optional[str]:
    value_utc = _as_utc(value)
    return value_utc.isoformat() if value_utc else None


def _hours_since(value: Optional[datetime], *, now: datetime) -> Optional[float]:
    value_utc = _as_utc(value)
    if value_utc is None:
        return None
    return max(0.0, (now - value_utc).total_seconds() / 3600.0)


def _status_slug(user: User) -> str:
    raw = getattr(user, "candidate_status", None)
    if raw is None:
        return ""
    value = getattr(raw, "value", raw)
    return str(value or "").strip().lower()


def _is_terminal(user: User) -> bool:
    status_value = getattr(user, "candidate_status", None)
    return bool(status_value and is_terminal_status(status_value))


def _default_risk_hint(
    priority_bucket: str,
    *,
    last_message_kind: str,
    is_terminal: bool,
) -> Optional[str]:
    if priority_bucket == "overdue":
        return "Кандидат ждёт ответ дольше SLA."
    if priority_bucket == "needs_reply":
        return "Последнее слово за кандидатом, нужен ответ рекрутера."
    if priority_bucket == "blocked":
        return "Нужна фиксация слота или подтверждение следующего этапа."
    if priority_bucket == "follow_up":
        return "Диалог остывает, нужен follow-up."
    if priority_bucket == "system":
        return "Последняя активность системная, диалог не требует немедленного ответа."
    if priority_bucket == "terminal" or is_terminal:
        return "Кандидат в терминальном статусе."
    if last_message_kind == "recruiter":
        return "Ждём ответ кандидата."
    return None


def _priority_payload(
    *,
    user: User,
    last_message_kind: str,
    last_message_at: Optional[datetime],
    follow_up_due_at: Optional[datetime],
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    age_hours = _hours_since(last_message_at, now=now) or 0.0
    due_at = _as_utc(follow_up_due_at)
    terminal = _is_terminal(user)

    requires_reply = last_message_kind == "candidate" and not terminal
    if requires_reply and age_hours >= _REPLY_SLA_HOURS:
        bucket = "overdue"
    elif requires_reply:
        bucket = "needs_reply"
    elif due_at and due_at <= now:
        bucket = "follow_up"
    elif getattr(user, "candidate_status", None) in _BLOCKED_STATUSES and not terminal:
        bucket = "blocked"
    elif terminal:
        bucket = "terminal"
    elif last_message_kind == "recruiter":
        bucket = "follow_up" if age_hours >= _FOLLOW_UP_HOURS else "waiting_candidate"
    elif last_message_kind in {"bot", "system"}:
        bucket = "system"
    else:
        bucket = "follow_up" if age_hours >= _FOLLOW_UP_HOURS else "waiting_candidate"

    if bucket == "overdue":
        sla_state = "overdue"
    elif bucket == "needs_reply":
        sla_state = "needs_reply"
    elif bucket == "blocked":
        sla_state = "blocked"
    elif bucket == "follow_up":
        sla_state = "follow_up"
    elif bucket == "waiting_candidate":
        sla_state = "waiting_candidate"
    elif bucket == "terminal":
        sla_state = "terminal"
    else:
        sla_state = "system"

    return {
        "priority_bucket": bucket,
        "priority_rank": _PRIORITY_BUCKETS[bucket],
        "requires_reply": requires_reply,
        "sla_state": sla_state,
        "is_terminal": terminal,
    }


def _normalize_ai_fit(
    payload_json: dict[str, Any] | None,
    *,
    created_at: Optional[datetime],
) -> dict[str, object]:
    scorecard = payload_json.get("scorecard") if isinstance(payload_json, dict) else None
    fit = payload_json.get("fit") if isinstance(payload_json, dict) else None
    fit = fit if isinstance(fit, dict) else {}
    recommendation = None
    risk_hint = None
    if isinstance(scorecard, dict):
        raw_recommendation = scorecard.get("recommendation")
        if isinstance(raw_recommendation, str):
            recommendation = raw_recommendation.strip().lower() or None
        blockers = scorecard.get("blockers") or []
        missing_data = scorecard.get("missing_data") or []
        source_items = blockers if blockers else missing_data
        if source_items and isinstance(source_items[0], dict):
            risk_hint = str(
                source_items[0].get("label")
                or source_items[0].get("evidence")
                or ""
            ).strip() or None

    raw_score = scorecard.get("final_score") if isinstance(scorecard, dict) else fit.get("score")
    score: Optional[int] = None
    if isinstance(raw_score, (int, float)):
        score = max(0, min(100, int(raw_score)))
    raw_level = fit_level_from_score(score) if score is not None else fit.get("level")
    level = raw_level.lower().strip() if isinstance(raw_level, str) else None
    if level not in {"high", "medium", "low", "unknown"}:
        level = None
    return {
        "score": score,
        "level": level,
        "recommendation": recommendation,
        "risk_hint": risk_hint,
        "updated_at": _iso(created_at),
    }


def _serialize_workspace(workspace: CandidateChatWorkspace | None) -> dict[str, object]:
    if workspace is None:
        return {
            "shared_note": "",
            "agreements": [],
            "follow_up_due_at": None,
            "updated_by": None,
            "updated_at": None,
        }
    agreements = [
        str(item).strip()
        for item in list(workspace.agreements_json or [])
        if str(item or "").strip()
    ]
    return {
        "shared_note": str(workspace.shared_note or ""),
        "agreements": agreements,
        "follow_up_due_at": _iso(workspace.follow_up_due_at),
        "updated_by": workspace.updated_by,
        "updated_at": _iso(workspace.updated_at),
    }


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


async def _load_accessible_user(
    session,
    candidate_id: int,
    principal: Principal,
    *,
    recruiter_city_ids: set[int],
    city_cache: dict[str, Optional[int]],
) -> User:
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
    return user


async def _load_thread_rows(
    principal: Principal,
) -> tuple[
    list[tuple[User, str | None, datetime | None, str | None, str | None, dict | None]],
    dict[int, Optional[datetime]],
    dict[int, Optional[datetime]],
    dict[int, int],
    dict[int, CandidateChatWorkspace],
    dict[int, str],
    dict[int, dict[str, object]],
]:
    latest_sq = (
        select(
            ChatMessage.candidate_id.label("candidate_id"),
            ChatMessage.text.label("text"),
            ChatMessage.created_at.label("created_at"),
            ChatMessage.direction.label("direction"),
            ChatMessage.author_label.label("author_label"),
            ChatMessage.payload_json.label("payload_json"),
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
                    latest_sq.c.author_label,
                    latest_sq.c.payload_json,
                )
                .join(latest_sq, latest_sq.c.candidate_id == User.id)
                .where(latest_sq.c.rn == 1)
                .order_by(latest_sq.c.created_at.desc())
            )
        ).all()

        candidate_ids = [int(row[0].id) for row in rows]
        if not candidate_ids:
            return [], {}, {}, {}, {}, {}, {}

        read_rows = (
            await session.execute(
                select(CandidateChatRead).where(
                    CandidateChatRead.candidate_id.in_(candidate_ids),
                    CandidateChatRead.principal_type == principal.type,
                    CandidateChatRead.principal_id == principal.id,
                )
            )
        ).scalars().all()
        read_map = {int(row.candidate_id): _as_utc(row.last_read_at) for row in read_rows}
        archived_map = {
            int(row.candidate_id): _as_utc(getattr(row, "archived_at", None))
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
                    ChatMessage.direction == "inbound",
                    or_(
                        CandidateChatRead.last_read_at.is_(None),
                        ChatMessage.created_at > CandidateChatRead.last_read_at,
                    ),
                )
                .group_by(ChatMessage.candidate_id)
            )
        ).all()
        unread_map = {int(candidate_id): int(total or 0) for candidate_id, total in unread_rows}

        workspace_rows = (
            await session.execute(
                select(CandidateChatWorkspace).where(CandidateChatWorkspace.candidate_id.in_(candidate_ids))
            )
        ).scalars().all()
        workspace_map = {int(row.candidate_id): row for row in workspace_rows}

        recruiter_map: dict[int, str] = {}
        recruiter_ids = {
            int(user.responsible_recruiter_id)
            for user, *_rest in rows
            if user.responsible_recruiter_id is not None
        }
        if recruiter_ids:
            recruiter_rows = (
                await session.execute(select(Recruiter).where(Recruiter.id.in_(recruiter_ids)))
            ).scalars().all()
            recruiter_map = {int(recruiter.id): recruiter.name for recruiter in recruiter_rows}

        ai_fit_map: dict[int, dict[str, object]] = {}
        ai_sq = (
            select(
                AIOutput.scope_id.label("candidate_id"),
                AIOutput.payload_json.label("payload_json"),
                AIOutput.created_at.label("created_at"),
                func.row_number()
                .over(
                    partition_by=AIOutput.scope_id,
                    order_by=AIOutput.created_at.desc(),
                )
                .label("rn"),
            )
            .where(
                AIOutput.scope_type == "candidate",
                AIOutput.kind == "candidate_summary_v1",
                AIOutput.scope_id.in_(candidate_ids),
                AIOutput.expires_at > datetime.now(timezone.utc),
            )
        ).subquery()
        ai_rows = await session.execute(
            select(ai_sq.c.candidate_id, ai_sq.c.payload_json, ai_sq.c.created_at).where(
                ai_sq.c.rn == 1
            )
        )
        for candidate_id, payload_json, created_at in ai_rows:
            ai_fit_map[int(candidate_id)] = _normalize_ai_fit(
                payload_json if isinstance(payload_json, dict) else None,
                created_at=created_at,
            )

    return rows, read_map, archived_map, unread_map, workspace_map, recruiter_map, ai_fit_map


async def list_threads(
    principal: Principal,
    *,
    search: Optional[str] = None,
    unread_only: bool = False,
    folder: Literal["inbox", "archive", "all"] = "inbox",
    limit: int = 100,
) -> dict[str, object]:
    principal = _normalize_principal(principal)
    recruiter_city_ids = await _recruiter_city_ids(principal)
    city_cache: dict[str, Optional[int]] = {}
    rows, read_map, archived_map, unread_map, workspace_map, recruiter_map, ai_fit_map = await _load_thread_rows(principal)

    query = (search or "").strip().lower()
    threads: list[dict[str, object]] = []
    latest_event_at: Optional[datetime] = None

    for user, last_text, last_created_at, last_direction, last_author_label, last_payload_json in rows:
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

        preview = compact_chat_preview(
            last_text,
            fallback="Системное сообщение" if last_direction == "outbound" else "Переписка ещё не началась",
        )
        haystack = " ".join(
            value
            for value in [
                user.fio,
                user.city,
                user.telegram_username,
                str(user.telegram_id) if user.telegram_id is not None else "",
                preview,
            ]
            if value
        ).lower()
        if query and query not in haystack:
            continue

        last_message_at = _as_utc(last_created_at)
        last_read_at = read_map.get(int(user.id))
        archived_at = archived_map.get(int(user.id))
        workspace = workspace_map.get(int(user.id))
        workspace_updated_at = _as_utc(workspace.updated_at) if workspace else None
        is_archived = archived_at is not None and (last_message_at is None or last_message_at <= archived_at)
        last_message_kind = derive_chat_message_kind(
            last_direction,
            author_label=last_author_label,
            payload_json=last_payload_json if isinstance(last_payload_json, dict) else None,
        )
        priority = _priority_payload(
            user=user,
            last_message_kind=last_message_kind,
            last_message_at=last_message_at,
            follow_up_due_at=workspace.follow_up_due_at if workspace else None,
        )
        priority_bucket = str(priority["priority_bucket"])
        if folder == "inbox" and is_archived:
            continue
        if folder == "archive" and not is_archived:
            continue
        if folder == "inbox" and priority_bucket in {"system", "terminal"} and unread_count <= 0:
            continue

        ai_fit = ai_fit_map.get(int(user.id), {})
        risk_hint = str(ai_fit.get("risk_hint") or "").strip() or _default_risk_hint(
            priority_bucket,
            last_message_kind=last_message_kind,
            is_terminal=bool(priority["is_terminal"]),
        )

        event_at = max(
            [
                value
                for value in [last_message_at, last_read_at, archived_at, workspace_updated_at]
                if value is not None
            ],
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
                "status_slug": _status_slug(user),
                "profile_url": f"/app/candidates/{user.id}",
                "telegram_username": user.telegram_username or user.username,
                "created_at": _iso(event_at) or datetime.now(timezone.utc).isoformat(),
                "last_message_at": _iso(last_message_at),
                "archived_at": _iso(archived_at),
                "is_archived": is_archived,
                "last_message_preview": preview,
                "last_message_kind": last_message_kind,
                "priority_bucket": priority_bucket,
                "priority_rank": int(priority["priority_rank"]),
                "requires_reply": bool(priority["requires_reply"]),
                "sla_state": str(priority["sla_state"]),
                "is_terminal": bool(priority["is_terminal"]),
                "vacancy_label": user.desired_position or "Вакансия не указана",
                "assignee_label": recruiter_map.get(int(user.responsible_recruiter_id or 0)) or "Не назначен",
                "relevance_score": ai_fit.get("score"),
                "relevance_level": ai_fit.get("level") or "unknown",
                "risk_hint": risk_hint,
                "workspace_follow_up_due_at": _iso(workspace.follow_up_due_at) if workspace else None,
                "last_message": {
                    "text": (last_text or "").strip() or "Сообщение",
                    "preview": preview,
                    "created_at": _iso(last_message_at),
                    "direction": last_direction,
                    "kind": last_message_kind,
                },
                "unread_count": unread_count,
            }
        )

    threads.sort(
        key=lambda item: (
            int(item["priority_rank"]) if isinstance(item.get("priority_rank"), int) else 999,
            -int(
                datetime.fromisoformat(
                    str(
                        item.get("last_message_at")
                        or item.get("created_at")
                        or datetime.now(timezone.utc).isoformat()
                    )
                ).timestamp()
            ),
        ),
    )
    return {
        "threads": threads[: max(1, min(limit, 200))],
        "latest_event_at": _iso(latest_event_at),
    }


async def wait_for_thread_updates(
    principal: Principal,
    *,
    since: Optional[datetime],
    timeout: int = 25,
    search: Optional[str] = None,
    unread_only: bool = False,
    folder: Literal["inbox", "archive", "all"] = "inbox",
    limit: int = 100,
) -> dict[str, object]:
    deadline = datetime.now(timezone.utc) + timedelta(seconds=max(timeout, 5))
    since_utc = _as_utc(since)

    while True:
        payload = await list_threads(
            principal,
            search=search,
            unread_only=unread_only,
            folder=folder,
            limit=limit,
        )
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


async def get_workspace(candidate_id: int, principal: Principal) -> dict[str, object]:
    principal = _normalize_principal(principal)
    recruiter_city_ids = await _recruiter_city_ids(principal)
    city_cache: dict[str, Optional[int]] = {}

    async with async_session() as session:
        await _load_accessible_user(
            session,
            candidate_id,
            principal,
            recruiter_city_ids=recruiter_city_ids,
            city_cache=city_cache,
        )
        workspace = await session.scalar(
            select(CandidateChatWorkspace).where(CandidateChatWorkspace.candidate_id == candidate_id)
        )
        return _serialize_workspace(workspace)


async def update_workspace(
    candidate_id: int,
    principal: Principal,
    *,
    shared_note: str,
    agreements: list[str],
    follow_up_due_at: Optional[datetime],
    updated_by: Optional[str] = None,
) -> dict[str, object]:
    principal = _normalize_principal(principal)
    recruiter_city_ids = await _recruiter_city_ids(principal)
    city_cache: dict[str, Optional[int]] = {}
    normalized_agreements = [item.strip() for item in agreements if item.strip()][:8]

    async with async_session() as session:
        await _load_accessible_user(
            session,
            candidate_id,
            principal,
            recruiter_city_ids=recruiter_city_ids,
            city_cache=city_cache,
        )
        workspace = await session.scalar(
            select(CandidateChatWorkspace).where(CandidateChatWorkspace.candidate_id == candidate_id)
        )
        now = datetime.now(timezone.utc)
        if workspace is None:
            workspace = CandidateChatWorkspace(
                candidate_id=candidate_id,
                shared_note=shared_note or "",
                agreements_json=normalized_agreements,
                follow_up_due_at=_as_utc(follow_up_due_at),
                updated_by=updated_by,
                created_at=now,
                updated_at=now,
            )
            session.add(workspace)
        else:
            workspace.shared_note = shared_note or ""
            workspace.agreements_json = normalized_agreements
            workspace.follow_up_due_at = _as_utc(follow_up_due_at)
            workspace.updated_by = updated_by
            workspace.updated_at = now
        await session.commit()
        await session.refresh(workspace)
        return _serialize_workspace(workspace)


async def mark_read(candidate_id: int, principal: Principal) -> None:
    principal = _normalize_principal(principal)
    recruiter_city_ids = await _recruiter_city_ids(principal)
    city_cache: dict[str, Optional[int]] = {}

    async with async_session() as session:
        await _load_accessible_user(
            session,
            candidate_id,
            principal,
            recruiter_city_ids=recruiter_city_ids,
            city_cache=city_cache,
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
        try:
            await session.commit()
        except IntegrityError:
            # Concurrent "mark as read" requests may race on the unique constraint.
            await session.rollback()
            state = await session.scalar(
                select(CandidateChatRead).where(
                    CandidateChatRead.candidate_id == candidate_id,
                    CandidateChatRead.principal_type == principal.type,
                    CandidateChatRead.principal_id == principal.id,
                )
            )
            if state is None:
                raise
            state.last_read_at = now
            await session.commit()


async def set_archived(candidate_id: int, principal: Principal, *, archived: bool) -> None:
    principal = _normalize_principal(principal)
    recruiter_city_ids = await _recruiter_city_ids(principal)
    city_cache: dict[str, Optional[int]] = {}

    async with async_session() as session:
        await _load_accessible_user(
            session,
            candidate_id,
            principal,
            recruiter_city_ids=recruiter_city_ids,
            city_cache=city_cache,
        )

        state = await session.scalar(
            select(CandidateChatRead).where(
                CandidateChatRead.candidate_id == candidate_id,
                CandidateChatRead.principal_type == principal.type,
                CandidateChatRead.principal_id == principal.id,
            )
        )
        if state is None and not archived:
            return

        now = datetime.now(timezone.utc)
        if state is None:
            state = CandidateChatRead(
                candidate_id=candidate_id,
                principal_type=principal.type,
                principal_id=principal.id,
                archived_at=now,
            )
            session.add(state)
        else:
            state.archived_at = now if archived else None
        await session.commit()


__all__ = [
    "get_workspace",
    "list_threads",
    "mark_read",
    "set_archived",
    "update_workspace",
    "wait_for_thread_updates",
]
