from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="operator")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    url = Column(String(512), nullable=False)
    region = Column(String(64), nullable=False, index=True)
    priority = Column(Integer, default=100, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    status = Column(String(32), default="HEALTHY", nullable=False, index=True)
    last_heartbeat = Column(DateTime)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    circuit_state = Column(String(16), default="CLOSED", nullable=False)
    circuit_opened_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    backups = relationship("BackupSnapshot", back_populates="service")


class FailoverEvent(Base):
    __tablename__ = "failover_events"

    id = Column(Integer, primary_key=True, index=True)
    from_region = Column(String(64), nullable=False)
    to_region = Column(String(64), nullable=False)
    reason = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BackupSnapshot(Base):
    __tablename__ = "backup_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    storage_key = Column(String(512), nullable=False)
    metadata_json = Column(JSONB, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service", back_populates="backups")


class RecoveryWorkflow(Base):
    __tablename__ = "recovery_workflows"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="RUNNING", index=True)
    failure_detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    rto_seconds = Column(Float)
    rpo_seconds = Column(Float)


class WorkflowLog(Base):
    __tablename__ = "workflow_logs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("recovery_workflows.id"), nullable=False, index=True)
    step = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
