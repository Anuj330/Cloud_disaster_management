"""Initial schema for cloud disaster management system"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260407_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="operator"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="HEALTHY"),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("circuit_state", sa.String(length=16), nullable=False, server_default="CLOSED"),
        sa.Column("circuit_opened_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_services_id", "services", ["id"])
    op.create_index("ix_services_name", "services", ["name"])
    op.create_index("ix_services_region", "services", ["region"])
    op.create_index("ix_services_status", "services", ["status"])

    op.create_table(
        "failover_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_region", sa.String(length=64), nullable=False),
        sa.Column("to_region", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_failover_events_id", "failover_events", ["id"])

    op.create_table(
        "backup_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
    )
    op.create_index("ix_backup_snapshots_id", "backup_snapshots", ["id"])
    op.create_index("ix_backup_snapshots_service_id", "backup_snapshots", ["service_id"])

    op.create_table(
        "recovery_workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RUNNING"),
        sa.Column("failure_detected_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("rto_seconds", sa.Float(), nullable=True),
        sa.Column("rpo_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
    )
    op.create_index("ix_recovery_workflows_id", "recovery_workflows", ["id"])
    op.create_index("ix_recovery_workflows_service_id", "recovery_workflows", ["service_id"])
    op.create_index("ix_recovery_workflows_status", "recovery_workflows", ["status"])

    op.create_table(
        "workflow_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["recovery_workflows.id"]),
    )
    op.create_index("ix_workflow_logs_id", "workflow_logs", ["id"])
    op.create_index("ix_workflow_logs_workflow_id", "workflow_logs", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_logs_workflow_id", table_name="workflow_logs")
    op.drop_index("ix_workflow_logs_id", table_name="workflow_logs")
    op.drop_table("workflow_logs")

    op.drop_index("ix_recovery_workflows_status", table_name="recovery_workflows")
    op.drop_index("ix_recovery_workflows_service_id", table_name="recovery_workflows")
    op.drop_index("ix_recovery_workflows_id", table_name="recovery_workflows")
    op.drop_table("recovery_workflows")

    op.drop_index("ix_backup_snapshots_service_id", table_name="backup_snapshots")
    op.drop_index("ix_backup_snapshots_id", table_name="backup_snapshots")
    op.drop_table("backup_snapshots")

    op.drop_index("ix_failover_events_id", table_name="failover_events")
    op.drop_table("failover_events")

    op.drop_index("ix_services_status", table_name="services")
    op.drop_index("ix_services_region", table_name="services")
    op.drop_index("ix_services_name", table_name="services")
    op.drop_index("ix_services_id", table_name="services")
    op.drop_table("services")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
