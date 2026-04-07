from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="operator")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    created_at: datetime


class ServiceCreate(BaseModel):
    name: str
    url: str
    region: str
    priority: int = 100
    is_primary: bool = False


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    region: str
    priority: int
    is_primary: bool
    status: str
    last_heartbeat: Optional[datetime] = None
    circuit_state: str


class BackupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    version: int
    storage_key: str
    metadata_json: dict[str, Any]
    size_bytes: int
    created_at: datetime


class FailoverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_region: str
    to_region: str
    reason: str
    created_at: datetime


class RecoveryWorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    rto_seconds: Optional[float] = None
    rpo_seconds: Optional[float] = None


class WorkflowLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    step: str
    status: str
    message: str
    created_at: datetime
