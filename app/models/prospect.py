from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import PriorityLevel, ProspectState
from app.db.base import Base
from app.models.mixins import TimestampMixin


class Prospect(TimestampMixin, Base):
    __tablename__ = "prospects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    linkedin_url: Mapped[str] = mapped_column(nullable=False)
    current_state: Mapped[ProspectState] = mapped_column(
        Enum(ProspectState, name="prospect_state"),
        default=ProspectState.CREATED,
        nullable=False,
        index=True,
    )
    final_priority: Mapped[PriorityLevel | None] = mapped_column(
        Enum(PriorityLevel, name="priority_level"), nullable=True, index=True
    )

    batch: Mapped["Batch"] = relationship(back_populates="prospects")
    stage_runs: Mapped[list["StageRun"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan", order_by="StageRun.started_at"
    )
    raw_responses: Mapped[list["RawProviderResponse"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )
    phase1_data: Mapped["Phase1NormalizedData | None"] = relationship(
        back_populates="prospect", uselist=False, cascade="all, delete-orphan"
    )
    qualification: Mapped["QualificationResult | None"] = relationship(
        back_populates="prospect", uselist=False, cascade="all, delete-orphan"
    )
    phase2_data: Mapped["Phase2NormalizedData | None"] = relationship(
        back_populates="prospect", uselist=False, cascade="all, delete-orphan"
    )
    priority_result: Mapped["PriorityResult | None"] = relationship(
        back_populates="prospect", uselist=False, cascade="all, delete-orphan"
    )
    review_events: Mapped[list["ReviewEvent"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan", order_by="ReviewEvent.created_at"
    )
    contact_requests: Mapped[list["ContactEnrichmentRequest"]] = relationship(
        back_populates="prospect",
        cascade="all, delete-orphan",
        order_by="ContactEnrichmentRequest.created_at",
    )

    @property
    def contact_request(self):
        return self.contact_requests[-1] if self.contact_requests else None
