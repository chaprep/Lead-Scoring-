"""PostgreSQL is the work ledger; broker deliveries only invite a conditional claim."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import hashlib

from sqlalchemy import select, func, update, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import StageName, StageStatus, ProspectState
from app.models.stage_run import StageRun
from app.models.prospect import Prospect
from app.models.batch import Batch


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


STATES = {
    StageName.PHASE1_ENRICHMENT: ProspectState.PHASE1_PROCESSING,
    StageName.PHASE1_NORMALISATION: ProspectState.PHASE1_NORMALISING,
    StageName.QUALIFICATION: ProspectState.QUALIFYING,
    StageName.PHASE2_COMPANY_ENRICHMENT: ProspectState.PHASE2_PROCESSING,
    StageName.PHASE2_NORMALISATION: ProspectState.PHASE2_NORMALISING,
    StageName.PRIORITISATION: ProspectState.PRIORITISING,
    StageName.PHASE2_CONTACT_ENRICHMENT: ProspectState.CONTACT_ENRICHMENT_PENDING,
}


def lock_batch(db, prospect):
    # All workflow mutations use batch -> prospect -> stage lock order.
    db.scalar(select(Batch).where(Batch.id == prospect.batch_id).with_for_update())
    db.refresh(prospect, with_for_update=True)


def enqueue(
    db: Session, prospect: Prospect, stage: StageName, *, previous=None, delay=0, automatic=False
):
    attempt = (
        db.scalar(
            select(func.max(StageRun.attempt_number)).where(
                StageRun.prospect_id == prospect.id, StageRun.stage == stage
            )
        )
        or 0
    ) + 1
    run = StageRun(
        prospect_id=prospect.id,
        stage=stage,
        status=StageStatus.QUEUED,
        attempt_number=attempt,
        due_at=now() + timedelta(seconds=delay),
        checkpoint=(
            dict(previous.checkpoint or {})
            if previous and stage != StageName.PHASE2_CONTACT_ENRICHMENT
            else {}
        ),
        automatic_retries=(previous.automatic_retries + 1 if automatic else 0) if previous else 0,
    )
    db.add(run)
    return run


def buckets(stage):
    s = get_settings()
    phase = (
        "phase1"
        if stage
        in {StageName.PHASE1_ENRICHMENT, StageName.PHASE1_NORMALISATION, StageName.QUALIFICATION}
        else "phase2"
    )
    result = {phase: s.phase1_max_concurrency if phase == "phase1" else s.phase2_max_concurrency}
    if stage in {StageName.QUALIFICATION, StageName.PRIORITISATION}:
        result["llm"] = s.llm_max_concurrency
    if stage == StageName.PHASE2_COMPANY_ENRICHMENT:
        result["company"] = s.company_provider_max_concurrency
    if stage == StageName.PHASE2_CONTACT_ENRICHMENT:
        result["contact"] = s.contact_provider_max_concurrency
    return result


def claim(db, run_id):
    run = db.get(StageRun, run_id)
    if run is None:
        db.rollback()
        return None
    prospect = db.get(Prospect, run.prospect_id)
    lock_batch(db, prospect)
    db.refresh(run)
    if run.status != StageStatus.QUEUED or utc(run.due_at) > now():
        db.rollback()
        return None
    capacity = buckets(run.stage)
    for bucket in sorted(capacity):
        if db.bind.dialect.name == "postgresql":
            key = int.from_bytes(hashlib.sha256(bucket.encode()).digest()[:8], "big", signed=True)
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    reservations = list(db.scalars(select(StageRun).where(StageRun.reservation_expires_at > now())))
    if any(
        sum(bucket in (r.reservations or []) for r in reservations) >= limit
        for bucket, limit in capacity.items()
    ):
        db.rollback()
        return None
    owner = str(uuid4())
    deadline = now() + timedelta(seconds=780)
    claimed = db.execute(
        update(StageRun)
        .where(StageRun.id == run.id, StageRun.status == StageStatus.QUEUED)
        .values(
            status=StageStatus.PROCESSING,
            owner=owner,
            started_at=now(),
            heartbeat_at=now(),
            lease_expires_at=now() + timedelta(seconds=90),
            execution_deadline=deadline,
            reservations=list(capacity),
            reservation_expires_at=deadline,
        )
    )
    if claimed.rowcount != 1:
        db.rollback()
        return None
    prospect.current_state = STATES[run.stage]
    db.commit()
    return owner


def owned(db, run_id, owner, *, recovery=False):
    run = db.get(StageRun, run_id)
    if run is None:
        return None
    prospect = db.get(Prospect, run.prospect_id)
    lock_batch(db, prospect)
    db.refresh(run)
    if (
        run.owner != owner
        or run.status != StageStatus.PROCESSING
        or (
            not recovery
            and (utc(run.lease_expires_at) <= now() or utc(run.execution_deadline) <= now())
        )
    ):
        db.rollback()
        return None
    return run


def finish(run, status=StageStatus.COMPLETED):
    run.status = status
    run.finished_at = now()
    run.owner = None
    run.lease_expires_at = None
    run.reservation_expires_at = None


class WorkerInterrupted(RuntimeError):
    pass


def classify(error, external):
    import httpx

    chain = []
    cause = error
    while cause and cause not in chain:
        chain.append(cause)
        cause = cause.__cause__
    if any(getattr(e, "external_outcome_unknown", False) for e in chain):
        return "EXTERNAL_OUTCOME_UNKNOWN", False, True
    if any(
        isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)) for e in chain
    ):
        return "BEFORE_TRANSMISSION", True, False
    if isinstance(error, WorkerInterrupted) and not external:
        return "WORKER_INTERRUPTED", True, False
    if not external:
        return "LOCAL_PROCESSING_ERROR", False, False
    if any(isinstance(e, (httpx.TimeoutException, httpx.TransportError)) for e in chain):
        return "EXTERNAL_OUTCOME_UNKNOWN", False, True
    from pydantic import ValidationError

    if (
        isinstance(error, ValidationError)
        or "invalid" in str(error).lower()
        or "malformed" in str(error).lower()
    ):
        return "INVALID_PROVIDER_RESPONSE", False, False
    if "required" in str(error).lower() or "configured" in str(error).lower():
        return "CONFIGURATION_ERROR", False, False
    if isinstance(error, (ValueError, KeyError, IndexError)):
        return "INVALID_PROVIDER_RESPONSE", False, False
    return "PROVIDER_FAILURE", False, external


def fail(db, run_id, owner, error, *, recovery=False):
    db.rollback()
    run = owned(db, run_id, owner, recovery=recovery)
    if run is None:
        return False
    code, auto, uncertain = classify(error, run.external_call_status == "IN_FLIGHT")
    deadline = run.execution_deadline
    finish(run, StageStatus.FAILED)
    run.failure_code = code
    run.error_type = type(error).__name__
    # Do not persist exception text: HTTP errors may contain credentials or callback URLs.
    messages = {
        "WORKER_INTERRUPTED": "Worker stopped before an external call; work was safely requeued.",
        "CONFIGURATION_ERROR": "Provider configuration is missing. Check local settings before retrying.",
        "INVALID_PROVIDER_RESPONSE": "Provider returned an invalid response. Investigate before retrying.",
        "EXTERNAL_OUTCOME_UNKNOWN": "Provider outcome is unknown. Retrying may cause a duplicate charge.",
        "BEFORE_TRANSMISSION": "Connection failed before request transmission.",
        "LOCAL_PROCESSING_ERROR": "Local processing failed. Check the saved inputs before retrying.",
        "PROVIDER_FAILURE": "Provider request failed. Investigate before retrying.",
    }
    run.error_message = messages[code]
    run.retryable = True
    run.retry_requires_confirmation = uncertain
    if uncertain:
        run.reservation_expires_at = deadline
    from app.models.contact import ContactEnrichmentRequest

    contact = db.scalar(
        select(ContactEnrichmentRequest).where(ContactEnrichmentRequest.stage_run_id == run.id)
    )
    if contact and contact.status != "RECEIVED":
        contact.status = "FAILED"
        contact.outcome = code
    prospect = db.get(Prospect, run.prospect_id)
    prospect.current_state = ProspectState.FAILED
    if auto and run.automatic_retries < get_settings().max_retry_attempts:
        n = run.automatic_retries
        delay = [5, 30, 120][n] if n < 3 else min(300, 120 * 2 ** (n - 2))
        db.flush()
        enqueue(db, prospect, run.stage, previous=run, delay=delay, automatic=True)
        prospect.current_state = STATES[run.stage]
    from app.services.batch_service import refresh_batch_status

    refresh_batch_status(db, prospect.batch)
    db.commit()
    return False
