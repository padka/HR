from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import List
from urllib.parse import urlparse

from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus

DEFAULT_CITIES: List[str] = [
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Новосибирск",
    "Екатеринбург",
    "Самара",
    "Удалённо",
]


def _guard_environment() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise SystemExit("Refusing to seed data in production.")
    parsed = urlparse(settings.database_url_async.replace("+asyncpg", "", 1))
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1"}:
        raise SystemExit(
            f"Refusing to seed data on non-local database host: {host or 'unknown'}"
        )


async def _seed(count: int) -> None:
    _guard_environment()
    now = datetime.now(timezone.utc)
    users: List[User] = []

    for idx in range(1, count + 1):
        is_stalled = (idx % 5 == 0)  # ~20% в статусе stalled_waiting_slot
        status = CandidateStatus.STALLED_WAITING_SLOT if is_stalled else CandidateStatus.WAITING_SLOT
        wait_hours = random.randint(2, 72) if not is_stalled else random.randint(30, 120)
        status_changed_at = now - timedelta(hours=wait_hours)

        user = User(
            fio=f"Входящий {idx:03d}",
            city=random.choice(DEFAULT_CITIES),
            candidate_status=status,
            status_changed_at=status_changed_at,
            manual_slot_requested_at=status_changed_at,
            manual_slot_comment="Ожидает слота",
            last_activity=status_changed_at,
            source="seed_incoming",
        )
        users.append(user)

    async with async_session() as session:
        session.add_all(users)
        await session.commit()

    print(f"Seeded {len(users)} incoming candidates.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed incoming (waiting) candidates for dashboard.")
    parser.add_argument("--count", type=int, default=100, help="How many candidates to create (default: 100)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    asyncio.run(_seed(args.count))


if __name__ == "__main__":
    main()
