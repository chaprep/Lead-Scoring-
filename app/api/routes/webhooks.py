import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.models.contact import ContactEnrichmentRequest, ContactCallbackReceipt
from app.services.contacts import validate_payload

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/signalhire/{token}", status_code=200)
async def signalhire_callback(token: str, request: Request, db: Session = Depends(get_db)):
    enrichment = db.scalar(
        select(ContactEnrichmentRequest).where(
            ContactEnrichmentRequest.callback_token_hash
            == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    if enrichment is None:
        raise HTTPException(404, "Unknown callback.")
    try:
        payload = validate_payload(await request.json(), enrichment.prospect.linkedin_url)
        supplied_id = request.headers.get("Request-Id")
        if supplied_id is not None and (not supplied_id.strip() or len(supplied_id) > 255):
            raise ValueError("Invalid Request-Id.")
        if (
            supplied_id
            and enrichment.provider_request_id
            and supplied_id != enrichment.provider_request_id
        ):
            raise ValueError("Request-Id does not match the submission.")
    except (ValueError, TypeError) as error:
        raise HTTPException(422, "Malformed callback payload or request identifier.") from error
    digest = hashlib.sha256(
        json.dumps(
            {"payload": payload, "provider_request_id": supplied_id},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    db.add(
        ContactCallbackReceipt(
            request_id=enrichment.id,
            provider_request_id=supplied_id,
            payload_hash=digest,
            payload=payload,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if (
            db.scalar(
                select(ContactCallbackReceipt.id).where(
                    ContactCallbackReceipt.request_id == enrichment.id,
                    ContactCallbackReceipt.payload_hash == digest,
                )
            )
            is None
        ):
            raise
    return {"accepted": True}
