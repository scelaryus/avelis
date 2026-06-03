"""Payment system with iron-clad RF integrity constraints.

Table: payment (all fields from CDC-ADV section 1.7)

Database enforcement (6 blocking constraints):
  PAY-C01: RF1 -> mode IN (CHEQUE, VIREMENT, CHEQUE_NOTAIRE)   [CHECK]
  PAY-C02: RF2 -> mode = ESPECES                                [CHECK]
  PAY-C03: SUM(RF1) <= prix_vente_rf1 per dossier               [TRIGGER]
  PAY-C04: SUM(RF2) <= prix_vente_rf2 per dossier               [TRIGGER]
  PAY-C05: SUM(RF1+RF2) <= prix_vente_reel per dossier          [TRIGGER]
  PAY-C06: REJETE/ANNULE payments are immutable                  [TRIGGER]

Revision ID: 014
Revises: 013
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "014"
down_revision: Union[str, None] = "013"
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
    # 1. CREATE TABLE
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "payment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Links
        sa.Column("dossier_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("client_id", UUID(as_uuid=True),
                  sa.ForeignKey("client.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("lot_id", UUID(as_uuid=True),
                  sa.ForeignKey("lot.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Classification
        sa.Column("type_paiement", sa.String(30), nullable=False),
        sa.Column("mode_reglement", sa.String(20), nullable=False),
        sa.Column("type_rf", sa.String(3), nullable=False),
        # Amount
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("devise", sa.String(3), nullable=False,
                  server_default=sa.text("'DZD'")),
        # Details
        sa.Column("reference_reglement", sa.String(100), nullable=True),
        sa.Column("banque_emettrice", sa.String(100), nullable=True),
        sa.Column("date_paiement", sa.Date, nullable=False, index=True),
        sa.Column("date_valeur", sa.Date, nullable=True),
        sa.Column("date_encaissement_effectif", sa.Date, nullable=True),
        # Status
        sa.Column("statut", sa.String(20), nullable=False,
                  server_default=sa.text("'EN_ATTENTE'")),
        # Credit tier
        sa.Column("palier_deblocage", sa.Numeric(5, 2), nullable=True),
        sa.Column("rapport_expert_id", UUID(as_uuid=True), nullable=True),
        # Justification
        sa.Column("piece_justificative_url", sa.Text, nullable=True),
        sa.Column("observations", sa.Text, nullable=True),
        # Maker/checker
        sa.Column("validated_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        # Accounting
        sa.Column("journal_entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal_entry.id", ondelete="SET NULL"),
                  nullable=True),
        # System
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. CHECK CONSTRAINTS (PAY-C01, PAY-C02, and basic validations)
    # ═════════════════════════════════════════════════════════════════════

    # PAY-C01: RF1 -> CHEQUE/VIREMENT/CHEQUE_NOTAIRE
    op.execute("""
        ALTER TABLE payment
        ADD CONSTRAINT chk_pay_c01_rf1_mode
        CHECK (
            type_rf != 'RF1'
            OR mode_reglement IN ('CHEQUE', 'VIREMENT', 'CHEQUE_NOTAIRE')
        );
    """)

    # PAY-C02: RF2 -> ESPECES
    op.execute("""
        ALTER TABLE payment
        ADD CONSTRAINT chk_pay_c02_rf2_mode
        CHECK (
            type_rf != 'RF2'
            OR mode_reglement = 'ESPECES'
        );
    """)

    # type_rf must be RF1 or RF2
    op.execute("""
        ALTER TABLE payment
        ADD CONSTRAINT chk_pay_rf_type
        CHECK (type_rf IN ('RF1', 'RF2'));
    """)

    # statut must be valid
    op.execute("""
        ALTER TABLE payment
        ADD CONSTRAINT chk_pay_statut
        CHECK (statut IN ('EN_ATTENTE', 'ENCAISSE', 'REJETE', 'ANNULE'));
    """)

    # montant must be positive
    op.execute("""
        ALTER TABLE payment
        ADD CONSTRAINT chk_pay_montant_positive
        CHECK (montant > 0);
    """)

    # mode_reglement must be valid
    op.execute("""
        ALTER TABLE payment
        ADD CONSTRAINT chk_pay_mode
        CHECK (mode_reglement IN ('CHEQUE', 'VIREMENT', 'ESPECES', 'CHEQUE_NOTAIRE'));
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 3. TRIGGER: PAY-C03/C04/C05 — overpayment prevention
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_payment_overflow_check()
        RETURNS TRIGGER AS $$
        DECLARE
            v_rf1_total NUMERIC(15,2);
            v_rf2_total NUMERIC(15,2);
            v_prix_rf1 NUMERIC(15,2);
            v_prix_rf2 NUMERIC(15,2);
            v_prix_reel NUMERIC(15,2);
        BEGIN
            -- Only check active payments
            IF NEW.statut NOT IN ('EN_ATTENTE', 'ENCAISSE') THEN
                RETURN NEW;
            END IF;

            -- Get dossier pricing
            SELECT prix_vente_rf1, COALESCE(prix_vente_rf2, 0), prix_vente_reel
            INTO v_prix_rf1, v_prix_rf2, v_prix_reel
            FROM dossier_adv WHERE id = NEW.dossier_adv_id;

            -- Current RF1 total (excluding this record if UPDATE)
            SELECT COALESCE(SUM(montant), 0) INTO v_rf1_total
            FROM payment
            WHERE dossier_adv_id = NEW.dossier_adv_id
              AND type_rf = 'RF1'
              AND statut IN ('EN_ATTENTE', 'ENCAISSE')
              AND is_deleted = false
              AND id != COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000');

            -- Current RF2 total
            SELECT COALESCE(SUM(montant), 0) INTO v_rf2_total
            FROM payment
            WHERE dossier_adv_id = NEW.dossier_adv_id
              AND type_rf = 'RF2'
              AND statut IN ('EN_ATTENTE', 'ENCAISSE')
              AND is_deleted = false
              AND id != COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000');

            -- Add the new payment amount to the correct bucket
            IF NEW.type_rf = 'RF1' THEN
                v_rf1_total := v_rf1_total + NEW.montant;
            ELSE
                v_rf2_total := v_rf2_total + NEW.montant;
            END IF;

            -- PAY-C03: RF1 overflow
            IF v_rf1_total > v_prix_rf1 THEN
                RAISE EXCEPTION
                    'PAY-C03: Depassement RF1 : total paiements RF1 = % DA > prix RF1 = % DA.',
                    ROUND(v_rf1_total, 2), ROUND(v_prix_rf1, 2)
                USING ERRCODE = 'P0001';
            END IF;

            -- PAY-C04: RF2 overflow
            IF v_rf2_total > v_prix_rf2 THEN
                RAISE EXCEPTION
                    'PAY-C04: Depassement RF2 : total paiements RF2 = % DA > prix RF2 = % DA.',
                    ROUND(v_rf2_total, 2), ROUND(v_prix_rf2, 2)
                USING ERRCODE = 'P0001';
            END IF;

            -- PAY-C05: Total overflow
            IF (v_rf1_total + v_rf2_total) > v_prix_reel THEN
                RAISE EXCEPTION
                    'PAY-C05: Depassement total : paiements = % DA > prix reel = % DA.',
                    ROUND(v_rf1_total + v_rf2_total, 2), ROUND(v_prix_reel, 2)
                USING ERRCODE = 'P0001';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_payment_overflow_check
        BEFORE INSERT OR UPDATE ON payment
        FOR EACH ROW EXECUTE FUNCTION gfi_payment_overflow_check();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 4. TRIGGER: PAY-C06 — immutability of REJETE/ANNULE
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_payment_immutable_check()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.statut IN ('REJETE', 'ANNULE') THEN
                -- Only allow soft-delete (is_deleted change)
                IF NEW.is_deleted != OLD.is_deleted THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION
                    'PAY-C06: Paiement % (statut %) est immutable. Creez un nouveau paiement.',
                    OLD.id, OLD.statut
                USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_payment_immutable
        BEFORE UPDATE ON payment
        FOR EACH ROW EXECUTE FUNCTION gfi_payment_immutable_check();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE TRIGGER trg_payment_updated_at
        BEFORE UPDATE ON payment
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
    """)
    op.execute("SELECT gfi_apply_no_delete_trigger('payment');")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_payment_updated_at ON payment;")
    op.execute("DROP TRIGGER IF EXISTS trg_payment_no_delete ON payment;")
    op.execute("DROP TRIGGER IF EXISTS trg_payment_immutable ON payment;")
    op.execute("DROP TRIGGER IF EXISTS trg_payment_overflow_check ON payment;")
    op.execute("DROP FUNCTION IF EXISTS gfi_payment_immutable_check();")
    op.execute("DROP FUNCTION IF EXISTS gfi_payment_overflow_check();")
    op.drop_table("payment")
