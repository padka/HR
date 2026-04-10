from __future__ import annotations

from dataclasses import dataclass
import hashlib

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.candidates.models import User


def normalize_max_user_id(value: str | None) -> str:
    return str(value or "").strip()


def max_user_id_fingerprint(max_user_id: str | None) -> str | None:
    normalized = normalize_max_user_id(max_user_id)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _max_user_id_lock_key(max_user_id: str) -> int:
    normalized = normalize_max_user_id(max_user_id)
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


@dataclass(frozen=True)
class MaxOwnershipSnapshot:
    max_user_id: str | None
    owners: tuple[User, ...]

    @property
    def linked(self) -> bool:
        return bool(self.max_user_id)

    @property
    def owner_count(self) -> int:
        return len(self.owners)

    @property
    def status(self) -> str:
        if not self.max_user_id:
            return "unlinked"
        if not self.owners:
            return "unclaimed"
        if len(self.owners) == 1:
            return "owned"
        return "ambiguous"

    @property
    def primary_owner(self) -> User | None:
        if len(self.owners) != 1:
            return None
        return self.owners[0]

    @property
    def owner_candidate_ids(self) -> tuple[int, ...]:
        return tuple(int(owner.id) for owner in self.owners)

    def is_owned_by(self, candidate_id: int | None) -> bool:
        if candidate_id is None or len(self.owners) != 1:
            return False
        return int(self.owners[0].id) == int(candidate_id)

    def owner_candidate_id(self, *, exclude_candidate_id: int | None = None) -> int | None:
        owner = self.primary_owner
        if owner is None:
            return None
        owner_id = int(owner.id)
        if exclude_candidate_id is not None and owner_id == int(exclude_candidate_id):
            return None
        return owner_id


async def acquire_max_user_id_claim_lock(session: AsyncSession, max_user_id: str | None) -> None:
    normalized = normalize_max_user_id(max_user_id)
    if not normalized:
        return
    bind = session.get_bind()
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "")).strip().lower()
    if dialect_name != "postgresql":
        return
    await session.execute(select(func.pg_advisory_xact_lock(_max_user_id_lock_key(normalized))))


async def inspect_max_user_ownership(
    session: AsyncSession,
    max_user_id: str | None,
) -> MaxOwnershipSnapshot:
    normalized = normalize_max_user_id(max_user_id)
    if not normalized:
        return MaxOwnershipSnapshot(max_user_id=None, owners=())
    owners = tuple(
        (
            await session.scalars(
                select(User)
                .where(func.trim(User.max_user_id) == normalized)
                .order_by(User.id.asc())
            )
        ).all()
    )
    return MaxOwnershipSnapshot(max_user_id=normalized, owners=owners)
