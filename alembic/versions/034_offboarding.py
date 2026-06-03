"""Offboarding + disciplinary: complete departure process + STC.

Tables:
- disciplinary_case: full workflow (PV -> convocation -> audition -> sanction)
- offboarding_process: checklist with 6 absolute prerequisites
- stc_calculation: 6-component decomposition

STC payment BLOCKED until ALL prerequisites true. No override.

Revision ID: 034
Revises: 033
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "034"
down_revision: Union[str, None] = "033"
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
    # 1. stc_calculation (before offboarding_process for FK)
    op.create_table(
        "stc_calculation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("offboarding_id", UUID(as_uuid=True), nullable=True),
        sa.Column("calculation_date", sa.Date, nullable=False),
        sa.Column("last_month_salary", sa.Numeric(15, 2), nullable=False),
        sa.Column("days_worked", sa.Integer, nullable=True),
        sa.Column("leave_compensation", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("leave_days_unused", sa.Numeric(5, 1), nullable=True),
        sa.Column("notice_indemnity", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("severance_pay", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("seniority_months", sa.Integer, nullable=True),
        sa.Column("thirteenth_month_prorated", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("advance_repayment", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("loan_balance", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("equipment_deduction", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("other_deductions", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("gross_stc", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(15, 2), nullable=False),
        sa.Column("net_stc", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'CALCULATED'")),
        sa.Column("payslip_id", UUID(as_uuid=True), sa.ForeignKey("payslip.id", ondelete="SET NULL"), nullable=True),
        *_system_columns(),
    )

    # 2. disciplinary_case
    op.create_table(
        "disciplinary_case",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("infraction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("infraction_location", sa.String(255), nullable=True),
        sa.Column("infraction_description", sa.Text, nullable=False),
        sa.Column("witnesses", sa.Text, nullable=True),
        sa.Column("evidence_urls", JSONB, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("pv_constat_date", sa.Date, nullable=False),
        sa.Column("pv_constat_url", sa.Text, nullable=True),
        sa.Column("convocation_date", sa.Date, nullable=True),
        sa.Column("audition_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audition_location", sa.String(255), nullable=True),
        sa.Column("rights_statement_included", sa.Boolean, nullable=True),
        sa.Column("convocation_url", sa.Text, nullable=True),
        sa.Column("employee_statements", sa.Text, nullable=True),
        sa.Column("questions_answers", sa.Text, nullable=True),
        sa.Column("assistant_name", sa.String(255), nullable=True),
        sa.Column("assistant_role", sa.String(100), nullable=True),
        sa.Column("pv_audition_url", sa.Text, nullable=True),
        sa.Column("sanction", sa.String(20), nullable=True),
        sa.Column("mise_a_pied_days", sa.Integer, nullable=True),
        sa.Column("decision_date", sa.Date, nullable=True),
        sa.Column("decision_justification", sa.Text, nullable=True),
        sa.Column("validated_drh", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_dg", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_pdg", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PV_CONSTAT'")),
        *_system_columns(),
    )

    # 3. offboarding_process
    op.create_table(
        "offboarding_process",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("employee_contract.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("trigger_type", sa.String(30), nullable=False),
        sa.Column("trigger_date", sa.Date, nullable=False),
        sa.Column("last_working_day", sa.Date, nullable=True),
        sa.Column("notice_period_waived", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("handover_pv_signed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("equipment_quitus_signed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("badge_deactivated", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("badge_deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("digital_access_revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("digital_access_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stc_verified_l6", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("stc_approved_triple", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("stc_calculation_id", UUID(as_uuid=True), sa.ForeignKey("stc_calculation.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stc_paid", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("stc_paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'INITIE'")),
        sa.Column("certificat_travail_url", sa.Text, nullable=True),
        sa.Column("attestation_travail_url", sa.Text, nullable=True),
        *_system_columns(),
    )

    for t in ("stc_calculation", "disciplinary_case", "offboarding_process"):
        op.execute(f"""CREATE TRIGGER trg_{t}_updated_at BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{t}');")


def downgrade() -> None:
    for t in ("offboarding_process", "disciplinary_case", "stc_calculation"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_updated_at ON {t};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_no_delete ON {t};")
    op.drop_table("offboarding_process")
    op.drop_table("disciplinary_case")
    op.drop_table("stc_calculation")
