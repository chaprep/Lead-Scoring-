from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_internal_api_key
from app.db.session import get_db
from app.models.contact import ContactEnrichmentRequest
from app.schemas.contact import InternalContactDetailResponse


router = APIRouter(prefix="/internal/prospects", tags=["internal contacts"])


@router.get("/{prospect_id}/contact", response_model=InternalContactDetailResponse)
def read_contact(
    prospect_id: UUID,
    _: None = Depends(require_internal_api_key),
    db: Session = Depends(get_db),
) -> InternalContactDetailResponse:
    enrichment = db.scalar(
        select(ContactEnrichmentRequest)
        .where(ContactEnrichmentRequest.prospect_id == prospect_id)
        .order_by(ContactEnrichmentRequest.created_at.desc(), ContactEnrichmentRequest.id.desc())
    )
    if enrichment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact enrichment not found."
        )
    if enrichment.normalized_contact_data is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact enrichment has not returned usable contact data.",
        )
    return InternalContactDetailResponse(
        prospect_id=prospect_id,
        provider=enrichment.provider,
        provider_request_id=enrichment.provider_request_id,
        status=enrichment.status,
        data=enrichment.normalized_contact_data,
    )
