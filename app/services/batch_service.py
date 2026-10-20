from collections import Counter
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload, object_session

from app.core.enums import BatchStatus, ProspectState
from app.models.batch import Batch
from app.models.icp import ICPSnapshot
from app.models.prospect import Prospect
from app.schemas.batch import BatchCreateRequest, BatchStatusResponse, ProspectListItem

QUEUED_STATES = {ProspectState.CREATED, ProspectState.PHASE1_QUEUED, ProspectState.PHASE2_QUEUED}
PROCESSING_STATES = {
    ProspectState.PHASE1_PROCESSING,
    ProspectState.PHASE1_NORMALISING,
    ProspectState.QUALIFYING,
    ProspectState.PHASE2_PROCESSING,
    ProspectState.PHASE2_NORMALISING,
    ProspectState.PRIORITISING,
    ProspectState.CONTACT_ENRICHMENT_PENDING,
    ProspectState.PASSED,
}
TERMINAL_STATES = {ProspectState.COMPLETED, ProspectState.REJECTED, ProspectState.FAILED}


def create_batch(session: Session, request: BatchCreateRequest) -> Batch:
    """Persist independent prospect workflows; task dispatch is added with pipeline orchestration."""
    icp_data = request.icp.model_dump()
    batch = Batch(total_prospects=len(request.prospects), icp_snapshot=ICPSnapshot(**icp_data))
    batch.prospects = [
        Prospect(
            name=prospect.name.strip(),
            linkedin_url=prospect.linkedin_url,
            current_state=ProspectState.PHASE1_QUEUED,
        )
        for prospect in request.prospects
    ]
    session.add(batch)
    session.flush()
    from app.pipeline.ledger import enqueue
    from app.core.enums import StageName

    for prospect in batch.prospects:
        enqueue(session, prospect, StageName.PHASE1_ENRICHMENT)
    session.commit()
    session.refresh(batch)
    return batch


def get_batch(session: Session, batch_id: UUID) -> Batch | None:
    return session.scalar(select(Batch).where(Batch.id == batch_id))


def refresh_batch_status(session: Session, batch: Batch) -> None:
    """Keep batch completion derived from its independent prospect workflows."""
    session.scalar(select(Batch).where(Batch.id == batch.id).with_for_update())
    session.flush()
    counts = _counts(session, batch.id)
    batch.status = _status(counts)


def _counts(session, batch_id):
    return Counter(
        dict(
            session.execute(
                select(Prospect.current_state, func.count())
                .where(Prospect.batch_id == batch_id)
                .group_by(Prospect.current_state)
            ).all()
        )
    )


def _status(counts):
    return (
        BatchStatus.COMPLETED
        if sum(counts.values()) and all(state in TERMINAL_STATES for state in counts)
        else BatchStatus.ACTIVE
    )


def batch_status(batch: Batch) -> BatchStatusResponse:
    session = object_session(batch)
    session.flush()
    counts = _counts(session, batch.id)
    return BatchStatusResponse(
        id=batch.id,
        status=_status(counts),
        total=sum(counts.values()),
        queued=sum(counts[state] for state in QUEUED_STATES),
        processing=sum(counts[state] for state in PROCESSING_STATES),
        human_review=counts[ProspectState.HUMAN_REVIEW],
        rejected=counts[ProspectState.REJECTED],
        failed=counts[ProspectState.FAILED],
        completed=counts[ProspectState.COMPLETED],
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def list_batch_prospects(
    session: Session,
    batch_id: UUID,
    state: ProspectState | None = None,
    priority: str | None = None,
) -> list[ProspectListItem]:
    statement = (
        select(Prospect)
        .where(Prospect.batch_id == batch_id)
        .options(
            selectinload(Prospect.phase1_data),
            selectinload(Prospect.qualification),
            selectinload(Prospect.priority_result),
            selectinload(Prospect.stage_runs),
        )
        .order_by(Prospect.created_at)
    )
    if state is not None:
        statement = statement.where(Prospect.current_state == state)
    if priority is not None:
        statement = statement.where(Prospect.final_priority == priority)
    items = []
    for prospect in session.scalars(statement):
        latest_run = max(prospect.stage_runs, key=lambda run: run.started_at, default=None)
        latest_failed_run = (
            latest_run if latest_run and latest_run.status.value == "FAILED" else None
        )
        qualification = prospect.qualification
        priority_result = prospect.priority_result
        items.append(
            ProspectListItem(
                id=prospect.id,
                name=prospect.name,
                linkedin_url=prospect.linkedin_url,
                current_state=prospect.current_state,
                final_priority=prospect.final_priority,
                job_title=prospect.phase1_data.job_title if prospect.phase1_data else None,
                company_name=prospect.phase1_data.company_name if prospect.phase1_data else None,
                current_stage=latest_run.stage if latest_run else None,
                current_stage_status=latest_run.status if latest_run else None,
                latest_error_message=latest_failed_run.error_message if latest_failed_run else None,
                failure_code=latest_failed_run.failure_code if latest_failed_run else None,
                retryable=bool(latest_failed_run and latest_failed_run.retryable),
                retry_requires_confirmation=bool(
                    latest_failed_run and latest_failed_run.retry_requires_confirmation
                ),
                contact_outcome=prospect.contact_request.outcome
                if prospect.contact_request
                else None,
                qualification_decision=qualification.decision if qualification else None,
                qualification_reason=qualification.reason if qualification else None,
                qualification_confidence=qualification.confidence if qualification else None,
                priority_reason=priority_result.reason if priority_result else None,
                priority_summary=priority_result.summary if priority_result else None,
                priority_confidence=priority_result.confidence if priority_result else None,
                positive_signals=priority_result.positive_signals if priority_result else [],
                negative_or_weak_signals=priority_result.negative_or_weak_signals
                if priority_result
                else [],
            )
        )
    return items
