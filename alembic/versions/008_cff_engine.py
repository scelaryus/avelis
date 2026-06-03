"""CFF (Cout Fiscal Fictif) engine: bareme_timbre, cff_calculation, cff_imputation.

The CFF engine handles the most error-prone calculation in GFI because
distribution uses the EMITTING COMPANY's ownership, not the project's.

Tables:
- bareme_timbre: parameterizable stamp duty schedule (DAF-managed)
- cff_calculation: decomposed CFF results (5 components)
- cff_imputation: per-associate distribution

Triggers:
- updated_at on all 3 tables
- soft-delete (KT-10) on cff_calculation and cff_imputation
- CHECK: cff_imputation.percentage_source must be 'entreprise_associe'

Seed: default bareme_timbre for 2024+ (2.5% rate, 20K exemption, 2500 DA cap)

Revision ID: 008
Revises: 007
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"
BAREME_ID = "c1000000-0000-0000-0000-000000000001"


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
    # ═════════════════════════════════════════════════════════════════════
    # 1. bareme_timbre (system reference, no company_id)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "bareme_timbre",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("effective_from", sa.Date, nullable=False, index=True),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column("exemption_threshold", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("20000")),
        sa.Column("rate_percent", sa.Numeric(5, 2), nullable=False,
                  server_default=sa.text("2.50")),
        sa.Column("cap_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("loi_reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. cff_calculation (GFIBase — company_id = EMITTER)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "cff_calculation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Source transaction
        sa.Column("financial_transaction_id", UUID(as_uuid=True),
                  sa.ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Entities
        sa.Column("receiver_company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        # Invoice
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("invoice_ref", sa.String(100), nullable=True),
        sa.Column("montant_ht", sa.Numeric(15, 2), nullable=False),
        # 5-step decomposition
        sa.Column("tva_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("tva_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("tap_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("tap_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("ibs_base", sa.Numeric(15, 2), nullable=False),
        sa.Column("ibs_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("ibs_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("ttc_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("stamp_duty_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("stamp_duty_exempt", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        # Total
        sa.Column("cff_total", sa.Numeric(15, 2), nullable=False),
        # Verifications
        sa.Column("v6_source_verified", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("v7_yamina_verified", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'CALCULATED'")),
        # System columns
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. cff_imputation (GFIBase — company_id = EMITTER)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "cff_imputation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("cff_calculation_id", UUID(as_uuid=True),
                  sa.ForeignKey("cff_calculation.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("percentage_used", sa.Numeric(7, 4), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("percentage_source", sa.String(30), nullable=False,
                  server_default=sa.text("'entreprise_associe'")),
        # System columns
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. CHECK CONSTRAINT: percentage_source must be 'entreprise_associe'
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE cff_imputation
        ADD CONSTRAINT chk_cff_imp_source
        CHECK (percentage_source = 'entreprise_associe');
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("bareme_timbre", "cff_calculation", "cff_imputation"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)

    for table in ("cff_calculation", "cff_imputation"):
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ═════════════════════════════════════════════════════════════════════
    # 6. SEED — default bareme_timbre (2024+)
    # ═════════════════════════════════════════════════════════════════════
    op.execute(f"""
        INSERT INTO bareme_timbre (
            id, effective_from, effective_to,
            exemption_threshold, rate_percent, cap_amount,
            loi_reference, notes
        ) VALUES (
            '{BAREME_ID}', '2024-01-01', NULL,
            20000, 2.50, 2500,
            'Loi de finances 2024',
            'Default schedule: 2.5% of TTC, exempt if TTC <= 20000 DA, '
            'capped at 2500 DA. DAF to update when loi de finances changes.'
        );
    """)


def downgrade() -> None:
    for table in ("cff_imputation", "cff_calculation", "bareme_timbre"):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};"
        )
    for table in ("cff_imputation", "cff_calculation"):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};"
        )
    op.drop_table("cff_imputation")
    op.drop_table("cff_calculation")
    op.drop_table("bareme_timbre")
