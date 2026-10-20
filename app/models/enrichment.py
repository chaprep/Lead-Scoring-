from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class RawProviderResponse(Base):
    __tablename__ = "raw_provider_responses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prospect_id: Mapped[UUID] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), index=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    prospect: Mapped["Prospect"] = relationship(back_populates="raw_responses")


class Phase1NormalizedData(TimestampMixin, Base):
    __tablename__ = "phase1_normalized_data"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prospect_id: Mapped[UUID] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str | None] = mapped_column(nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(nullable=True)
    job_title: Mapped[str | None] = mapped_column(nullable=True)
    current_role: Mapped[str | None] = mapped_column(nullable=True)
    department: Mapped[str | None] = mapped_column(nullable=True)
    location: Mapped[str | None] = mapped_column(nullable=True)
    current_company: Mapped[str | None] = mapped_column(nullable=True)
    company_name: Mapped[str | None] = mapped_column(nullable=True)
    company_domain: Mapped[str | None] = mapped_column(nullable=True)
    industry: Mapped[str | None] = mapped_column(nullable=True)
    company_type: Mapped[str | None] = mapped_column(nullable=True)
    employee_count: Mapped[int | None] = mapped_column(nullable=True)
    employee_count_min: Mapped[int | None] = mapped_column(nullable=True)
    employee_count_max: Mapped[int | None] = mapped_column(nullable=True)
    hq_location: Mapped[str | None] = mapped_column(nullable=True)
    company_description: Mapped[str | None] = mapped_column(nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    professional_summary: Mapped[str | None] = mapped_column(nullable=True)
    education: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    open_to_work: Mapped[bool | None] = mapped_column(nullable=True)
    person_follower_count: Mapped[int | None] = mapped_column(nullable=True)
    company_tagline: Mapped[str | None] = mapped_column(nullable=True)
    company_specialities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    company_founded_year: Mapped[int | None] = mapped_column(nullable=True)
    company_follower_count: Mapped[int | None] = mapped_column(nullable=True)

    prospect: Mapped["Prospect"] = relationship(back_populates="phase1_data")


class Phase2NormalizedData(TimestampMixin, Base):
    __tablename__ = "phase2_normalized_data"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prospect_id: Mapped[UUID] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), unique=True
    )
    signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    prospect: Mapped["Prospect"] = relationship(back_populates="phase2_data")
