from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.deps import require_admin, require_operator_or_admin
from app.core.database import get_db
from app.models.entities import Service, User
from app.models.schemas import ServiceCreate, ServiceOut
from app.services.health_service import evaluate_service_health, run_all_health_checks

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceOut)
def register_service(
    payload: ServiceCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ServiceOut:
    service = Service(**payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return ServiceOut.model_validate(service)


@router.get("", response_model=list[ServiceOut])
def list_services(
    region: str | None = Query(default=None),
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> list[ServiceOut]:
    query = db.query(Service)
    if region:
        query = query.filter(Service.region == region)
    services = query.order_by(Service.priority.asc()).all()
    return [ServiceOut.model_validate(service) for service in services]


@router.post("/{service_id}/heartbeat", response_model=ServiceOut)
def heartbeat_service(
    service_id: int,
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> ServiceOut:
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    service = evaluate_service_health(db, service)
    return ServiceOut.model_validate(service)


@router.post("/heartbeat/all")
def heartbeat_all_services(
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    return run_all_health_checks(db)
