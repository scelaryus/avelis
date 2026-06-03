"""6-level payslip verification pipeline.

Table: payslip_verification with per-level results, anomalies, z-scores.

Revision ID: 030
Revises: 029
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "030"
down_revision: Union[str, None] = "029"
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
    op.create_table(
        "payslip_verification",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("payslip_id", UUID(as_uuid=True),
                  sa.ForeignKey("payslip.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("level_name", sa.String(50), nullable=False),
        sa.Column("verdict", sa.String(10), nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("checks_performed", sa.Integer, nullable=True),
        sa.Column("checks_passed", sa.Integer, nullable=True),
        sa.Column("checks_failed", sa.Integer, nullable=True),
        sa.Column("checks_flagged", sa.Integer, nullable=True),
        sa.Column("anomalies", JSONB, nullable=True),
        sa.Column("llm_raw_response", sa.Text, nullable=True),
        sa.Column("llm_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("anomaly_score", sa.Numeric(8, 4), nullable=True),
        sa.Column("z_scores", JSONB, nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("review_action", sa.String(20), nullable=True),
        sa.Column("review_justification", sa.Text, nullable=True),
        *_system_columns(),
    )

    op.execute("""
        ALTER TABLE payslip_verification
        ADD CONSTRAINT chk_pv_level
        CHECK (level >= 1 AND level <= 6);
    """)

    op.execute("""
        ALTER TABLE payslip_verification
        ADD CONSTRAINT chk_pv_verdict
        CHECK (verdict IN ('PASS', 'FLAG', 'FAIL', 'PENDING', 'SKIPPED'));
    """)

    op.execute("""
        CREATE TRIGGER trg_payslip_verification_updated_at
        BEFORE UPDATE ON payslip_verification
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
    """)
    op.execute("SELECT gfi_apply_no_delete_trigger('payslip_verification');")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_payslip_verification_updated_at ON payslip_verification;")
    op.execute("DROP TRIGGER IF EXISTS trg_payslip_verification_no_delete ON payslip_verification;")
    op.drop_table("payslip_verification")
