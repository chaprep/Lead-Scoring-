from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import PriorityLevel, ProspectState, StageName, StageStatus


class StageRunResponse(BaseModel):
    id: UUID
    stage: StageName
    status: StageStatus
    provider: str | None
    attempt_number: int
    started_at: datetime
    finished_at: datetime | None
    error_type: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class RawResponseDetail(BaseModel):
    id: UUID
    phase: str
    provider: str
    payload: dict[str, Any]
    retrieved_at: datetime

    model_config = {"from_attributes": True}


class ProspectDetailResponse(BaseModel):
    id: UUID
    batch_id: UUID
    name: str
    linkedin_url: str
    current_state: ProspectState
    final_priority: PriorityLevel | None
    created_at: datetime
    updated_at: datetime
    failure_code: str | None = None
    retryable: bool = False
    retry_requires_confirmation: bool = False
    contact_outcome: str | None = None
    stage_history: list[StageRunResponse]
    raw_provider_responses: list[RawResponseDetail]
    phase1_normalized_data: dict[str, Any] | None = None
    qualification: dict[str, Any] | None = None
    phase2_normalized_data: dict[str, Any] | None = None
    priority_result: dict[str, Any] | None = None
