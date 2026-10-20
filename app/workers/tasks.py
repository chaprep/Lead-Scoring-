from app.workers.celery_app import celery_app
from app.pipeline.execution import run_stage


@celery_app.task(name="workflow.v2.execute", queue="workflow.v2")
def execute_stage(stage_run_id: str):
    return run_stage(stage_run_id)


@celery_app.task(name="app.workers.tasks.healthcheck")
def healthcheck():
    return "ok"


# Legacy queues are quarantined. Old deliveries cannot start provider work.
@celery_app.task(name="app.workers.tasks.run_phase1")
def run_phase1(*args):
    return False


@celery_app.task(name="app.workers.tasks.run_phase2")
def run_phase2(*args):
    return False


@celery_app.task(name="app.workers.tasks.run_prioritization")
def run_prioritization(*args):
    return False


@celery_app.task(name="app.workers.tasks.run_contact_enrichment")
def run_contact_enrichment(*args):
    return False
