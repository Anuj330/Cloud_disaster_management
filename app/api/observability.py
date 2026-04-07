from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.api.deps import require_operator_or_admin
from app.core.database import get_db
from app.models.entities import FailoverEvent, RecoveryWorkflow, Service, User, WorkflowLog
from app.models.schemas import FailoverOut, RecoveryWorkflowOut, WorkflowLogOut
from app.services.failover_service import get_region_state

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/system-status")
def system_status(_: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)) -> dict:
    state = get_region_state()
    total_services = db.query(func.count(Service.id)).scalar() or 0
    healthy_services = db.query(func.count(Service.id)).filter(Service.status == "HEALTHY").scalar() or 0
    degraded_services = db.query(func.count(Service.id)).filter(Service.status == "DEGRADED").scalar() or 0
    down_services = db.query(func.count(Service.id)).filter(Service.status == "DOWN").scalar() or 0

    return {
        "active_region": state["active_region"],
        "standby_region": state["standby_region"],
        "service_counts": {
            "total": total_services,
            "healthy": healthy_services,
            "degraded": degraded_services,
            "down": down_services,
        },
    }


@router.get("/failovers", response_model=list[FailoverOut])
def failover_logs(_: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)) -> list[FailoverOut]:
    events = db.query(FailoverEvent).order_by(FailoverEvent.created_at.desc()).limit(100).all()
    return [FailoverOut.model_validate(event) for event in events]


@router.get("/workflows", response_model=list[RecoveryWorkflowOut])
def recovery_workflows(
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> list[RecoveryWorkflowOut]:
    workflows = db.query(RecoveryWorkflow).order_by(RecoveryWorkflow.started_at.desc()).limit(100).all()
    return [RecoveryWorkflowOut.model_validate(workflow) for workflow in workflows]


@router.get("/workflows/{workflow_id}/logs", response_model=list[WorkflowLogOut])
def workflow_logs(
    workflow_id: int,
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> list[WorkflowLogOut]:
    logs = (
        db.query(WorkflowLog)
        .filter(WorkflowLog.workflow_id == workflow_id)
        .order_by(WorkflowLog.created_at.asc())
        .all()
    )
    return [WorkflowLogOut.model_validate(log_entry) for log_entry in logs]


@router.get("/metrics/recovery")
def recovery_metrics(_: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)) -> dict:
    avg_rto = db.query(func.avg(RecoveryWorkflow.rto_seconds)).scalar()
    avg_rpo = db.query(func.avg(RecoveryWorkflow.rpo_seconds)).scalar()
    completed = db.query(func.count(RecoveryWorkflow.id)).filter(RecoveryWorkflow.status == "COMPLETED").scalar() or 0
    return {
        "completed_workflows": completed,
        "avg_rto_seconds": float(avg_rto) if avg_rto is not None else None,
        "avg_rpo_seconds": float(avg_rpo) if avg_rpo is not None else None,
    }
