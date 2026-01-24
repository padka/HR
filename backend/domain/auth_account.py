from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.base import Base

PrincipalType = Literal["admin", "recruiter"]


class AuthAccount(Base):
    __tablename__ = "auth_accounts"
    __table_args__ = (
        UniqueConstraint("username", name="uq_auth_accounts_username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    principal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<AuthAccount {self.username} type={self.principal_type} pid={self.principal_id}>"

