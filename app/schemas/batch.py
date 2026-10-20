from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator
from urllib.parse import urlsplit, unquote
import re

from app.core.enums import (
    BatchStatus,
    PriorityLevel,
    ProspectState,
    QualificationDecision,
    StageName,
    StageStatus,
)


class ICPSnapshotInput(BaseModel):
    company_size_min: int | None = Field(default=None, ge=1)
    company_size_max: int | None = Field(default=None, ge=1)
    industries: list[str] = Field(default_factory=list)
    company_types: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    seniorities: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_range(self):
        if (
            self.company_size_min
            and self.company_size_max
            and self.company_size_max < self.company_size_min
        ):
            raise ValueError("Company size maximum must be at least the minimum.")
        return self

    @field_validator(
        "industries", "company_types", "departments", "seniorities", "geographies", "exclusions"
    )
    @classmethod
    def valid_entries(cls, values):
        if len(values) > 50 or any(
            not value.strip() or len(value.strip()) > 500 for value in values
        ):
            raise ValueError(
                "Each ICP list accepts at most 50 nonblank entries of at most 500 characters."
            )
        return [value.strip() for value in values]


class ProspectInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    linkedin_url: str = Field(min_length=1, max_length=2048)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("linkedin_url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname
            not in {"linkedin.com", "www.linkedin.com", "uk.linkedin.com", "in.linkedin.com"}
            or parsed.username is not None
            or parsed.password is not None
            or ":" in parsed.netloc
            or not re.fullmatch(r"/in/[^/]+/?", parsed.path)
            or any(c.isspace() for c in unquote(parsed.path))
            or "%2f" in parsed.path.lower()
        ):
            raise ValueError(
                "Use a LinkedIn person URL such as https://www.linkedin.com/in/profile."
            )
        return "https://www.linkedin.com" + parsed.path.rstrip("/")


class BatchCreateRequest(BaseModel):
    icp: ICPSnapshotInput
    prospects: list[ProspectInput] = Field(min_length=1, max_length=250)


class BatchCreatedResponse(BaseModel):
    id: UUID
    status: BatchStatus
    total_prospects: int

    model_config = {"from_attributes": True}


class BatchStatusResponse(BaseModel):
    id: UUID
    status: BatchStatus
    total: int
    queued: int
    processing: int
    human_review: int
    rejected: int
    failed: int
    completed: int
    created_at: datetime
    updated_at: datetime


class ProspectListItem(BaseModel):
    id: UUID
    name: str
    linkedin_url: str
    current_state: ProspectState
    final_priority: PriorityLevel | None
    job_title: str | None = None
    company_name: str | None = None
    current_stage: StageName | None = None
    current_stage_status: StageStatus | None = None
    latest_error_message: str | None = None
    failure_code: str | None = None
    retryable: bool = False
    retry_requires_confirmation: bool = False
    contact_outcome: str | None = None
    qualification_decision: QualificationDecision | None = None
    qualification_reason: str | None = None
    qualification_confidence: str | None = None
    priority_reason: str | None = None
    priority_summary: str | None = None
    priority_confidence: str | None = None
    positive_signals: list[str] = Field(default_factory=list)
    negative_or_weak_signals: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}
