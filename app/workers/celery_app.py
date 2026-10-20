from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("lead_scoring", broker=str(settings.redis_url), backend=str(settings.redis_url))
celery_app.conf.update(
    task_default_queue="workflow.v2",
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=720,
    task_time_limit=780,
    broker_transport_options={
        "visibility_timeout": 1800,
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
    },
    result_backend_transport_options={"visibility_timeout": 1800},
    visibility_timeout=1800,
    broker_connection_timeout=3,
    task_acks_late=True,
    task_track_started=True,
    worker_concurrency=settings.celery_worker_concurrency,
    broker_connection_retry_on_startup=True,
    task_routes={"workflow.v2.execute": {"queue": "workflow.v2"}},
)
celery_app.autodiscover_tasks(["app.workers"])
