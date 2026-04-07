from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.metrics import RECOVERY_WORKFLOWS_TOTAL
from app.models.entities import RecoveryWorkflow, Service, WorkflowLog
from app.services.backup_service import restore_latest_backup
from app.services.failover_service import trigger_failover


def log_workflow_step(db: Session, workflow_id: int, step: str, status: str, message: str) -> None:
    log_entry = WorkflowLog(workflow_id=workflow_id, step=step, status=status, message=message)
    db.add(log_entry)
    db.commit()


def run_recovery_workflow(db: Session, service_id: int, reason: str) -> RecoveryWorkflow:
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise ValueError("Service not found")

    workflow = RecoveryWorkflow(service_id=service_id, status="RUNNING")
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    RECOVERY_WORKFLOWS_TOTAL.inc()

    detected_at = workflow.failure_detected_at.replace(tzinfo=timezone.utc)

    log_workflow_step(db, workflow.id, "detect_failure", "SUCCESS", reason)

    failover_result = trigger_failover(db, reason=f"Workflow {workflow.id}: {reason}")
    log_workflow_step(
        db,
        workflow.id,
        "trigger_failover",
        "SUCCESS",
        f"Switched {failover_result['from_region']} -> {failover_result['to_region']}",
    )

    latest_backup = restore_latest_backup(db, service_id)
    if latest_backup:
        backup_time = latest_backup.created_at.replace(tzinfo=timezone.utc)
        rpo = (detected_at - backup_time).total_seconds()
        log_workflow_step(
            db,
            workflow.id,
            "restore_backup",
            "SUCCESS",
            f"Restored backup version {latest_backup.version}",
        )
    else:
        rpo = None
        log_workflow_step(db, workflow.id, "restore_backup", "FAILED", "No backup available")

    workflow.status = "COMPLETED"
    workflow.completed_at = datetime.utcnow()
    started_at = workflow.started_at.replace(tzinfo=timezone.utc)
    completed_at = workflow.completed_at.replace(tzinfo=timezone.utc)
    workflow.rto_seconds = (completed_at - started_at).total_seconds()
    workflow.rpo_seconds = rpo

    service.status = "HEALTHY"
    service.consecutive_failures = 0
    service.circuit_state = "CLOSED"
    service.circuit_opened_at = None

    db.commit()
    db.refresh(workflow)

    log_workflow_step(db, workflow.id, "mark_recovered", "SUCCESS", "Service marked as recovered")
    return workflow
