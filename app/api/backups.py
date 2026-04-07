from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import require_operator_or_admin
from app.core.database import get_db
from app.models.entities import BackupSnapshot, Service, User
from app.models.schemas import BackupOut
from app.services.backup_service import create_backup, restore_latest_backup

router = APIRouter(prefix="/backups", tags=["backups"])


@router.post("/{service_id}", response_model=BackupOut)
def backup_service(
    service_id: int,
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> BackupOut:
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    snapshot = create_backup(db, service)
    return BackupOut.model_validate(snapshot)


@router.get("/history", response_model=list[BackupOut])
def backup_history(_: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)) -> list[BackupOut]:
    snapshots = db.query(BackupSnapshot).order_by(BackupSnapshot.created_at.desc()).limit(200).all()
    return [BackupOut.model_validate(snapshot) for snapshot in snapshots]


@router.post("/{service_id}/restore", response_model=BackupOut)
def restore_service_backup(
    service_id: int,
    _: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
) -> BackupOut:
    snapshot = restore_latest_backup(db, service_id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No snapshot found")
    return BackupOut.model_validate(snapshot)
