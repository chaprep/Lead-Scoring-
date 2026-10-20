from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.core.enums import ProspectState, StageStatus
from app.db.session import get_db
from app.models.stage_run import StageRun
from app.schemas.batch import ProspectListItem
from app.schemas.prospect import ProspectDetailResponse
from app.services.batch_service import list_batch_prospects, refresh_batch_status
from app.services.prospect_service import get_prospect, prospect_detail
from app.services.review_service import InvalidReviewAction, approve, override_rejection, reject
from app.pipeline.ledger import enqueue, lock_batch
from app.pipeline.transitions import retry_target
from pydantic import BaseModel


class RetryRequest(BaseModel):
    acknowledge_possible_duplicate_charge: bool = False


router = APIRouter(prefix="/prospects", tags=["prospects"])


@router.get("/{prospect_id}", response_model=ProspectDetailResponse)
def read_detail(prospect_id: UUID, db: Session = Depends(get_db)) -> ProspectDetailResponse:
    prospect = get_prospect(db, prospect_id)
    if prospect is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prospect not found.")
    return prospect_detail(prospect)


def _review(prospect_id: UUID, action: str, db: Session) -> None:
    prospect = get_prospect(db, prospect_id)
    if prospect is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prospect not found.")
    try:
        {"approve": approve, "reject": reject, "override": override_rejection}[action](db, prospect)
        refresh_batch_status(db, prospect.batch)
        db.commit()
    except InvalidReviewAction as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/{prospect_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
def approve_review(prospect_id: UUID, db: Session = Depends(get_db)) -> None:
    _review(prospect_id, "approve", db)


@router.post("/{prospect_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_review(prospect_id: UUID, db: Session = Depends(get_db)) -> None:
    _review(prospect_id, "reject", db)


@router.post("/{prospect_id}/override", status_code=status.HTTP_204_NO_CONTENT)
def override(prospect_id: UUID, db: Session = Depends(get_db)) -> None:
    _review(prospect_id, "override", db)


@router.post(
    "/{prospect_id}/retry", response_model=ProspectListItem, status_code=status.HTTP_202_ACCEPTED
)
def retry(
    prospect_id: UUID, body: RetryRequest | None = None, db: Session = Depends(get_db)
) -> ProspectListItem:
    prospect = get_prospect(db, prospect_id)
    if prospect is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prospect not found.")
    lock_batch(db, prospect)
    if prospect.current_state is not ProspectState.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Only failed prospects can be retried."
        )

    failed_run = db.scalar(
        select(StageRun)
        .where(StageRun.prospect_id == prospect.id, StageRun.status == StageStatus.FAILED)
        .order_by(StageRun.started_at.desc())
    )
    if failed_run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No failed stage could be identified."
        )

    if failed_run.retry_requires_confirmation and not (
        body and body.acknowledge_possible_duplicate_charge
    ):
        raise HTTPException(
            409,
            "The provider outcome is unknown. Acknowledge possible duplicate charges before retrying.",
        )
    enqueue(db, prospect, failed_run.stage, previous=failed_run)
    prospect.current_state = retry_target(failed_run.stage)
    refresh_batch_status(db, prospect.batch)
    db.commit()

    return next(
        item for item in list_batch_prospects(db, prospect.batch_id) if item.id == prospect.id
    )
