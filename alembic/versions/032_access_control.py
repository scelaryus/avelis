"""Physical access control: S4A controllers, badges, events, middleware.

Tables:
- site_middleware: per-site FastAPI service config
- access_controller: S4A ACB-W4PS devices
- access_zone: logical zones with schedules
- badge_record: badge lifecycle (creation to deactivation)
- badge_event: raw events with SHA-256 dedup
- middleware_command: queued commands for offline resilience

Revision ID: 032
Revises: 031
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _system_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("version", sa.Integer, nullable=False,
                  server_default=sa.text("1")),
    ]


def upgrade() -> None:
    # 1-6: Create all tables
    for table_def in _table_defs():
        op.create_table(table_def["name"], *table_def["columns"], *_system_columns())

    # CHECK constraints
    op.execute("""ALTER TABLE badge_event ADD CONSTRAINT chk_be_direction
        CHECK (direction IN ('IN', 'OUT'));""")
    op.execute("""ALTER TABLE badge_event ADD CONSTRAINT chk_be_result
        CHECK (result IN ('GRANTED', 'DENIED'));""")

    # Triggers
    for t in ("site_middleware", "access_controller", "access_zone",
              "badge_record", "badge_event", "middleware_command"):
        op.execute(f"""CREATE TRIGGER trg_{t}_updated_at BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{t}');")


def _table_defs():
    return [
        {"name": "site_middleware", "columns": [
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("site_name", sa.String(255), nullable=False),
            sa.Column("site_code", sa.String(20), nullable=False, index=True),
            sa.Column("api_base_url", sa.String(255), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'DISCONNECTED'")),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("pending_commands", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("pending_events", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True),
        ]},
        {"name": "access_controller", "columns": [
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("middleware_id", UUID(as_uuid=True), sa.ForeignKey("site_middleware.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("controller_id", sa.String(30), nullable=False, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("firmware_version", sa.String(20), nullable=True),
            sa.Column("door_count", sa.Integer, nullable=False, server_default=sa.text("4")),
            sa.Column("user_capacity", sa.Integer, nullable=False, server_default=sa.text("10000")),
            sa.Column("current_user_count", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'OFFLINE'")),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        ]},
        {"name": "access_zone", "columns": [
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("zone_code", sa.String(30), nullable=False, index=True),
            sa.Column("zone_name", sa.String(255), nullable=False),
            sa.Column("controllers_config", JSONB, nullable=False),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        ]},
        {"name": "badge_record", "columns": [
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("badge_number", sa.String(50), unique=True, nullable=False, index=True),
            sa.Column("employee_name", sa.String(255), nullable=False),
            sa.Column("access_zones", JSONB, nullable=True),
            sa.Column("valid_from", sa.Date, nullable=False),
            sa.Column("valid_until", sa.Date, nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING_SYNC'")),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deactivation_reason", sa.String(30), nullable=True),
            sa.Column("synced_to_controllers", JSONB, nullable=True),
            sa.Column("sync_failures", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("last_sync_attempt", sa.DateTime(timezone=True), nullable=True),
        ]},
        {"name": "badge_event", "columns": [
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("badge_number", sa.String(50), nullable=False, index=True),
            sa.Column("controller_id", sa.String(30), nullable=False),
            sa.Column("door_id", sa.Integer, nullable=False),
            sa.Column("direction", sa.String(3), nullable=False),
            sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("result", sa.String(10), nullable=False),
            sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("event_hash", sa.String(64), nullable=True, unique=True),
            sa.Column("processed_for_attendance", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("anomaly_detected", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("anomaly_type", sa.String(30), nullable=True),
            sa.Column("middleware_id", UUID(as_uuid=True), sa.ForeignKey("site_middleware.id", ondelete="SET NULL"), nullable=True),
        ]},
        {"name": "middleware_command", "columns": [
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("middleware_id", UUID(as_uuid=True), sa.ForeignKey("site_middleware.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("command_type", sa.String(20), nullable=False),
            sa.Column("payload", JSONB, nullable=False),
            sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("5")),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'QUEUED'")),
            sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("max_retries", sa.Integer, nullable=False, server_default=sa.text("48")),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
        ]},
    ]


def downgrade() -> None:
    for t in ("middleware_command", "badge_event", "badge_record",
              "access_zone", "access_controller", "site_middleware"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_updated_at ON {t};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_no_delete ON {t};")
    for t in ("middleware_command", "badge_event", "badge_record",
              "access_zone", "access_controller", "site_middleware"):
        op.drop_table(t)
