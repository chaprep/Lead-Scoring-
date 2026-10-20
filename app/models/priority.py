from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import PriorityLevel
from app.db.base import Base
from app.models.mixins import TimestampMixin


class PriorityResult(TimestampMixin, Base):
    __tablename__ = "priority_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prospect_id: Mapped[UUID] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), unique=True
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel, name="priority_level", create_type=False), nullable=False
    )
    confidence: Mapped[str] = mapped_column(nullable=False)
    positive_signals: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    negative_or_weak_signals: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reason: Mapped[str] = mapped_column(nullable=False)
    summary: Mapped[str] = mapped_column(nullable=False)
    criteria_assessments: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    model_identifier: Mapped[str | None] = mapped_column(nullable=True)
    provider_identifier: Mapped[str | None] = mapped_column(nullable=True)
    usage_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    prospect: Mapped["Prospect"] = relationship(back_populates="priority_result")
