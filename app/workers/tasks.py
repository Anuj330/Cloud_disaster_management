import logging
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.entities import Service
from app.services.backup_service import create_backup
from app.services.health_service import run_all_health_checks
from app.services.recovery_service import run_recovery_workflow

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.run_health_checks")
def run_health_checks() -> dict:
    db = SessionLocal()
    try:
        return run_all_health_checks(db)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.scheduled_backup_all_services")
def scheduled_backup_all_services() -> dict:
    db = SessionLocal()
    created = 0
    try:
        services = db.query(Service).all()
        for service in services:
            create_backup(db, service)
            created += 1
        return {"created_backups": created}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_recovery_workflow_task")
def run_recovery_workflow_task(service_id: int, reason: str) -> dict:
    db = SessionLocal()
    try:
        workflow = run_recovery_workflow(db, service_id=service_id, reason=reason)
        return {"workflow_id": workflow.id, "status": workflow.status}
    finally:
        db.close()
