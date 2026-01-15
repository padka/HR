from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus

DEFAULT_CITIES = [
    "Moscow",
    "Saint Petersburg",
    "Kazan",
    "Novosibirsk",
    "Yekaterinburg",
    "Samara",
    "Remote",
]

STATUS_POOL = [
    CandidateStatus.LEAD,
    CandidateStatus.CONTACTED,
    CandidateStatus.INVITED,
    CandidateStatus.TEST1_COMPLETED,
    CandidateStatus.WAITING_SLOT,
    CandidateStatus.STALLED_WAITING_SLOT,
    CandidateStatus.INTERVIEW_SCHEDULED,
    CandidateStatus.INTERVIEW_CONFIRMED,
    CandidateStatus.INTERVIEW_DECLINED,
    CandidateStatus.TEST2_SENT,
    CandidateStatus.TEST2_COMPLETED,
    CandidateStatus.TEST2_FAILED,
    CandidateStatus.INTRO_DAY_SCHEDULED,
    CandidateStatus.HIRED,
    CandidateStatus.NOT_HIRED,
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


def _resolve_status(value: str, *, randomize: bool) -> Optional[CandidateStatus]:
    if randomize:
        return random.choice(STATUS_POOL)
    if not value or value.lower() == "none":
        return None
    normalized = value.strip().lower()
    for status in CandidateStatus:
        if status.value == normalized:
            return status
    raise SystemExit(f"Unknown status: {value}")


async def _seed(
    *,
    count: int,
    prefix: str,
    source: str,
    status_value: str,
    random_status: bool,
) -> None:
    _guard_environment()
    now = datetime.now(timezone.utc)
    users: list[User] = []
    for idx in range(1, count + 1):
        status = _resolve_status(status_value, randomize=random_status)
        last_activity = now - timedelta(
            days=random.randint(0, 30),
            seconds=random.randint(0, 24 * 3600),
        )
        users.append(
            User(
                fio=f"{prefix} {idx:04d}",
                city=random.choice(DEFAULT_CITIES),
                source=source,
                candidate_status=status,
                status_changed_at=last_activity if status else None,
                last_activity=last_activity,
            )
        )

    async with async_session() as session:
        session.add_all(users)
        await session.commit()

    print(f"Inserted {len(users)} test users.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed test users into the database.")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--prefix", default="Load Test User")
    parser.add_argument("--source", default="seed")
    parser.add_argument("--status", default="lead")
    parser.add_argument("--random-status", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    asyncio.run(
        _seed(
            count=args.count,
            prefix=args.prefix,
            source=args.source,
            status_value=args.status,
            random_status=args.random_status,
        )
    )


if __name__ == "__main__":
    main()
