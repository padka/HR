from __future__ import annotations

from datetime import UTC, datetime

from backend.domain.base import Base
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class SimulatorRun(Base):
    __tablename__ = "simulator_runs"
    __table_args__ = (
        Index("ix_simulator_runs_status_started", "status", "started_at"),
        Index("ix_simulator_runs_created_by", "created_by_type", "created_by_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_type: Mapped[str] = mapped_column(String(16), nullable=False, default="admin")
    created_by_id: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)

    steps: Mapped[list[SimulatorStep]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SimulatorStep.step_order.asc()",
    )


class SimulatorStep(Base):
    __tablename__ = "simulator_steps"
    __table_args__ = (
        Index("ix_simulator_steps_run_order", "run_id", "step_order"),
        Index("ix_simulator_steps_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulator_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    run: Mapped[SimulatorRun] = relationship(back_populates="steps")
