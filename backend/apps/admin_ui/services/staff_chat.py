from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, func, and_, or_

from backend.apps.admin_ui.security import Principal
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.candidates.models import User
from backend.domain.candidates.status import get_status_label
from backend.domain.models import (
    Recruiter,
    StaffMessage,
    StaffMessageAttachment,
    StaffMessageTask,
    StaffThread,
    StaffThreadMember,
)

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

MAX_ATTACHMENT_SIZE_MB = 20
DEFAULT_GROUP_TITLE = "Общий чат отдела"


def _principal_label(principal_type: str, principal_id: int, recruiter: Optional[Recruiter]) -> str:
    if principal_type == "admin":
        return "Администратор"
    if recruiter:
        return recruiter.name
    return f"Рекрутер {principal_id}"


async def _load_recruiter(principal_id: int) -> Optional[Recruiter]:
    async with async_session() as session:
        rec = await session.get(Recruiter, principal_id)
        if rec:
            session.expunge(rec)
        return rec


def _member_filter(principal: Principal):
    if principal.type == "admin":
        return or_(
            and_(StaffThreadMember.principal_type == "admin", StaffThreadMember.principal_id == principal.id),
            and_(StaffThreadMember.principal_type == "admin", StaffThreadMember.principal_id == -1),
        )
    return and_(
        StaffThreadMember.principal_type == principal.type,
        StaffThreadMember.principal_id == principal.id,
    )


def _member_key(member: StaffThreadMember) -> tuple[str, int]:
    if member.principal_type == "admin":
        return ("admin", -1)
    return (member.principal_type, member.principal_id)


def _merge_read_map(members: Iterable[StaffThreadMember]) -> dict[tuple[str, int], Optional[datetime]]:
    read_map: dict[tuple[str, int], Optional[datetime]] = {}
    for member in members:
        key = _member_key(member)
        current = read_map.get(key)
        if member.last_read_at is None:
            if key not in read_map:
                read_map[key] = None
            continue
        if current is None or member.last_read_at > current:
            read_map[key] = member.last_read_at
    return read_map


def _format_member_label(member: StaffThreadMember, recruiter: Optional[Recruiter]) -> str:
    return _principal_label(member.principal_type, member.principal_id, recruiter)


def _format_candidate_card(user: User, recruiter: Optional[Recruiter]) -> dict:
    status_label = get_status_label(user.candidate_status)
    status_slug = user.candidate_status.value if user.candidate_status else None
    return {
        "id": user.id,
        "name": user.fio or "Без имени",
        "city": user.city or "Не указан",
        "status_label": status_label,
        "status_slug": status_slug,
        "telegram_id": user.telegram_id,
        "profile_url": f"/app/candidates/{user.id}",
        "recruiter": {
            "id": recruiter.id if recruiter else None,
            "name": recruiter.name if recruiter else None,
        },
    }


def _serialize_member(member: StaffThreadMember, recruiter: Optional[Recruiter]) -> dict:
    return {
        "type": member.principal_type,
        "id": member.principal_id,
        "role": member.role,
        "name": _format_member_label(member, recruiter),
        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
        "last_read_at": member.last_read_at.isoformat() if member.last_read_at else None,
        "is_placeholder": member.principal_type == "admin" and member.principal_id == -1,
    }


