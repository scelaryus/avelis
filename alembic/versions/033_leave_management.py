"""Leave management: 10 types, 6-level verification, fraud detection.

Tables:
- leave_balance: annual entitlement tracking
- leave_request: request with verification pipeline
- leave_verification: per-level results (L1-L6)

Revision ID: 033
Revises: 032
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "033"
down_revision: Union[str, None] = "032"
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
    # 1. leave_balance
    op.create_table(
        "leave_balance",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("leave_type", sa.String(30), nullable=False),
        sa.Column("entitled_days", sa.Numeric(5, 1), nullable=False),
        sa.Column("used_days", sa.Numeric(5, 1), nullable=False, server_default=sa.text("0")),
        sa.Column("remaining_days", sa.Numeric(5, 1), nullable=False),
        sa.Column("carried_from_previous", sa.Numeric(5, 1), nullable=False, server_default=sa.text("0")),
        *_system_columns(),
    )

    # 2. leave_request
    op.create_table(
        "leave_request",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("leave_type", sa.String(30), nullable=False, index=True),
        sa.Column("start_date", sa.Date, nullable=False, index=True),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("duration_days", sa.Numeric(5, 1), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("medical_certificate_url", sa.Text, nullable=True),
        sa.Column("supporting_document_url", sa.Text, nullable=True),
        sa.Column("certificate_ocr_result", JSONB, nullable=True),
        sa.Column("pay_impact", sa.String(20), nullable=False, server_default=sa.text("'FULL'")),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'BROUILLON'")),
        sa.Column("approved_by_manager", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_manager_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_drh", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_drh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("fraud_alert", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("fraud_details", JSONB, nullable=True),
        sa.Column("replacement_employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="SET NULL"), nullable=True),
        *_system_columns(),
    )

    # 3. leave_verification
    op.create_table(
        "leave_verification",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("leave_request_id", UUID(as_uuid=True), sa.ForeignKey("leave_request.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("level_name", sa.String(50), nullable=False),
        sa.Column("verdict", sa.String(10), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anomalies", JSONB, nullable=True),
        sa.Column("badge_events_during_leave", JSONB, nullable=True),
        sa.Column("fraud_confirmed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        *_system_columns(),
    )

    for t in ("leave_balance", "leave_request", "leave_verification"):
        op.execute(f"""CREATE TRIGGER trg_{t}_updated_at BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{t}');")


def downgrade() -> None:
    for t in ("leave_verification", "leave_request", "leave_balance"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_updated_at ON {t};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_no_delete ON {t};")
    op.drop_table("leave_verification")
    op.drop_table("leave_request")
    op.drop_table("leave_balance")
