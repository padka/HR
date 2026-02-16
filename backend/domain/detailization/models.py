from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.base import Base


class DetailizationEntry(Base):
    """
    Persistent reporting row for candidates who reached the intro day stage.

    Goal:
    - Auto-create rows from intro_day slot assignments / slots
    - Allow recruiters/admins to fill missing fields manually
    - Keep reporting stable even when operational entities are cleaned up
      (e.g. candidate slot links released after NOT_HIRED).
    """

    __tablename__ = "detailization_entries"
    __table_args__ = (
        UniqueConstraint("slot_assignment_id", name="uq_detailization_slot_assignment"),
        Index("ix_detailization_entries_conducted_at", "conducted_at"),
        Index(
            "ix_detailization_entries_recruiter_conducted_at",
            "recruiter_id",
            "conducted_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    slot_assignment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("slot_assignments.id", ondelete="SET NULL"),
        nullable=True,
    )
    slot_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("slots.id", ondelete="SET NULL"),
        nullable=True,
    )

    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recruiter_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("recruiters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    city_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("cities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conducted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Manual fields
    expert_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    column_9: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_attached: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    created_by_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="system"
    )
    created_by_id: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Optional relationships (kept as string refs to avoid import cycles)
    candidate = relationship("User")
    recruiter = relationship("Recruiter")
    city = relationship("City")
    slot = relationship("Slot")
    slot_assignment = relationship("SlotAssignment")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            f"<DetailizationEntry {self.id} candidate={self.candidate_id} "
            f"slot_assignment={self.slot_assignment_id} conducted_at={self.conducted_at}>"
        )