def _serialize_message(
    msg: StaffMessage,
    *,
    attachments: list[StaffMessageAttachment],
    task: Optional[StaffMessageTask],
    candidate: Optional[User],
    recruiter_map: dict[int, Recruiter],
    read_map: dict[tuple[str, int], Optional[datetime]],
) -> dict:
    sender_recruiter = recruiter_map.get(msg.sender_id) if msg.sender_type == "recruiter" else None
    sender_label = _principal_label(msg.sender_type, msg.sender_id, sender_recruiter)
    sender_key = ("admin", -1) if msg.sender_type == "admin" else (msg.sender_type, msg.sender_id)
    recipient_keys = [key for key in read_map.keys() if key != sender_key]
    read_by_count = 0
    for key in recipient_keys:
        last_read = read_map.get(key)
        if last_read and last_read >= msg.created_at:
            read_by_count += 1

    payload = {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_type": msg.sender_type,
        "sender_id": msg.sender_id,
        "sender_label": sender_label,
        "type": msg.message_type,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "attachments": [
            {
                "id": att.id,
                "filename": att.filename,
                "mime_type": att.mime_type,
                "size": att.size,
            }
            for att in attachments
        ],
        "read_by_count": read_by_count,
        "read_by_total": len(recipient_keys),
    }

    if task:
        task_payload = {
            "candidate_id": task.candidate_id,
            "status": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "decided_at": task.decided_at.isoformat() if task.decided_at else None,
            "decided_by_type": task.decided_by_type,
            "decided_by_id": task.decided_by_id,
            "decision_comment": task.decision_comment,
        }
        payload["task"] = task_payload
        if candidate:
            recruiter = recruiter_map.get(getattr(candidate, "responsible_recruiter_id", None))
            payload["candidate"] = _format_candidate_card(candidate, recruiter)

    return payload

async def _ensure_member(thread_id: int, principal: Principal) -> StaffThreadMember:
    async with async_session() as session:
        member = await session.get(
            StaffThreadMember,
            (thread_id, principal.type, principal.id),
        )
        if not member and principal.type == "admin":
            member = await session.get(
                StaffThreadMember,
                (thread_id, "admin", -1),
            )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Чат не найден"})
        session.expunge(member)
        return member


async def _ensure_default_threads(principal: Principal) -> None:
    """Ensure baseline staff chats exist so users always see at least one thread."""
    async with async_session() as session:
        # Ensure default group chat exists
        group = (
            await session.execute(
                select(StaffThread).where(
                    StaffThread.thread_type == "group",
                    StaffThread.title == DEFAULT_GROUP_TITLE,
                )
            )
        ).scalar_one_or_none()

        if not group:
            group = StaffThread(thread_type="group", title=DEFAULT_GROUP_TITLE)
            session.add(group)
            await session.flush()

            # Add admin placeholder
            session.add(
                StaffThreadMember(
                    thread_id=group.id,
                    principal_type="admin",
                    principal_id=-1,
                    role="owner",
                )
            )

            recruiters = (
                await session.execute(
                    select(Recruiter).where(Recruiter.active.is_(True))
                )
            ).scalars().all()
            for rec in recruiters:
                session.add(
                    StaffThreadMember(
                        thread_id=group.id,
                        principal_type="recruiter",
                        principal_id=rec.id,
                        role="member",
                    )
                )
            await session.commit()
        else:
            # Ensure current principal is member of the default group
            member = await session.get(
                StaffThreadMember,
                (group.id, principal.type, principal.id),
            )
            if not member:
                session.add(
                    StaffThreadMember(
                        thread_id=group.id,
                        principal_type=principal.type,
                        principal_id=principal.id,
                        role="member",
                    )
                )
                await session.commit()

        # Ensure recruiter has a direct channel to admin
        if principal.type == "recruiter":
            recruiter_thread_ids = (
                await session.execute(
                    select(StaffThreadMember.thread_id).where(
                        StaffThreadMember.principal_type == "recruiter",
                        StaffThreadMember.principal_id == principal.id,
                    )
                )
            ).scalars().all()
            if recruiter_thread_ids:
                existing = (
                    await session.execute(
                        select(StaffThread)
                        .where(
                            StaffThread.id.in_(recruiter_thread_ids),
                            StaffThread.thread_type == "direct",
                        )
                        .join(StaffThreadMember)
                        .where(
                            StaffThreadMember.principal_type == "admin",
                            StaffThreadMember.principal_id == -1,
                        )
                    )
                ).scalar_one_or_none()
            else:
                existing = None

            if not existing:
                direct = StaffThread(thread_type="direct", title=None)
                session.add(direct)
                await session.flush()
                session.add_all(
                    [
                        StaffThreadMember(
                            thread_id=direct.id,
                            principal_type="recruiter",
                            principal_id=principal.id,
                            role="member",
                        ),
                        StaffThreadMember(
                            thread_id=direct.id,
                            principal_type="admin",
                            principal_id=-1,
                            role="member",
                        ),
                    ]
                )
                await session.commit()


