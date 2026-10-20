from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import BatchStatus
from app.db.base import Base
from app.models.mixins import TimestampMixin


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, name="batch_status"), default=BatchStatus.ACTIVE, nullable=False
    )
    total_prospects: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_optional: Mapped[str | None] = mapped_column(nullable=True)

    icp_snapshot: Mapped["ICPSnapshot"] = relationship(
        back_populates="batch", uselist=False, cascade="all, delete-orphan"
    )
    prospects: Mapped[list["Prospect"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
