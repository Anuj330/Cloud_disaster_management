from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dr_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "scheduled-health-check": {
            "task": "app.workers.tasks.run_health_checks",
            "schedule": settings.monitoring_interval_seconds,
        },
        "scheduled-backup": {
            "task": "app.workers.tasks.scheduled_backup_all_services",
            "schedule": settings.backup_schedule_minutes * 60,
        },
    },
)
