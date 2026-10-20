from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ProspectState
from app.models.prospect import Prospect
from app.models.review_event import ReviewEvent
from app.pipeline.transitions import transition


class InvalidReviewAction(ValueError):
    pass


def _record(session: Session, prospect: Prospect, action: str) -> None:
    session.add(ReviewEvent(prospect_id=prospect.id, action=action))


def approve(session: Session, prospect: Prospect) -> None:
    from app.pipeline.ledger import lock_batch

    lock_batch(session, prospect)
    if prospect.current_state is not ProspectState.HUMAN_REVIEW:
        raise InvalidReviewAction("Only prospects in HUMAN_REVIEW can be approved.")
    transition(prospect, ProspectState.PHASE2_QUEUED)
    from app.pipeline.ledger import enqueue
    from app.core.enums import StageName

    enqueue(session, prospect, StageName.PHASE2_COMPANY_ENRICHMENT)
    _record(session, prospect, "HUMAN_REVIEW_APPROVED")


def reject(session: Session, prospect: Prospect) -> None:
    from app.pipeline.ledger import lock_batch

    lock_batch(session, prospect)
    if prospect.current_state is not ProspectState.HUMAN_REVIEW:
        raise InvalidReviewAction("Only prospects in HUMAN_REVIEW can be rejected.")
    transition(prospect, ProspectState.REJECTED)
    _record(session, prospect, "HUMAN_REVIEW_REJECTED")


def override_rejection(session: Session, prospect: Prospect) -> None:
    from app.pipeline.ledger import lock_batch

    lock_batch(session, prospect)
    if prospect.current_state is not ProspectState.REJECTED:
        raise InvalidReviewAction("Only rejected prospects can be manually overridden.")
    transition(prospect, ProspectState.PHASE2_QUEUED)
    from app.pipeline.ledger import enqueue
    from app.core.enums import StageName

    enqueue(session, prospect, StageName.PHASE2_COMPANY_ENRICHMENT)
    _record(session, prospect, "REJECTION_OVERRIDDEN")


def bulk_action(session: Session, batch_id: UUID, action: str) -> list[UUID]:
    from app.models.batch import Batch

    session.scalar(select(Batch).where(Batch.id == batch_id).with_for_update())
    prospects = list(
        session.scalars(
            select(Prospect).where(
                Prospect.batch_id == batch_id, Prospect.current_state == ProspectState.HUMAN_REVIEW
            )
        )
    )
    for prospect in prospects:
        approve(session, prospect) if action == "approve" else reject(session, prospect)
    return [prospect.id for prospect in prospects]
