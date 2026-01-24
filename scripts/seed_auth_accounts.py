#!/usr/bin/env python
"""
Seed auth_accounts for admin and recruiters.

Usage:
  ADMIN_USERNAME=admin ADMIN_PASSWORD=changeme \
  RECRUITER_PASSWORD=recruiter123 \
  python scripts/seed_auth_accounts.py
"""
from __future__ import annotations

import asyncio
import os
from typing import Literal, Tuple

from sqlalchemy import select

from backend.core.db import async_session
from backend.core.passwords import hash_password
from backend.domain.auth_account import AuthAccount
from backend.domain.models import Recruiter

PrincipalType = Literal["admin", "recruiter"]


async def _upsert_account(
    username: str,
    raw_password: str,
    principal_type: PrincipalType,
    principal_id: int,
) -> str:
    password_hash = hash_password(raw_password)
    async with async_session() as session:
        existing = await session.scalar(
            select(AuthAccount).where(AuthAccount.username == username)
        )
        if existing:
            existing.password_hash = password_hash
            existing.principal_type = principal_type
            existing.principal_id = principal_id
            existing.is_active = True
            action = "updated"
        else:
            session.add(
                AuthAccount(
                    username=username,
                    password_hash=password_hash,
                    principal_type=principal_type,
                    principal_id=principal_id,
                    is_active=True,
                )
            )
            action = "created"
        await session.commit()
    return action


async def seed_admin() -> Tuple[str, str]:
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    principal_id = int(os.getenv("ADMIN_PRINCIPAL_ID", "0"))
    action = await _upsert_account(username, password, "admin", principal_id)
    return username, action


async def seed_recruiters() -> Tuple[int, int]:
    """Create recruiter accounts for all active recruiters."""
    default_password = os.getenv("RECRUITER_PASSWORD", "recruiter123")
    created = updated = 0
    async with async_session() as session:
        recruiters = await session.scalars(
            select(Recruiter).where(Recruiter.active.is_(True))
        )
        for rec in recruiters:
            username = getattr(rec, "email", None) or getattr(rec, "tg_chat_id", None)
            if not username:
                username = f"recruiter{rec.id}"
            action = await _upsert_account(
                str(username),
                default_password,
                "recruiter",
                rec.id,
            )
            if action == "created":
                created += 1
            else:
                updated += 1
    return created, updated


async def main() -> None:
    admin_username, admin_action = await seed_admin()
    created_rec, updated_rec = await seed_recruiters()
    print(
        f"[seed_auth_accounts] admin {admin_username}: {admin_action}; "
        f"recruiters created={created_rec}, updated={updated_rec}"
    )


if __name__ == "__main__":
    asyncio.run(main())
