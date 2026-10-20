from typing import Literal

import redis
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, Literal["ok", "unavailable"]]:
    """Report whether the API and its required local dependencies are reachable."""
    settings = get_settings()
    database_status: Literal["ok", "unavailable"] = "ok"
    redis_status: Literal["ok", "unavailable"] = "ok"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_status = "unavailable"

    try:
        redis.from_url(str(settings.redis_url), socket_connect_timeout=1).ping()
    except (redis.RedisError, OSError):
        redis_status = "unavailable"

    overall: Literal["ok", "unavailable"] = (
        "ok" if database_status == "ok" and redis_status == "ok" else "unavailable"
    )
    return {"status": overall, "database": database_status, "redis": redis_status}


@router.get("/health/workflow")
def workflow_health():
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func
    from app.models.contact import CoordinatorHeartbeat
    from app.models.stage_run import StageRun
    from app.core.enums import StageStatus
    from app.pipeline.ledger import now, utc

    with Session(engine) as db:
        beat = db.get(CoordinatorHeartbeat, 1)
        oldest = db.scalar(
            select(func.min(StageRun.due_at)).where(
                StageRun.status == StageStatus.QUEUED, StageRun.due_at < now()
            )
        )
        alive = bool(beat and (now() - utc(beat.seen_at)).total_seconds() < 15)
        return {
            "coordinator_alive": alive,
            "last_seen_at": beat.seen_at if beat else None,
            "oldest_overdue_seconds": max(0, (now() - utc(oldest)).total_seconds())
            if oldest
            else 0,
            "publication_failures": db.scalar(
                select(func.count())
                .select_from(StageRun)
                .where(
                    StageRun.status == StageStatus.QUEUED, StageRun.publication_error.is_not(None)
                )
            ),
            "expired_leases": db.scalar(
                select(func.count())
                .select_from(StageRun)
                .where(
                    StageRun.status == StageStatus.PROCESSING,
                    StageRun.owner.is_not(None),
                    StageRun.lease_expires_at < now(),
                )
            ),
        }
