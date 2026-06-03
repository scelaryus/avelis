"""Margin calculation + associate profit distribution.

Tables:
- margin_calculation: project margin snapshot (6 indicators)
- quote_part_result: per-associate 3-step distribution (4 views)

Revision ID: 021
Revises: 020
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "021"
down_revision: Union[str, None] = "020"
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
        "margin_calculation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("calculation_date", sa.Date, nullable=False, index=True),
        sa.Column("period_label", sa.String(20), nullable=True),
        # Revenue
        sa.Column("ca_rf1", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("ca_rf2", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("ca_total", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        # Costs by category
        sa.Column("cc1_terrain", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc2_construction", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc3_materiaux", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc4_payroll", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc5_bbz", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc6_cff", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc7_inter_proj", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc8_compensation", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc9_assoc", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc10_commission", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc11_impots", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc14_frais_adm", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc15_frais_fin", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc16_divers", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        # Margins
        sa.Column("cout_direct", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("marge_brute", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cout_total", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("marge_nette", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("marge_operationnelle", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("detail_json", JSONB, nullable=True),
        *_system_columns(),
    )

    op.create_table(
        "quote_part_result",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("margin_calculation_id", UUID(as_uuid=True),
                  sa.ForeignKey("margin_calculation.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("pct_projet", sa.Numeric(7, 4), nullable=False),
        # 3 steps
        sa.Column("qp_brute", sa.Numeric(15, 2), nullable=False),
        sa.Column("cff_total_deducted", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("qp_after_cff", sa.Numeric(15, 2), nullable=False),
        sa.Column("cc9_withdrawals", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("cc10_commissions", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("qp_finale", sa.Numeric(15, 2), nullable=False),
        # Alternative views
        sa.Column("qp_without_cff", sa.Numeric(15, 2), nullable=True),
        sa.Column("cff_cost_delta", sa.Numeric(15, 2), nullable=True),
        sa.Column("qp_operationnelle", sa.Numeric(15, 2), nullable=True),
        *_system_columns(),
    )

    for table in ("margin_calculation", "quote_part_result"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in ("quote_part_result", "margin_calculation"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("quote_part_result")
    op.drop_table("margin_calculation")