async def list_threads(principal: Principal) -> dict:
    await _ensure_default_threads(principal)
    async with async_session() as session:
        members = (
            await session.execute(
                select(StaffThreadMember)
                .where(_member_filter(principal))
            )
        ).scalars().all()
        thread_ids = sorted({m.thread_id for m in members})
        if not thread_ids:
            return []

        threads = (
            await session.execute(
                select(StaffThread).where(StaffThread.id.in_(thread_ids))
            )
        ).scalars().all()

        result: List[dict] = []
        latest_event_at: Optional[datetime] = None
        for thread in threads:
            member_reads = [
                m.last_read_at
                for m in members
                if m.thread_id == thread.id and m.last_read_at is not None
            ]
            member_last_read = max(member_reads) if member_reads else None
            last_msg = (
                await session.execute(
                    select(StaffMessage)
                    .where(StaffMessage.thread_id == thread.id)
                    .order_by(StaffMessage.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            # resolve display title
            display_title = thread.title or "Групповой чат"
            if thread.thread_type == "direct":
                # find other member (avoid admin placeholder)
                if principal.type == "admin":
                    other = (
                        await session.execute(
                            select(StaffThreadMember).where(
                                StaffThreadMember.thread_id == thread.id,
                                StaffThreadMember.principal_type != "admin",
                            )
                        )
                    ).scalar_one_or_none()
                else:
                    others = (
                        await session.execute(
                            select(StaffThreadMember)
                            .where(
                                StaffThreadMember.thread_id == thread.id,
                                ~(
                                    (StaffThreadMember.principal_type == principal.type)
                                    & (StaffThreadMember.principal_id == principal.id)
                                ),
                            )
                        )
                    ).scalars().all()
                    other = None
                    if others:
                        other = next((item for item in others if item.principal_type != "admin"), others[0])
                if other:
                    recruiter = None
                    if other.principal_type == "recruiter":
                        recruiter = await session.get(Recruiter, other.principal_id)
                    display_title = _principal_label(other.principal_type, other.principal_id, recruiter)

            unread_count = 0
            if member_last_read is None:
                unread_count = await session.scalar(
                    select(func.count(StaffMessage.id)).where(StaffMessage.thread_id == thread.id)
                ) or 0
            else:
                unread_count = await session.scalar(
                    select(func.count(StaffMessage.id)).where(
                        StaffMessage.thread_id == thread.id,
                        StaffMessage.created_at > member_last_read,
                    )
                ) or 0

            thread_event_at = last_msg.created_at if last_msg else thread.created_at
            if latest_event_at is None or thread_event_at > latest_event_at:
                latest_event_at = thread_event_at

            result.append(
                {
                    "id": thread.id,
                    "type": thread.thread_type,
                    "title": display_title,
                    "created_at": thread.created_at.isoformat(),
                    "last_message": {
                        "text": last_msg.text if last_msg else None,
                        "created_at": last_msg.created_at.isoformat() if last_msg else None,
                        "sender_type": last_msg.sender_type if last_msg else None,
                        "sender_id": last_msg.sender_id if last_msg else None,
                        "type": last_msg.message_type if last_msg else None,
                    },
                    "unread_count": unread_count,
                }
            )

        result.sort(key=lambda item: item["last_message"]["created_at"] or item["created_at"], reverse=True)
        return {
            "threads": result,
            "latest_event_at": latest_event_at.isoformat() if latest_event_at else None,
        }


async def create_or_get_direct_thread(principal: Principal, other_type: str, other_id: int) -> dict:
    async with async_session() as session:
        if principal.type == "admin":
            member_threads = (
                await session.execute(
                    select(StaffThreadMember.thread_id).where(
                        StaffThreadMember.principal_type == "admin",
                        StaffThreadMember.principal_id.in_([principal.id, -1]),
                    )
                )
            ).scalars().all()
        else:
            member_threads = (
                await session.execute(
                    select(StaffThreadMember.thread_id)
                    .where(
                        StaffThreadMember.principal_type == principal.type,
                        StaffThreadMember.principal_id == principal.id,
                    )
                )
            ).scalars().all()

        if member_threads:
            existing = (
                await session.execute(
                    select(StaffThread)
                    .where(
                        StaffThread.id.in_(member_threads),
                        StaffThread.thread_type == "direct",
                    )
                    .join(StaffThreadMember)
                    .where(
                        StaffThreadMember.principal_type == other_type,
                        StaffThreadMember.principal_id == other_id,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                return {"id": existing.id, "type": existing.thread_type, "title": existing.title}

        thread = StaffThread(thread_type="direct", title=None)
        session.add(thread)
        await session.flush()

        principal_member_id = principal.id
        if principal.type == "admin":
            principal_member_id = -1

        session.add_all(
            [
                StaffThreadMember(
                    thread_id=thread.id,
                    principal_type=principal.type,
                    principal_id=principal_member_id,
                    role="member",
                ),
                StaffThreadMember(
                    thread_id=thread.id,
                    principal_type=other_type,
                    principal_id=other_id,
                    role="member",
                ),
            ]
        )
        await session.commit()
        return {"id": thread.id, "type": thread.thread_type, "title": thread.title}


async def create_group_thread(principal: Principal, title: str, members: Iterable[dict]) -> dict:
    if principal.type != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Недостаточно прав"})

    async with async_session() as session:
        thread = StaffThread(thread_type="group", title=title or "Групповой чат")
        session.add(thread)
        await session.flush()

        unique_members = {(m["type"], int(m["id"])) for m in members if m.get("type") and m.get("id")}
        for m_type, _ in unique_members:
            if m_type not in {"admin", "recruiter"}:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Недопустимый тип участника"})
        unique_members.add((principal.type, principal.id))

        session.add_all(
            [
                StaffThreadMember(
                    thread_id=thread.id,
                    principal_type=m_type,
                    principal_id=m_id,
                    role="owner" if (m_type, m_id) == (principal.type, principal.id) else "member",
                )
                for m_type, m_id in unique_members
            ]
        )
        await session.commit()
        return {"id": thread.id, "type": thread.thread_type, "title": thread.title}


async def list_messages(thread_id: int, principal: Principal, limit: int = 50, before: Optional[datetime] = None) -> dict:
    await _ensure_member(thread_id, principal)
    async with async_session() as session:
        stmt = select(StaffMessage).where(StaffMessage.thread_id == thread_id)
        if before:
            stmt = stmt.where(StaffMessage.created_at < before)
        stmt = stmt.order_by(StaffMessage.created_at.desc()).limit(min(limit, 200))
        messages = (await session.execute(stmt)).scalars().all()
        message_ids = [msg.id for msg in messages]

        attachments_map: dict[int, list[StaffMessageAttachment]] = {}
        if message_ids:
            attachments = (
                await session.execute(
                    select(StaffMessageAttachment).where(StaffMessageAttachment.message_id.in_(message_ids))
                )
            ).scalars().all()
            for att in attachments:
                attachments_map.setdefault(att.message_id, []).append(att)

        task_map: dict[int, StaffMessageTask] = {}
        candidate_map: dict[int, User] = {}
        if message_ids:
            tasks = (
                await session.execute(
                    select(StaffMessageTask).where(StaffMessageTask.message_id.in_(message_ids))
                )
            ).scalars().all()
            for task in tasks:
                task_map[task.message_id] = task

            candidate_ids = [task.candidate_id for task in tasks]
            if candidate_ids:
                candidates = (
                    await session.execute(select(User).where(User.id.in_(candidate_ids)))
                ).scalars().all()
                candidate_map = {candidate.id: candidate for candidate in candidates}

        members = (
            await session.execute(select(StaffThreadMember).where(StaffThreadMember.thread_id == thread_id))
        ).scalars().all()
        read_map = _merge_read_map(members)

        recruiter_ids = {m.principal_id for m in members if m.principal_type == "recruiter"}
        recruiter_ids.update(
            msg.sender_id for msg in messages if msg.sender_type == "recruiter"
        )
        for candidate in candidate_map.values():
            recruiter_id = getattr(candidate, "responsible_recruiter_id", None)
            if recruiter_id:
                recruiter_ids.add(recruiter_id)
        recruiter_map: dict[int, Recruiter] = {}
        if recruiter_ids:
            recruiters = (
                await session.execute(select(Recruiter).where(Recruiter.id.in_(recruiter_ids)))
            ).scalars().all()
            recruiter_map = {rec.id: rec for rec in recruiters}

        member_payload = [
            _serialize_member(member, recruiter_map.get(member.principal_id))
            for member in members
        ]

        payload = [
            _serialize_message(
                msg,
                attachments=attachments_map.get(msg.id, []),
                task=task_map.get(msg.id),
                candidate=candidate_map.get(task_map[msg.id].candidate_id) if msg.id in task_map else None,
                recruiter_map=recruiter_map,
                read_map=read_map,
            )
            for msg in reversed(messages)
        ]

        latest_message_at = max((msg.created_at for msg in messages), default=None)
        latest_edit_at = max((msg.edited_at for msg in messages if msg.edited_at), default=None)
        latest_read_at = max((dt for dt in read_map.values() if dt), default=None)
        latest_activity_at = max(
            (dt for dt in [latest_message_at, latest_edit_at, latest_read_at] if dt),
            default=None,
        )

        return {
            "messages": payload,
            "has_more": len(messages) == limit,
            "latest_message_at": latest_message_at.isoformat() if latest_message_at else None,
            "latest_activity_at": latest_activity_at.isoformat() if latest_activity_at else None,
            "members": member_payload,
        }


def _store_attachment(thread_id: int, upload: UploadFile) -> dict:
    settings = get_settings()
    data_dir = Path(settings.data_dir)
    upload_dir = data_dir / "staff_uploads" / f"thread_{thread_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_name = upload.filename or "file"
    ext = Path(original_name).suffix
    storage_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = upload_dir / storage_name

    contents = upload.file.read()
    size = len(contents)
    if size > MAX_ATTACHMENT_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"message": f"Файл слишком большой (лимит {MAX_ATTACHMENT_SIZE_MB} МБ)"},
        )

    storage_path.write_bytes(contents)

    return {
        "filename": original_name,
        "mime_type": upload.content_type,
        "size": size,
        "storage_path": str(storage_path.relative_to(data_dir)),
    }


async def send_message(
    thread_id: int,
    principal: Principal,
    text: Optional[str],
    files: Optional[List[UploadFile]],
) -> dict:
    await _ensure_member(thread_id, principal)

    if not text and not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Сообщение пустое"})

    async with async_session() as session:
        msg = StaffMessage(
            thread_id=thread_id,
            sender_type=principal.type,
            sender_id=principal.id,
            message_type="text",
            text=text.strip() if text else None,
            created_at=datetime.now(timezone.utc),
        )
        session.add(msg)
        await session.flush()

        attachments = []
        for upload in files or []:
            if upload.content_type and upload.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"message": "Недопустимый тип файла"},
                )
            meta = _store_attachment(thread_id, upload)
            attachments.append(
                StaffMessageAttachment(
                    message_id=msg.id,
                    filename=meta["filename"],
                    mime_type=meta["mime_type"],
                    size=meta["size"],
                    storage_path=meta["storage_path"],
                )
            )

        if attachments:
            session.add_all(attachments)

        await session.commit()
        await session.refresh(msg)

    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_type": msg.sender_type,
        "sender_id": msg.sender_id,
        "type": msg.message_type,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
        "attachments": [
            {
                "id": att.id,
                "filename": att.filename,
                "mime_type": att.mime_type,
                "size": att.size,
            }
            for att in attachments
        ],
    }


async def get_message_payload(message_id: int, principal: Principal) -> dict:
    candidate_id = None
    async with async_session() as session:
        msg = await session.get(StaffMessage, message_id)
        if not msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Сообщение не найдено"})
        member = await session.get(
            StaffThreadMember,
            (msg.thread_id, principal.type, principal.id),
        )
        if not member and principal.type == "admin":
            member = await session.get(
                StaffThreadMember,
                (msg.thread_id, "admin", -1),
            )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Чат не найден"})

        attachments = (
            await session.execute(
                select(StaffMessageAttachment).where(StaffMessageAttachment.message_id == msg.id)
            )
        ).scalars().all()

        task = (
            await session.execute(
                select(StaffMessageTask).where(StaffMessageTask.message_id == msg.id)
            )
        ).scalar_one_or_none()
        candidate = None
        recruiter_ids: set[int] = set()
        if task:
            candidate = await session.get(User, task.candidate_id)
            recruiter_id = getattr(candidate, "responsible_recruiter_id", None) if candidate else None
            if recruiter_id:
                recruiter_ids.add(recruiter_id)

        if msg.sender_type == "recruiter":
            recruiter_ids.add(msg.sender_id)

        recruiter_map: dict[int, Recruiter] = {}
        if recruiter_ids:
            recruiters = (
                await session.execute(select(Recruiter).where(Recruiter.id.in_(recruiter_ids)))
            ).scalars().all()
            recruiter_map = {rec.id: rec for rec in recruiters}

        members = (
            await session.execute(select(StaffThreadMember).where(StaffThreadMember.thread_id == msg.thread_id))
        ).scalars().all()
        read_map = _merge_read_map(members)

        return _serialize_message(
            msg,
            attachments=attachments,
            task=task,
            candidate=candidate,
            recruiter_map=recruiter_map,
            read_map=read_map,
        )


async def list_thread_members(thread_id: int, principal: Principal) -> list[dict]:
    await _ensure_member(thread_id, principal)
    async with async_session() as session:
        members = (
            await session.execute(select(StaffThreadMember).where(StaffThreadMember.thread_id == thread_id))
        ).scalars().all()
        recruiter_ids = {m.principal_id for m in members if m.principal_type == "recruiter"}
        recruiter_map: dict[int, Recruiter] = {}
        if recruiter_ids:
            recruiters = (
                await session.execute(select(Recruiter).where(Recruiter.id.in_(recruiter_ids)))
            ).scalars().all()
            recruiter_map = {rec.id: rec for rec in recruiters}
        return [_serialize_member(member, recruiter_map.get(member.principal_id)) for member in members]


async def add_thread_members(thread_id: int, principal: Principal, members: Iterable[dict]) -> list[dict]:
    if principal.type != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Недостаточно прав"})
    async with async_session() as session:
        thread = await session.get(StaffThread, thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Чат не найден"})

        unique_members = {(m.get("type"), int(m.get("id"))) for m in members if m.get("type") and m.get("id")}
        for member_type, member_id in unique_members:
            if member_type not in {"admin", "recruiter"}:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Недопустимый тип участника"})
            exists = await session.get(StaffThreadMember, (thread_id, member_type, member_id))
            if exists:
                continue
            session.add(
                StaffThreadMember(
                    thread_id=thread_id,
                    principal_type=member_type,
                    principal_id=member_id,
                    role="member",
                )
            )
        await session.commit()
    return await list_thread_members(thread_id, principal)


async def remove_thread_member(thread_id: int, principal: Principal, member_type: str, member_id: int) -> list[dict]:
    if principal.type != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Недостаточно прав"})
    if member_type == "admin" and member_id == -1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Нельзя удалить системного администратора"})
    async with async_session() as session:
        member = await session.get(StaffThreadMember, (thread_id, member_type, member_id))
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Участник не найден"})
        await session.delete(member)
        await session.commit()
    return await list_thread_members(thread_id, principal)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def wait_for_thread_updates(
    principal: Principal,
    *,
    since: Optional[datetime],
    timeout: int = 25,
) -> dict:
    deadline = datetime.now(timezone.utc) + timedelta(seconds=max(timeout, 5))
    since_utc = _as_utc(since)
    while True:
        payload = await list_threads(principal)
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


async def wait_for_message_updates(
    thread_id: int,
    principal: Principal,
    *,
    since: Optional[datetime],
    timeout: int = 25,
) -> dict:
    await _ensure_member(thread_id, principal)
    deadline = datetime.now(timezone.utc) + timedelta(seconds=max(timeout, 5))
    since_utc = _as_utc(since)
    latest_message_at: Optional[datetime] = None
    latest_activity_at: Optional[datetime] = None
    while True:
        async with async_session() as session:
            members = (
                await session.execute(select(StaffThreadMember).where(StaffThreadMember.thread_id == thread_id))
            ).scalars().all()
            read_map = _merge_read_map(members)
            latest_message_at = await session.scalar(
                select(func.max(StaffMessage.created_at)).where(StaffMessage.thread_id == thread_id)
            )
            latest_edit_at = await session.scalar(
                select(func.max(StaffMessage.edited_at)).where(StaffMessage.thread_id == thread_id)
            )
            latest_read_at = max((dt for dt in read_map.values() if dt), default=None)
            latest_activity_at = max(
                (dt for dt in [latest_message_at, latest_edit_at, latest_read_at] if dt),
                default=None,
            )

            latest_activity_at_utc = _as_utc(latest_activity_at)
            if since_utc is None or (latest_activity_at_utc and latest_activity_at_utc > since_utc):
                stmt = select(StaffMessage).where(StaffMessage.thread_id == thread_id)
                if since_utc:
                    stmt = stmt.where(
                        or_(
                            StaffMessage.created_at > since_utc,
                            StaffMessage.edited_at > since_utc,
                        )
                    )
                stmt = stmt.order_by(StaffMessage.created_at.asc())
                messages = (await session.execute(stmt)).scalars().all()
                message_ids = [msg.id for msg in messages]

                attachments_map: dict[int, list[StaffMessageAttachment]] = {}
                if message_ids:
                    attachments = (
                        await session.execute(
                            select(StaffMessageAttachment).where(StaffMessageAttachment.message_id.in_(message_ids))
                        )
                    ).scalars().all()
                    for att in attachments:
                        attachments_map.setdefault(att.message_id, []).append(att)

                task_map: dict[int, StaffMessageTask] = {}
                candidate_map: dict[int, User] = {}
                if message_ids:
                    tasks = (
                        await session.execute(
                            select(StaffMessageTask).where(StaffMessageTask.message_id.in_(message_ids))
                        )
                    ).scalars().all()
                    for task in tasks:
                        task_map[task.message_id] = task
                    candidate_ids = [task.candidate_id for task in tasks]
                    if candidate_ids:
                        candidates = (
                            await session.execute(select(User).where(User.id.in_(candidate_ids)))
                        ).scalars().all()
                        candidate_map = {candidate.id: candidate for candidate in candidates}

                recruiter_ids = {m.principal_id for m in members if m.principal_type == "recruiter"}
                recruiter_ids.update(
                    msg.sender_id for msg in messages if msg.sender_type == "recruiter"
                )
                for candidate in candidate_map.values():
                    recruiter_id = getattr(candidate, "responsible_recruiter_id", None)
                    if recruiter_id:
                        recruiter_ids.add(recruiter_id)
                recruiter_map: dict[int, Recruiter] = {}
                if recruiter_ids:
                    recruiters = (
                        await session.execute(select(Recruiter).where(Recruiter.id.in_(recruiter_ids)))
                    ).scalars().all()
                    recruiter_map = {rec.id: rec for rec in recruiters}

                member_payload = [
                    _serialize_member(member, recruiter_map.get(member.principal_id))
                    for member in members
                ]
                payload_messages = [
                    _serialize_message(
                        msg,
                        attachments=attachments_map.get(msg.id, []),
                        task=task_map.get(msg.id),
                        candidate=candidate_map.get(task_map[msg.id].candidate_id) if msg.id in task_map else None,
                        recruiter_map=recruiter_map,
                        read_map=read_map,
                    )
                    for msg in messages
                ]
                return {
                    "messages": payload_messages,
                    "members": member_payload,
                    "latest_message_at": latest_message_at.isoformat() if latest_message_at else None,
                    "latest_activity_at": latest_activity_at.isoformat() if latest_activity_at else None,
                    "updated": True,
                }

        if datetime.now(timezone.utc) >= deadline:
            return {
                "messages": [],
                "members": [],
                "latest_message_at": latest_message_at.isoformat() if latest_message_at else None,
                "latest_activity_at": latest_activity_at.isoformat() if latest_activity_at else None,
                "updated": False,
            }
        await asyncio.sleep(1.0)


async def send_candidate_task(
    thread_id: int,
    principal: Principal,
    candidate_id: int,
    note: Optional[str] = None,
) -> dict:
    await _ensure_member(thread_id, principal)
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Кандидат не найден"})
        if principal.type == "recruiter" and user.responsible_recruiter_id != principal.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Кандидат не найден"})

        now = datetime.now(timezone.utc)
        msg = StaffMessage(
            thread_id=thread_id,
            sender_type=principal.type,
            sender_id=principal.id,
            message_type="candidate_task",
            text=note.strip() if note else None,
            created_at=now,
        )
        session.add(msg)
        await session.flush()
        task = StaffMessageTask(
            message_id=msg.id,
            candidate_id=user.id,
            status="pending",
            created_at=now,
        )
        session.add(task)
        await session.commit()

    return await get_message_payload(msg.id, principal)


async def decide_candidate_task(
    message_id: int,
    principal: Principal,
    decision: str,
    comment: Optional[str] = None,
) -> dict:
    if principal.type != "recruiter":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Недостаточно прав"})

    decision = (decision or "").strip().lower()
    if decision not in {"accepted", "declined"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Некорректное решение"})
    if decision == "declined" and not (comment or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Укажите причину отказа"})

    async with async_session() as session:
        msg = await session.get(StaffMessage, message_id)
        if not msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Сообщение не найдено"})
        member = await session.get(
            StaffThreadMember,
            (msg.thread_id, principal.type, principal.id),
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Чат не найден"})
        task = await session.get(StaffMessageTask, message_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Задача не найдена"})
        if task.status != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Задача уже обработана"})

        user = await session.get(User, task.candidate_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Кандидат не найден"})

        previous_recruiter = getattr(user, "responsible_recruiter_id", None)
        now = datetime.now(timezone.utc)
        if decision == "accepted":
            user.responsible_recruiter_id = principal.id

        task.status = decision
        task.decided_at = now
        task.decided_by_type = principal.type
        task.decided_by_id = principal.id
        task.decision_comment = comment.strip() if comment else None
        msg.edited_at = now
        candidate_id = task.candidate_id
        await session.commit()

    await log_audit_action(
        action="staff_candidate_task_" + decision,
        entity_type="candidate",
        entity_id=candidate_id,
        changes={
            "from_recruiter_id": previous_recruiter,
            "to_recruiter_id": principal.id if decision == "accepted" else previous_recruiter,
            "comment": comment.strip() if comment else None,
            "message_id": message_id,
        },
    )

    return await get_message_payload(message_id, principal)


async def mark_read(thread_id: int, principal: Principal) -> None:
    async with async_session() as session:
        members: list[StaffThreadMember] = []
        member = await session.get(
            StaffThreadMember,
            (thread_id, principal.type, principal.id),
        )
        if member:
            members.append(member)
        if principal.type == "admin":
            placeholder = await session.get(
                StaffThreadMember,
                (thread_id, "admin", -1),
            )
            if placeholder and placeholder not in members:
                members.append(placeholder)
        if not members:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Чат не найден"})
        now = datetime.now(timezone.utc)
        for member in members:
            member.last_read_at = now
        await session.commit()


async def get_attachment(attachment_id: int, principal: Principal) -> StaffMessageAttachment:
    async with async_session() as session:
        attachment = await session.get(StaffMessageAttachment, attachment_id)
        if not attachment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Файл не найден"})
        msg = await session.get(StaffMessage, attachment.message_id)
        if not msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Файл не найден"})
        member = await session.get(
            StaffThreadMember,
            (msg.thread_id, principal.type, principal.id),
        )
        if not member and principal.type == "admin":
            member = await session.get(
                StaffThreadMember,
                (msg.thread_id, "admin", -1),
            )
        if not member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Нет доступа"})
        session.expunge(attachment)
        return attachment
