"""Validate receipts at the boundary and apply them under workflow locks."""

from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.core.enums import StageStatus, ProspectState
from app.models.contact import ContactEnrichmentRequest, ContactCallbackReceipt
from app.models.stage_run import StageRun
from app.pipeline.ledger import now, finish, lock_batch
from app.schemas.batch import ProspectInput
from app.services.contact_normalizer import normalize_signalhire_callback
from app.services.batch_service import refresh_batch_status


class Candidate(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    contacts: list[dict[str, Any]] = Field(default_factory=list)


class CallbackItem(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    item: str = Field(min_length=1)
    status: Literal["success", "failed", "credits_are_over", "timeout_exceeded", "duplicate_query"]
    candidate: Candidate | None = None

    @model_validator(mode="after")
    def success_candidate(self):
        if self.status == "success" and self.candidate is None:
            raise ValueError("Successful callbacks require a candidate object.")
        return self


def validate_payload(payload, linkedin_url):
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError("Expected exactly one callback item for this request.")
    item = CallbackItem.model_validate(items[0])
    canonical = ProspectInput(name="callback", linkedin_url=item.item).linkedin_url
    if canonical != ProspectInput(name="callback", linkedin_url=linkedin_url).linkedin_url:
        raise ValueError("Callback identifier does not match the request.")
    return {"items": [item.model_dump(exclude_none=True)]}


def apply_contact(db, request, run, payload):
    item = payload["items"][0]
    request.raw_callback_payload = payload
    normalized = normalize_signalhire_callback(payload)
    usable = normalized and any(
        c.get("type") in {"email", "phone"}
        and isinstance(c.get("value"), str)
        and c["value"].strip()
        for c in normalized["contacts"]
    )
    request.normalized_contact_data = normalized if usable else None
    request.status = "RECEIVED"
    request.outcome = (
        ("CONTACTS_FOUND" if usable else "NO_CONTACTS_FOUND")
        if item["status"] == "success"
        else item["status"].upper()
    )
    p = request.prospect
    latest = db.scalar(
        select(ContactEnrichmentRequest)
        .where(ContactEnrichmentRequest.prospect_id == p.id)
        .order_by(ContactEnrichmentRequest.created_at.desc(), ContactEnrichmentRequest.id.desc())
    )
    # A queued newer contact stage also supersedes this attempt before submission starts.
    newer = db.scalar(
        select(StageRun)
        .where(
            StageRun.prospect_id == p.id,
            StageRun.stage == run.stage,
            StageRun.attempt_number > run.attempt_number,
        )
        .limit(1)
    )
    if latest.id != request.id or newer is not None:
        return
    if item["status"] == "success":
        finish(run)
        run.failure_code = None
        run.error_type = None
        run.error_message = None
        run.retryable = False
        run.retry_requires_confirmation = False
        p.current_state = ProspectState.COMPLETED
    else:
        finish(run, StageStatus.FAILED)
        run.failure_code = request.outcome
        run.error_type = "ContactProviderFailure"
        run.error_message = (
            f"Contact provider reported {item['status']}. Check the provider before retrying."
        )
        run.retryable = True
        run.retry_requires_confirmation = item["status"] in {"timeout_exceeded", "duplicate_query"}
        p.current_state = ProspectState.FAILED


def process_receipts(db):
    ids = list(
        db.scalars(
            select(ContactCallbackReceipt.id).where(ContactCallbackReceipt.processed_at.is_(None))
        )
    )
    db.commit()
    for receipt_id in ids:
        receipt = db.get(ContactCallbackReceipt, receipt_id)
        request = db.get(ContactEnrichmentRequest, receipt.request_id)
        lock_batch(db, request.prospect)
        db.refresh(receipt, with_for_update=True)
        db.refresh(request)
        if receipt.processed_at:
            db.rollback()
            continue
        run = db.get(StageRun, request.stage_run_id)
        if (
            receipt.provider_request_id
            and request.provider_request_id
            and receipt.provider_request_id != request.provider_request_id
        ):
            receipt.processing_error = "REQUEST_ID_MISMATCH"
        elif run is None:
            receipt.processing_error = "LEGACY_ATTEMPT_WITHOUT_STAGE"
        elif request.status != "RECEIVED":
            if receipt.provider_request_id:
                request.provider_request_id = receipt.provider_request_id
            apply_contact(db, request, run, receipt.payload)
            refresh_batch_status(db, request.prospect.batch)
        receipt.processed_at = now()
        db.commit()


def expire_contacts(db):
    ids = list(
        db.scalars(
            select(ContactEnrichmentRequest.id).where(
                ContactEnrichmentRequest.status.in_(["PENDING", "SUBMITTED"]),
                ContactEnrichmentRequest.deadline < now(),
            )
        )
    )
    db.commit()
    for request_id in ids:
        request = db.get(ContactEnrichmentRequest, request_id)
        lock_batch(db, request.prospect)
        db.refresh(request)
        run = db.get(StageRun, request.stage_run_id) if request.stage_run_id else None
        if (
            request.status in {"PENDING", "SUBMITTED"}
            and run
            and run.status == StageStatus.PROCESSING
        ):
            request.status = "TIMED_OUT"
            request.outcome = "CALLBACK_TIMEOUT"
            finish(run, StageStatus.FAILED)
            run.failure_code = "CALLBACK_TIMEOUT"
            run.error_type = "CallbackTimeout"
            run.error_message = "No contact callback arrived before the deadline. Retrying may cause a duplicate charge."
            run.retryable = True
            run.retry_requires_confirmation = True
            request.prospect.current_state = ProspectState.FAILED
            refresh_batch_status(db, request.prospect.batch)
        db.commit()
