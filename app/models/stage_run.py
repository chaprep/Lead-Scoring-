from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func, JSON, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import StageName, StageStatus
from app.db.base import Base


class StageRun(Base):
    __tablename__ = "stage_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prospect_id: Mapped[UUID] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[StageName] = mapped_column(Enum(StageName, name="stage_name"), nullable=False)
    status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus, name="stage_status"), default=StageStatus.QUEUED, nullable=False
    )
    provider: Mapped[str | None] = mapped_column(nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_type: Mapped[str | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(nullable=True)

    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publication_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    publication_error: Mapped[str | None]
    owner: Mapped[str | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_call_status: Mapped[str] = mapped_column(
        default="NOT_STARTED", server_default="NOT_STARTED"
    )
    failure_code: Mapped[str | None]
    retryable: Mapped[bool] = mapped_column(default=False, server_default="false")
    retry_requires_confirmation: Mapped[bool] = mapped_column(default=False, server_default="false")
    automatic_retries: Mapped[int] = mapped_column(default=0, server_default="0")
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    reservations: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    reservation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_stage_runs_active_prospect",
            "prospect_id",
            unique=True,
            postgresql_where=text("status IN ('QUEUED', 'PROCESSING')"),
            sqlite_where=text("status IN ('QUEUED', 'PROCESSING')"),
        ),
    )

    prospect: Mapped["Prospect"] = relationship(back_populates="stage_runs")
