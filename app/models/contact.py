from __future__ import annotations

from uuid import UUID, uuid4

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ContactEnrichmentRequest(TimestampMixin, Base):
    __tablename__ = "contact_enrichment_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prospect_id: Mapped[UUID] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(nullable=False)
    callback_token_hash: Mapped[str] = mapped_column(nullable=False, unique=True)
    provider_request_id: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="PENDING")
    raw_callback_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    normalized_contact_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    stage_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("stage_runs.id"), unique=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None]

    prospect: Mapped["Prospect"] = relationship(back_populates="contact_requests")


class ContactCallbackReceipt(Base):
    __tablename__ = "contact_callback_receipts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("contact_enrichment_requests.id", ondelete="CASCADE"), index=True
    )
    provider_request_id: Mapped[str | None]
    payload_hash: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_error: Mapped[str | None]
    __table_args__ = (UniqueConstraint("request_id", "payload_hash"),)


class CoordinatorHeartbeat(Base):
    __tablename__ = "coordinator_heartbeat"
    id: Mapped[int] = mapped_column(primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
