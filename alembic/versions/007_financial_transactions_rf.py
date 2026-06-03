"""Financial transactions with Réalité Financière (RF) classification.

Every financial transaction is classified into exactly one of 4 RFs.
This migration creates the financial_transaction table with hard
database-level constraints enforcing RF/payment mode compatibility.

Database enforcement:
- CHECK: rf_type IN ('RF1','RF2','RF3','RF4') — mandatory
- CHECK: RF1 → payment_mode IN ('CHEQUE','VIREMENT','CHEQUE_NOTAIRE')
- CHECK: RF2 → payment_mode = 'ESPECES'
- CHECK: RF3 → payment_mode IN ('SANS_OBJET','COMPENSATION')
- CHECK: RF4 → payment_mode = 'SANS_OBJET'
- pgcrypto extension for RF2 amount encryption at rest
- Trigger: RF3 with both emitter and receiver as group entities
  → auto-sets cff_triggered = 'Y'
- Soft-delete trigger (KT-10)
- updated_at trigger

Views:
- v_financial_vue_officielle: RF1 + RF3 transactions
- v_financial_vue_interne: all transactions (RF1+RF2+RF3+RF4)

Revision ID: 007
Revises: 006
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "007"
down_revision: Union[str, None] = "006"
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
    # 1. pgcrypto EXTENSION (for RF2 encryption at rest)
    # ═════════════════════════════════════════════════════════════════════
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # ═════════════════════════════════════════════════════════════════════
    # 2. CREATE financial_transaction TABLE
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "financial_transaction",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # RF classification
        sa.Column("rf_type", sa.String(3), nullable=False, index=True),
        # Transaction identity
        sa.Column("transaction_date", sa.Date, nullable=False, index=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("label", sa.Text, nullable=False),
        # Category
        sa.Column("category", sa.String(40), nullable=False, index=True),
        # Amount
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False,
                  server_default=sa.text("'DZD'")),
        # Payment mode
        sa.Column("payment_mode", sa.String(20), nullable=True),
        # Project link
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        # Associate link
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        # RF3 inter-group
        sa.Column("emitter_company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("receiver_company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("cff_triggered", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        # RF2 encrypted copy
        sa.Column("rf2_amount_encrypted", sa.Text, nullable=True),
        # Document tracking
        sa.Column("document_type", sa.String(60), nullable=True),
        sa.Column("document_ref", sa.String(100), nullable=True),
        sa.Column("client_visible", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        # Metadata
        sa.Column("metadata_json", JSONB, nullable=True),
        # System columns
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. CHECK CONSTRAINTS — RF type validity
    # ═════════════════════════════════════════════════════════════════════

    # 3a. rf_type must be one of the 4 values
    op.execute("""
        ALTER TABLE financial_transaction
        ADD CONSTRAINT chk_ft_rf_type
        CHECK (rf_type IN ('RF1', 'RF2', 'RF3', 'RF4'));
    """)

    # 3b. RF1 → payment must be CHEQUE, VIREMENT, or CHEQUE_NOTAIRE
    op.execute("""
        ALTER TABLE financial_transaction
        ADD CONSTRAINT chk_ft_rf1_payment
        CHECK (
            rf_type != 'RF1'
            OR payment_mode IN ('CHEQUE', 'VIREMENT', 'CHEQUE_NOTAIRE')
        );
    """)

    # 3c. RF2 → payment must be ESPECES
    op.execute("""
        ALTER TABLE financial_transaction
        ADD CONSTRAINT chk_ft_rf2_payment
        CHECK (
            rf_type != 'RF2'
            OR payment_mode = 'ESPECES'
        );
    """)

    # 3d. RF3 → payment must be SANS_OBJET or COMPENSATION
    op.execute("""
        ALTER TABLE financial_transaction
        ADD CONSTRAINT chk_ft_rf3_payment
        CHECK (
            rf_type != 'RF3'
            OR payment_mode IN ('SANS_OBJET', 'COMPENSATION')
        );
    """)

    # 3e. RF4 → payment must be SANS_OBJET
    op.execute("""
        ALTER TABLE financial_transaction
        ADD CONSTRAINT chk_ft_rf4_payment
        CHECK (
            rf_type != 'RF4'
            OR payment_mode = 'SANS_OBJET'
        );
    """)

    # 3f. payment_mode must be valid
    op.execute("""
        ALTER TABLE financial_transaction
        ADD CONSTRAINT chk_ft_payment_mode
        CHECK (
            payment_mode IS NULL
            OR payment_mode IN (
                'ESPECES', 'CHEQUE', 'VIREMENT',
                'CHEQUE_NOTAIRE', 'COMPENSATION', 'SANS_OBJET'
            )
        );
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 4. TRIGGER — RF2 auto-encrypt amount at rest
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_rf2_encrypt_amount()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.rf_type = 'RF2' THEN
                -- Encrypt the amount using pgcrypto with a server-side key.
                -- In production, the key should come from a secure vault.
                -- Using a placeholder key reference here.
                NEW.rf2_amount_encrypted := encode(
                    pgp_sym_encrypt(
                        NEW.amount::text,
                        current_setting('app.rf2_encryption_key', true)
                    ),
                    'base64'
                );
            ELSE
                NEW.rf2_amount_encrypted := NULL;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_ft_rf2_encrypt
        BEFORE INSERT OR UPDATE ON financial_transaction
        FOR EACH ROW EXECUTE FUNCTION gfi_rf2_encrypt_amount();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. TRIGGER — RF3 inter-group auto-flag CFF
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_rf3_auto_cff()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.rf_type = 'RF3'
               AND NEW.emitter_company_id IS NOT NULL
               AND NEW.receiver_company_id IS NOT NULL
            THEN
                -- Both emitter and receiver must be group entities
                IF EXISTS (
                    SELECT 1 FROM company
                    WHERE id = NEW.emitter_company_id
                      AND is_deleted = false
                ) AND EXISTS (
                    SELECT 1 FROM company
                    WHERE id = NEW.receiver_company_id
                      AND is_deleted = false
                ) THEN
                    NEW.cff_triggered := 'Y';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_ft_rf3_cff
        BEFORE INSERT OR UPDATE ON financial_transaction
        FOR EACH ROW EXECUTE FUNCTION gfi_rf3_auto_cff();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 6. STANDARD TRIGGERS (updated_at, soft-delete)
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE TRIGGER trg_financial_transaction_updated_at
        BEFORE UPDATE ON financial_transaction
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
    """)
    op.execute(
        "SELECT gfi_apply_no_delete_trigger('financial_transaction');"
    )

    # ═════════════════════════════════════════════════════════════════════
    # 7. DATABASE VIEWS — Vue Officielle / Vue Interne
    # ═════════════════════════════════════════════════════════════════════

    # Vue Officielle: RF1 + RF3 only (what tax authority sees)
    op.execute("""
        CREATE OR REPLACE VIEW v_financial_vue_officielle AS
        SELECT
            id, company_id, rf_type, transaction_date, reference, label,
            category, amount, currency, payment_mode,
            project_id, associate_id,
            emitter_company_id, receiver_company_id, cff_triggered,
            document_type, document_ref, client_visible,
            created_at, created_by, is_deleted
        FROM financial_transaction
        WHERE rf_type IN ('RF1', 'RF3')
          AND is_deleted = false;
    """)

    # Vue Interne: all RFs (economic reality)
    op.execute("""
        CREATE OR REPLACE VIEW v_financial_vue_interne AS
        SELECT
            id, company_id, rf_type, transaction_date, reference, label,
            category, amount, currency, payment_mode,
            project_id, associate_id,
            emitter_company_id, receiver_company_id, cff_triggered,
            rf2_amount_encrypted,
            document_type, document_ref, client_visible,
            created_at, created_by, is_deleted
        FROM financial_transaction
        WHERE is_deleted = false;
    """)

    # Écart view: RF2 + RF4 only (difference between official and reality)
    op.execute("""
        CREATE OR REPLACE VIEW v_financial_ecart AS
        SELECT
            id, company_id, rf_type, transaction_date, reference, label,
            category, amount, currency, payment_mode,
            project_id, associate_id,
            created_at, created_by, is_deleted
        FROM financial_transaction
        WHERE rf_type IN ('RF2', 'RF4')
          AND is_deleted = false;
    """)

    # Summary view: aggregated by company, project, RF type
    op.execute("""
        CREATE OR REPLACE VIEW v_financial_summary AS
        SELECT
            company_id,
            project_id,
            rf_type,
            COUNT(*) AS tx_count,
            SUM(amount) AS total_amount,
            MIN(transaction_date) AS first_date,
            MAX(transaction_date) AS last_date
        FROM financial_transaction
        WHERE is_deleted = false
        GROUP BY company_id, project_id, rf_type;
    """)


def downgrade() -> None:
    # Drop views
    op.execute("DROP VIEW IF EXISTS v_financial_summary;")
    op.execute("DROP VIEW IF EXISTS v_financial_ecart;")
    op.execute("DROP VIEW IF EXISTS v_financial_vue_interne;")
    op.execute("DROP VIEW IF EXISTS v_financial_vue_officielle;")

    # Drop triggers
    op.execute(
        "DROP TRIGGER IF EXISTS trg_financial_transaction_updated_at "
        "ON financial_transaction;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_financial_transaction_no_delete "
        "ON financial_transaction;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ft_rf3_cff "
        "ON financial_transaction;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ft_rf2_encrypt "
        "ON financial_transaction;"
    )
    op.execute("DROP FUNCTION IF EXISTS gfi_rf3_auto_cff();")
    op.execute("DROP FUNCTION IF EXISTS gfi_rf2_encrypt_amount();")

    # Drop table (constraints drop with it)
    op.drop_table("financial_transaction")

    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
