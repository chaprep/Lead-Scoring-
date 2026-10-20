from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.prospect import Prospect
from app.schemas.prospect import ProspectDetailResponse, RawResponseDetail, StageRunResponse


def get_prospect(session: Session, prospect_id: UUID) -> Prospect | None:
    statement = (
        select(Prospect)
        .where(Prospect.id == prospect_id)
        .options(
            selectinload(Prospect.stage_runs),
            selectinload(Prospect.raw_responses),
            selectinload(Prospect.phase1_data),
            selectinload(Prospect.qualification),
            selectinload(Prospect.phase2_data),
            selectinload(Prospect.priority_result),
        )
    )
    return session.scalar(statement)


def _model_data(model: object | None, excluded: set[str]) -> dict[str, Any] | None:
    if model is None:
        return None
    return {
        column.name: getattr(model, column.name)
        for column in model.__table__.columns
        if column.name not in excluded
    }


def prospect_detail(prospect: Prospect) -> ProspectDetailResponse:
    raw_responses = []
    for item in prospect.raw_responses:
        if item.provider == "signalhire_callback":
            raw_responses.append(
                RawResponseDetail(
                    id=item.id,
                    phase=item.phase,
                    provider=item.provider,
                    payload={
                        "redacted": True,
                        "message": "SignalHire contact data is not exposed by this endpoint.",
                    },
                    retrieved_at=item.retrieved_at,
                )
            )
        else:
            raw_responses.append(RawResponseDetail.model_validate(item))
    latest = max(prospect.stage_runs, key=lambda r: r.started_at, default=None)
    failed = latest if latest and latest.status.value == "FAILED" else None
    return ProspectDetailResponse(
        id=prospect.id,
        batch_id=prospect.batch_id,
        name=prospect.name,
        linkedin_url=prospect.linkedin_url,
        current_state=prospect.current_state,
        final_priority=prospect.final_priority,
        created_at=prospect.created_at,
        updated_at=prospect.updated_at,
        failure_code=failed.failure_code if failed else None,
        retryable=bool(failed and failed.retryable),
        retry_requires_confirmation=bool(failed and failed.retry_requires_confirmation),
        contact_outcome=prospect.contact_request.outcome if prospect.contact_request else None,
        stage_history=[StageRunResponse.model_validate(item) for item in prospect.stage_runs],
        raw_provider_responses=raw_responses,
        phase1_normalized_data=_model_data(
            prospect.phase1_data, {"id", "prospect_id", "created_at", "updated_at"}
        ),
        qualification=_model_data(
            prospect.qualification, {"id", "prospect_id", "created_at", "updated_at"}
        ),
        phase2_normalized_data=_model_data(
            prospect.phase2_data, {"id", "prospect_id", "created_at", "updated_at"}
        ),
        priority_result=_model_data(
            prospect.priority_result, {"id", "prospect_id", "created_at", "updated_at"}
        ),
    )
