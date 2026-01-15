"""
Utility to seed demo candidates that are waiting for slot assignment.

Run in dev/test environments only:
    python scripts/generate_waiting_candidates.py --count 6
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from itertools import cycle
from typing import Iterable

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.core.db import async_session  # noqa: E402
from backend.domain.candidates.models import User  # noqa: E402
from backend.domain.candidates.services import create_or_update_user  # noqa: E402
from backend.domain.candidates.status import CandidateStatus  # noqa: E402


Profile = dict[str, object]


PROFILES: list[Profile] = [
    {
        "name": "Анна Кузнецова",
        "city": "Москва",
        "username": "anna.waiting",
        "comment": "Готова с 10 до 18, просьба дать слот утром",
        "wait_hours": 5,
        "stalled": False,
        "tz": "Europe/Moscow",
    },
    {
        "name": "Дмитрий Орлов",
        "city": "Казань",
        "username": "d.orlov",
        "comment": "Можно только после 15:00, рабочие дни",
        "wait_hours": 28,
        "stalled": True,
        "tz": "Europe/Moscow",
    },
    {
        "name": "Екатерина Полякова",
        "city": "Новосибирск",
        "username": "katya.poly",
        "comment": "Предпочтительно онлайн, время 12-16 местного",
        "wait_hours": 14,
        "stalled": False,
        "tz": "Asia/Novosibirsk",
    },
    {
        "name": "Алексей Власов",
        "city": "Санкт-Петербург",
        "username": "avlasov",
        "comment": "Можно сегодня вечером или завтра утром",
        "wait_hours": 7,
        "stalled": False,
        "tz": "Europe/Moscow",
    },
    {
        "name": "Мария Громова",
        "city": "Екатеринбург",
        "username": "m.gromova",
        "comment": "Доступна после 19:00, просьба предупредить заранее",
        "wait_hours": 36,
        "stalled": True,
        "tz": "Asia/Yekaterinburg",
    },
    {
        "name": "Сергей Смирнов",
        "city": "Минск",
        "username": "sergey.sm",
        "comment": "Любое время с 9 до 17 (UTC+3)",
        "wait_hours": 10,
        "stalled": False,
        "tz": "Europe/Minsk",
    },
]


async def _apply_status(
    user: User, *, comment: str, tz: str, wait_hours: int, stalled: bool
) -> None:
    """Update candidate to waiting/stalled state with availability note."""
    async with async_session() as session:
        db_user = await session.get(User, user.id)
        if not db_user:
            return
        now = datetime.now(timezone.utc)
        db_user.candidate_status = (
            CandidateStatus.STALLED_WAITING_SLOT if stalled else CandidateStatus.WAITING_SLOT
        )
        db_user.status_changed_at = now - timedelta(hours=wait_hours)
        db_user.manual_slot_requested_at = db_user.status_changed_at
        db_user.manual_slot_from = now + timedelta(hours=6)
        db_user.manual_slot_to = now + timedelta(hours=36)
        db_user.manual_slot_comment = comment
        db_user.manual_slot_timezone = tz
        await session.commit()


async def generate_waiting_candidates(count: int) -> list[User]:
    """Create demo candidates waiting for slot assignment."""
    created: list[User] = []
    profile_iter: Iterable[Profile] = cycle(PROFILES)
    base_telegram = 980000000  # large offset to avoid collisions with real TG IDs

    for idx in range(count):
        profile = next(profile_iter)
        telegram_id = base_telegram + idx + 1
        user = await create_or_update_user(
            telegram_id=telegram_id,
            fio=str(profile["name"]),
            city=str(profile["city"]),
            username=str(profile["username"]),
            initial_status=CandidateStatus.WAITING_SLOT,
        )
        await _apply_status(
            user,
            comment=str(profile["comment"]),
            tz=str(profile["tz"]),
            wait_hours=int(profile["wait_hours"]),
            stalled=bool(profile["stalled"]),
        )
        created.append(user)
    return created


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate demo candidates waiting for slot assignment (incoming list)."
    )
    parser.add_argument("--count", type=int, default=6, help="How many candidates to create (default: 6)")
    args = parser.parse_args()

    created = await generate_waiting_candidates(max(1, args.count))
    print(f"Created/updated {len(created)} candidates in WAITING_SLOT / STALLED_WAITING_SLOT.")


if __name__ == "__main__":
    asyncio.run(main())
