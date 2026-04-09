import logging
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.redis_client import redis_client
from app.models.entities import Service
from app.services.backup_service import create_backup
from app.services.health_service import run_all_health_checks
from app.services.recovery_service import run_recovery_workflow

logger = logging.getLogger(__name__)


def _acquire_lock(lock_key: str, ttl_seconds: int) -> bool:
    try:
        return bool(redis_client.set(lock_key, "1", nx=True, ex=ttl_seconds))
    except Exception:
        logger.exception("Lock acquire failed, continuing without distributed lock", extra={"lock_key": lock_key})
        return True


def _release_lock(lock_key: str) -> None:
    try:
        redis_client.delete(lock_key)
    except Exception:
        logger.exception("Lock release failed", extra={"lock_key": lock_key})


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
    skipped = 0
    try:
        services = db.query(Service).all()
        for service in services:
            lock_key = f"dr:lock:backup:service:{service.id}"
            if not _acquire_lock(lock_key, ttl_seconds=120):
                skipped += 1
                continue
            try:
                create_backup(db, service)
                created += 1
            finally:
                _release_lock(lock_key)
        return {"created_backups": created, "skipped_backups": skipped}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_recovery_workflow_task")
def run_recovery_workflow_task(service_id: int, reason: str) -> dict:
    lock_key = f"dr:lock:recovery:service:{service_id}"
    if not _acquire_lock(lock_key, ttl_seconds=600):
        logger.info(
            "Skipping duplicate recovery workflow task",
            extra={"event": "recovery_duplicate", "service_id": service_id},
        )
        return {"service_id": service_id, "status": "SKIPPED_DUPLICATE"}

    db = SessionLocal()
    try:
        workflow = run_recovery_workflow(db, service_id=service_id, reason=reason)
        return {"workflow_id": workflow.id, "status": workflow.status}
    finally:
        db.close()
        _release_lock(lock_key)
