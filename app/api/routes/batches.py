from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.enums import ProspectState
from app.db.session import get_db
from app.models.batch import Batch
from app.schemas.batch import (
    BatchCreateRequest,
    BatchCreatedResponse,
    BatchStatusResponse,
    ProspectListItem,
)
from app.services.batch_service import (
    batch_status,
    create_batch,
    get_batch,
    list_batch_prospects,
    refresh_batch_status,
)
from app.services.review_service import bulk_action
from app.schemas.review import BulkReviewResponse

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("", response_model=BatchCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
def create(request: BatchCreateRequest, db: Session = Depends(get_db)) -> Batch:
    batch = create_batch(db, request)
    return batch


@router.get("/{batch_id}", response_model=BatchStatusResponse)
def read_status(batch_id: UUID, db: Session = Depends(get_db)) -> BatchStatusResponse:
    batch = get_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    return batch_status(batch)


@router.get("/{batch_id}/prospects", response_model=list[ProspectListItem])
def read_prospects(
    batch_id: UUID,
    state: ProspectState | None = Query(default=None),
    priority: str | None = Query(default=None, pattern="^P[123]$"),
    db: Session = Depends(get_db),
) -> list[ProspectListItem]:
    if get_batch(db, batch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    return list_batch_prospects(db, batch_id, state, priority)


@router.post("/{batch_id}/human-review/approve-all", response_model=BulkReviewResponse)
def approve_all(batch_id: UUID, db: Session = Depends(get_db)) -> BulkReviewResponse:
    if get_batch(db, batch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    prospect_ids = bulk_action(db, batch_id, "approve")
    batch = get_batch(db, batch_id)
    if batch:
        refresh_batch_status(db, batch)
    db.commit()
    return BulkReviewResponse(updated_count=len(prospect_ids))


@router.post("/{batch_id}/human-review/reject-all", response_model=BulkReviewResponse)
def reject_all(batch_id: UUID, db: Session = Depends(get_db)) -> BulkReviewResponse:
    if get_batch(db, batch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    prospect_ids = bulk_action(db, batch_id, "reject")
    batch = get_batch(db, batch_id)
    if batch:
        refresh_batch_status(db, batch)
    db.commit()
    return BulkReviewResponse(updated_count=len(prospect_ids))
