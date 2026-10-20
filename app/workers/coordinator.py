"""Durably dispatch queued work, reconcile leases, and apply contact receipts."""

import logging
import time
from datetime import timedelta
from sqlalchemy import select, or_
from app.db.session import SessionLocal
from app.models.stage_run import StageRun
from app.models.contact import CoordinatorHeartbeat
from app.core.enums import StageStatus
from app.pipeline.ledger import now, utc, fail, WorkerInterrupted
from app.services.contacts import process_receipts, expire_contacts
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


def tick(factory=SessionLocal, publish=None):
    publish = publish or celery_app.send_task
    with factory() as db:
        beat = db.get(CoordinatorHeartbeat, 1)
        if beat is None:
            db.add(CoordinatorHeartbeat(id=1, seen_at=now()))
        else:
            beat.seen_at = now()
        db.commit()
        process_receipts(db)
        expire_contacts(db)
        expired = list(
            db.scalars(
                select(StageRun.id).where(
                    StageRun.status == StageStatus.PROCESSING,
                    StageRun.owner.is_not(None),
                    StageRun.lease_expires_at < now(),
                )
            )
        )
        db.commit()
        for run_id in expired:
            run = db.get(StageRun, run_id)
            # Recover under the same ownership fence by temporarily extending the expired lease.
            # Reconciliation holds workflow locks, so a stale worker cannot win this update.
            from app.pipeline.ledger import lock_batch

            lock_batch(db, run.prospect)
            db.refresh(run)
            if (
                run.status != StageStatus.PROCESSING
                or run.owner is None
                or utc(run.lease_expires_at) >= now()
            ):
                db.rollback()
                continue
            from uuid import uuid4

            recovery_owner = str(uuid4())
            run.owner = recovery_owner
            run.lease_expires_at = now() + timedelta(seconds=90)
            db.commit()
            fail(
                db,
                run_id,
                recovery_owner,
                WorkerInterrupted("Worker execution interrupted"),
                recovery=True,
            )
        due = list(
            db.scalars(
                select(StageRun.id).where(
                    StageRun.status == StageStatus.QUEUED,
                    StageRun.due_at <= now(),
                    or_(
                        StageRun.published_at.is_(None),
                        StageRun.published_at < now() - timedelta(seconds=30),
                    ),
                )
            )
        )
        db.commit()
        for run_id in due:
            run = db.get(StageRun, run_id)
            run.publication_attempts += 1
            db.commit()
            try:
                publish("workflow.v2.execute", args=[str(run_id)], queue="workflow.v2", retry=False)
                run.published_at = now()
                run.publication_error = None
            except Exception as error:
                run.publication_error = type(error).__name__
                db.commit()
                break
            db.commit()


def main():
    while True:
        try:
            tick()
        except Exception:
            log.exception("Coordinator scan failed")
        time.sleep(2)


if __name__ == "__main__":
    main()
