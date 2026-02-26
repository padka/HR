from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select

from backend.apps.admin_ui.security import Principal
from backend.apps.admin_ui.utils import DEFAULT_TZ
from backend.core.db import async_session
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.models import CalendarTask, Recruiter

__all__ = [
    "create_calendar_task",
    "update_calendar_task",
    "delete_calendar_task",
    "list_calendar_tasks_for_range",
]


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_title(value: str) -> str:
    title = sanitize_plain_text(value or "", max_length=180).strip()
    if not title:
        raise ValueError("title_required")
    return title


def _normalize_description(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    clean = sanitize_plain_text(value, max_length=1500).strip()
    return clean or None


def _serialize_task(task: CalendarTask, recruiter_name: str, recruiter_tz: Optional[str]) -> Dict[str, object]:
    return {
        "id": int(task.id),
        "title": task.title,
        "description": task.description,
        "start_utc": task.start_utc.isoformat() if task.start_utc else None,
        "end_utc": task.end_utc.isoformat() if task.end_utc else None,
        "is_done": bool(task.is_done),
        "recruiter_id": int(task.recruiter_id),
        "recruiter_name": recruiter_name,
        "recruiter_tz": recruiter_tz or DEFAULT_TZ,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


async def _resolve_recruiter_id(
    principal: Principal,
    requested_recruiter_id: Optional[int],
) -> int:
    if principal.type == "recruiter":
        if requested_recruiter_id is not None and requested_recruiter_id != principal.id:
            raise PermissionError("forbidden")
        return int(principal.id)

    if requested_recruiter_id is None:
        raise ValueError("recruiter_required")

    async with async_session() as session:
        recruiter = await session.get(Recruiter, requested_recruiter_id)
        if recruiter is None:
            raise LookupError("recruiter_not_found")
    return int(requested_recruiter_id)


def _assert_task_scope(task: CalendarTask, principal: Principal) -> None:
    if principal.type == "admin":
        return
    if int(task.recruiter_id) != int(principal.id):
        raise PermissionError("forbidden")


async def list_calendar_tasks_for_range(
    start_utc: datetime,
    end_utc: datetime,
    *,
    recruiter_id: Optional[int] = None,
) -> List[Dict[str, object]]:
    start_utc = _ensure_aware_utc(start_utc)
    end_utc = _ensure_aware_utc(end_utc)

    async with async_session() as session:
        stmt = (
            select(CalendarTask, Recruiter.name, Recruiter.tz)
            .join(Recruiter, Recruiter.id == CalendarTask.recruiter_id)
            .where(
                CalendarTask.start_utc < end_utc,
                CalendarTask.end_utc > start_utc,
            )
            .order_by(CalendarTask.start_utc.asc(), CalendarTask.id.asc())
        )
        if recruiter_id is not None:
            stmt = stmt.where(CalendarTask.recruiter_id == recruiter_id)

        rows = (await session.execute(stmt)).all()
        return [_serialize_task(task, recruiter_name, recruiter_tz) for task, recruiter_name, recruiter_tz in rows]


async def create_calendar_task(
    *,
    principal: Principal,
    title: str,
    start_utc: datetime,
    end_utc: datetime,
    description: Optional[str] = None,
    recruiter_id: Optional[int] = None,
    is_done: bool = False,
) -> Dict[str, object]:
    normalized_title = _normalize_title(title)
    normalized_description = _normalize_description(description)
    start_value = _ensure_aware_utc(start_utc)
    end_value = _ensure_aware_utc(end_utc)
    if end_value <= start_value:
        raise ValueError("invalid_time_range")

    resolved_recruiter_id = await _resolve_recruiter_id(principal, recruiter_id)

    async with async_session() as session:
        recruiter = await session.get(Recruiter, resolved_recruiter_id)
        if recruiter is None:
            raise LookupError("recruiter_not_found")

        task = CalendarTask(
            recruiter_id=resolved_recruiter_id,
            title=normalized_title,
            description=normalized_description,
            start_utc=start_value,
            end_utc=end_value,
            is_done=bool(is_done),
            created_by_type=principal.type,
            created_by_id=int(principal.id),
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return _serialize_task(task, recruiter.name, recruiter.tz)


async def update_calendar_task(
    task_id: int,
    *,
    principal: Principal,
    title: Optional[str] = None,
    description: Optional[str] = None,
    start_utc: Optional[datetime] = None,
    end_utc: Optional[datetime] = None,
    is_done: Optional[bool] = None,
    recruiter_id: Optional[int] = None,
) -> Dict[str, object]:
    async with async_session() as session:
        task = await session.get(CalendarTask, task_id)
        if task is None:
            raise LookupError("task_not_found")
        _assert_task_scope(task, principal)

        if recruiter_id is not None:
            if principal.type == "recruiter" and recruiter_id != principal.id:
                raise PermissionError("forbidden")
            recruiter = await session.get(Recruiter, recruiter_id)
            if recruiter is None:
                raise LookupError("recruiter_not_found")
            task.recruiter_id = recruiter_id
        else:
            recruiter = await session.get(Recruiter, task.recruiter_id)

        if title is not None:
            task.title = _normalize_title(title)
        if description is not None:
            task.description = _normalize_description(description)
        if start_utc is not None:
            task.start_utc = _ensure_aware_utc(start_utc)
        if end_utc is not None:
            task.end_utc = _ensure_aware_utc(end_utc)
        if is_done is not None:
            task.is_done = bool(is_done)

        if task.end_utc <= task.start_utc:
            raise ValueError("invalid_time_range")

        task.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(task)
        recruiter_name = recruiter.name if recruiter is not None else ""
        recruiter_tz = recruiter.tz if recruiter is not None else DEFAULT_TZ
        return _serialize_task(task, recruiter_name, recruiter_tz)


async def delete_calendar_task(task_id: int, *, principal: Principal) -> bool:
    async with async_session() as session:
        task = await session.get(CalendarTask, task_id)
        if task is None:
            return False
        _assert_task_scope(task, principal)
        await session.delete(task)
        await session.commit()
        return True
