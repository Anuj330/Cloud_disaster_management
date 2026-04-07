from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import require_operator_or_admin
from app.core.database import get_db
from app.models.entities import Service, User
from app.services.failover_service import get_region_state, trigger_failover
from app.workers.tasks import run_recovery_workflow_task

router = APIRouter(prefix="/dr", tags=["disaster-recovery"])


@router.get("/regions")
def get_regions(_: User = Depends(require_operator_or_admin)) -> dict[str, str]:
    return get_region_state()


@router.post("/failover")
def failover(
    reason: str = "Manual failover",
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    return trigger_failover(db, reason=reason)


@router.post("/recover/{service_id}")
def trigger_recovery_workflow(
    service_id: int,
    reason: str = "Service failure detected",
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    task = run_recovery_workflow_task.delay(service_id=service_id, reason=reason)
    return {"task_id": task.id, "service_id": service_id, "status": "QUEUED"}
