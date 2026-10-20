from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.enums import QualificationDecision
from app.models.enrichment import Phase1NormalizedData
from app.models.icp import ICPSnapshot


class QualificationProviderError(RuntimeError):
    """A technical Jev failure; never a substitute business decision."""

    def __init__(self, message: str, envelopes: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.envelopes = envelopes or []


@dataclass(slots=True)
class QualificationOutcome:
    decision: QualificationDecision
    person_fit: str | None
    company_fit: str | None
    exclusion_flags: list[str]
    reason: str
    confidence: str
    assessments: dict[str, Any]
    overall_fit_band: str
    confidence_band: str
    model_identifier: str | None
    provider_identifier: str
    usage_metadata: dict[str, Any]
    response_envelopes: list[dict[str, Any]] = field(default_factory=list)


class QualificationDecisionProvider(Protocol):
    provider_name: str

    async def decide(self, icp: ICPSnapshot, data: Phase1NormalizedData) -> QualificationOutcome: ...
