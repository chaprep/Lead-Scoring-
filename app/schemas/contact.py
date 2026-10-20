from typing import Any
from uuid import UUID

from pydantic import BaseModel


class InternalContactDetailResponse(BaseModel):
    prospect_id: UUID
    provider: str
    provider_request_id: str | None
    status: str
    data: dict[str, Any]
