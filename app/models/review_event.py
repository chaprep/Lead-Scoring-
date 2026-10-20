from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewEvent(Base):
    __tablename__ = "review_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prospect_id: Mapped[UUID] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    prospect: Mapped["Prospect"] = relationship(back_populates="review_events")
