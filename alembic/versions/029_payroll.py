"""Payroll: 10-step calculation engine for GENERAL and BTPH regimes.

Table: payslip with all 10-step components stored individually.

CHECK: CNAS regime IN (GENERAL, BTPH)
Soft-delete trigger.

Revision ID: 029
Revises: 028
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "029"
down_revision: Union[str, None] = "028"
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
        "payslip",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True),
                  sa.ForeignKey("employee.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        # Step 1
        sa.Column("cnas_regime", sa.String(10), nullable=False),
        sa.Column("cnas_employee_rate", sa.Numeric(6, 3), nullable=False),
        sa.Column("cnas_employer_rate", sa.Numeric(6, 3), nullable=False),
        # Step 2
        sa.Column("salary_base", sa.Numeric(15, 2), nullable=False),
        sa.Column("prime_rendement", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("prime_nuisance", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("prime_panier", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("indemnite_transport", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("prime_iep", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("prime_chantier", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("overtime_hours", sa.Numeric(6, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("overtime_amount", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("gross_salary", sa.Numeric(15, 2), nullable=False),
        # Step 3
        sa.Column("cnas_employee_amount", sa.Numeric(15, 2), nullable=False),
        # Step 4
        sa.Column("taxable_income", sa.Numeric(15, 2), nullable=False),
        # Steps 5-6
        sa.Column("irg_brut", sa.Numeric(15, 2), nullable=False),
        sa.Column("irg_abatement", sa.Numeric(15, 2), nullable=False),
        sa.Column("irg_final", sa.Numeric(15, 2), nullable=False),
        # Step 7
        sa.Column("advance_repayment", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("loan_installment", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("other_deductions", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_deductions", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        # Step 8
        sa.Column("net_salary", sa.Numeric(15, 2), nullable=False),
        # Step 9
        sa.Column("cnas_employer_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("formation_contribution", sa.Numeric(15, 2), nullable=False),
        sa.Column("apprentissage_contribution", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_employer_cost", sa.Numeric(15, 2), nullable=False),
        # Step 10
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'CALCULATED'")),
        sa.Column("spi_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("journal_entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal_entry.id", ondelete="SET NULL"), nullable=True),
        *_system_columns(),
    )

    op.execute("""
        ALTER TABLE payslip
        ADD CONSTRAINT chk_ps_regime
        CHECK (cnas_regime IN ('GENERAL', 'BTPH'));
    """)

    op.execute("""
        CREATE TRIGGER trg_payslip_updated_at
        BEFORE UPDATE ON payslip
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
    """)
    op.execute("SELECT gfi_apply_no_delete_trigger('payslip');")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_payslip_updated_at ON payslip;")
    op.execute("DROP TRIGGER IF EXISTS trg_payslip_no_delete ON payslip;")
    op.drop_table("payslip")
