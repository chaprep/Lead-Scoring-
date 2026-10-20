from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ICPSnapshot(TimestampMixin, Base):
    __tablename__ = "icp_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), unique=True)
    company_size_min: Mapped[int | None] = mapped_column(nullable=True)
    company_size_max: Mapped[int | None] = mapped_column(nullable=True)
    industries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    company_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    departments: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    seniorities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    geographies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    exclusions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    batch: Mapped["Batch"] = relationship(back_populates="icp_snapshot")
