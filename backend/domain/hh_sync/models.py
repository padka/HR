"""SQLAlchemy ORM model for hh_sync_log table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.base import Base


class HHSyncLog(Base):
    """Audit log for hh.ru synchronization events."""

    __tablename__ = "hh_sync_log"
    __table_args__ = (
        Index("ix_hh_sync_log_candidate", "candidate_id", "created_at"),
        Index("ix_hh_sync_log_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rs_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hh_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            f"<HHSyncLog {self.id} candidate={self.candidate_id} "
            f"type={self.event_type} status={self.status}>"
        )
