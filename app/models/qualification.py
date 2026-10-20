from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import QualificationDecision
from app.db.base import Base
from app.models.mixins import TimestampMixin


class QualificationResult(TimestampMixin, Base):
    __tablename__ = "qualification_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prospect_id: Mapped[UUID] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), unique=True
    )
    decision: Mapped[QualificationDecision] = mapped_column(
        Enum(QualificationDecision, name="qualification_decision"), nullable=False
    )
    person_fit: Mapped[str | None] = mapped_column(nullable=True)
    company_fit: Mapped[str | None] = mapped_column(nullable=True)
    exclusion_flags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reason: Mapped[str] = mapped_column(nullable=False)
    confidence: Mapped[str] = mapped_column(nullable=False)
    assessments: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overall_fit_band: Mapped[str | None] = mapped_column(nullable=True)
    confidence_band: Mapped[str | None] = mapped_column(nullable=True)
    model_identifier: Mapped[str | None] = mapped_column(nullable=True)
    provider_identifier: Mapped[str | None] = mapped_column(nullable=True)
    usage_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    prospect: Mapped["Prospect"] = relationship(back_populates="qualification")
