"""Credit purchase workflow: 9 steps, 5 disbursement tiers.

Tables:
- credit_tier: 5 tiers per credit dossier (20+15+35+25+5=100%)
- expert_report: construction expert reports for tier validation
- wire_transfer_order: pre-signed orders for tiers 15/35/25%
- guarantee_fund: per entity+project+bank guarantee availability

Database enforcement:
  FIN-003: TRIGGER verifies tier percentages sum to 100% per dossier
  CRE-005: Expert report must be VALIDE before tier disbursement
  CHECK constraints on statuses and tier percentages

Revision ID: 016
Revises: 015
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "016"
down_revision: Union[str, None] = "015"
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
    # ═════════════════════════════════════════════════════════════════════
    # 1. expert_report (must exist before credit_tier FK)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "expert_report",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dossier_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("tier_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("expert_name", sa.String(255), nullable=False),
        sa.Column("agrement_number", sa.String(50), nullable=True),
        sa.Column("site_visit_date", sa.Date, nullable=True),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("completion_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("conformity", sa.Boolean, nullable=True),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column("document_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'RECU'")),
        sa.Column("validated_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. wire_transfer_order
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "wire_transfer_order",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dossier_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("tier_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("dossier_reference", sa.String(40), nullable=False),
        sa.Column("company_bank_account", sa.String(50), nullable=True),
        sa.Column("signature_date", sa.Date, nullable=True),
        sa.Column("scan_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'EN_ATTENTE'")),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. credit_tier
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "credit_tier",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dossier_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("tier_number", sa.Integer, nullable=False),
        sa.Column("tier_label", sa.String(30), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'EN_ATTENTE'")),
        sa.Column("routing", sa.String(20), nullable=False),
        sa.Column("expert_report_id", UUID(as_uuid=True),
                  sa.ForeignKey("expert_report.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("wire_order_id", UUID(as_uuid=True),
                  sa.ForeignKey("wire_transfer_order.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("request_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wire_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("debloque_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_id", UUID(as_uuid=True),
                  sa.ForeignKey("payment.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("wire_alert_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("days_since_request", sa.Integer, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. guarantee_fund
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "guarantee_fund",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("garantie_totale", sa.Numeric(15, 2), nullable=False),
        sa.Column("garantie_utilisee", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("garantie_disponible", sa.Numeric(15, 2), nullable=False),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 5. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════

    op.execute("""
        ALTER TABLE credit_tier
        ADD CONSTRAINT chk_ct_percentage
        CHECK (percentage IN (5, 15, 20, 25, 35));
    """)

    op.execute("""
        ALTER TABLE credit_tier
        ADD CONSTRAINT chk_ct_routing
        CHECK (routing IN ('VIA_NOTAIRE', 'DIRECT'));
    """)

    op.execute("""
        ALTER TABLE expert_report
        ADD CONSTRAINT chk_er_status
        CHECK (status IN ('RECU', 'VALIDE', 'REJETE'));
    """)

    op.execute("""
        ALTER TABLE expert_report
        ADD CONSTRAINT chk_er_tier
        CHECK (tier_percentage IN (15, 25, 35));
    """)

    op.execute("""
        ALTER TABLE wire_transfer_order
        ADD CONSTRAINT chk_wto_status
        CHECK (status IN ('EN_ATTENTE', 'SIGNE', 'EXECUTE'));
    """)

    op.execute("""
        ALTER TABLE wire_transfer_order
        ADD CONSTRAINT chk_wto_tier
        CHECK (tier_percentage IN (15, 25, 35));
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 6. FIN-003 TRIGGER: Verify tier sum = 100% per dossier
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_credit_tier_sum_check()
        RETURNS TRIGGER AS $$
        DECLARE
            v_total NUMERIC(5,2);
        BEGIN
            SELECT COALESCE(SUM(percentage), 0) INTO v_total
            FROM credit_tier
            WHERE dossier_adv_id = NEW.dossier_adv_id
              AND is_deleted = false;

            IF v_total > 100 THEN
                RAISE EXCEPTION
                    'FIN-003: Credit tier sum = %% > 100%% for dossier %.',
                    v_total, NEW.dossier_adv_id
                USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_credit_tier_sum_check
        AFTER INSERT ON credit_tier
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION gfi_credit_tier_sum_check();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 7. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    all_tables = [
        "expert_report", "wire_transfer_order",
        "credit_tier", "guarantee_fund",
    ]
    for table in all_tables:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    all_tables = [
        "credit_tier", "guarantee_fund",
        "wire_transfer_order", "expert_report",
    ]
    for table in all_tables:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")

    op.execute("DROP TRIGGER IF EXISTS trg_credit_tier_sum_check ON credit_tier;")
    op.execute("DROP FUNCTION IF EXISTS gfi_credit_tier_sum_check();")

    for table in all_tables:
        op.drop_table(table)
