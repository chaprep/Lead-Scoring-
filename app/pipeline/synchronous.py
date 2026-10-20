from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.stage_run import StageRun
from app.core.enums import StageStatus
from app.pipeline.execution import run_stage


def process_group(prospect_id, stages, session=None):
    db = session or SessionLocal()
    succeeded = False
    try:
        while True:
            run = db.scalar(
                select(StageRun).where(
                    StageRun.prospect_id == prospect_id,
                    StageRun.status == StageStatus.QUEUED,
                    StageRun.stage.in_(stages),
                )
            )
            if run is None:
                return succeeded
            if not run_stage(run.id, db):
                return False
            succeeded = True
    finally:
        if session is None:
            db.close()
