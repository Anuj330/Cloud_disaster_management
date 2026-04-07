import json
import os
from datetime import datetime, timezone
from sqlalchemy import func
from app.core.config import get_settings
from app.core.metrics import BACKUPS_CREATED_TOTAL
from app.models.entities import BackupSnapshot, Service

settings = get_settings()


def _ensure_object_store() -> None:
    os.makedirs(settings.object_store_path, exist_ok=True)


def create_backup(db, service: Service) -> BackupSnapshot:
    _ensure_object_store()
    latest_version = (
        db.query(func.max(BackupSnapshot.version))
        .filter(BackupSnapshot.service_id == service.id)
        .scalar()
        or 0
    )
    next_version = latest_version + 1

    timestamp = datetime.now(timezone.utc)
    file_name = f"{service.name}_{service.id}_v{next_version}_{int(timestamp.timestamp())}.json"
    storage_key = os.path.join(settings.object_store_path, file_name)

    payload = {
        "service_id": service.id,
        "service_name": service.name,
        "region": service.region,
        "captured_at": timestamp.isoformat(),
        "status": service.status,
        "version": next_version,
    }

    with open(storage_key, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj)

    snapshot = BackupSnapshot(
        service_id=service.id,
        version=next_version,
        storage_key=storage_key,
        metadata_json=payload,
        size_bytes=os.path.getsize(storage_key),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    BACKUPS_CREATED_TOTAL.inc()
    return snapshot


def restore_latest_backup(db, service_id: int) -> BackupSnapshot | None:
    snapshot = (
        db.query(BackupSnapshot)
        .filter(BackupSnapshot.service_id == service_id)
        .order_by(BackupSnapshot.version.desc())
        .first()
    )
    return snapshot
