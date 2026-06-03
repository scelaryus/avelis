"""ADV (Administration des Ventes) dossier system.

Tables:
- client: real estate buyers/prospects
- dossier_adv: central sales dossier (16-state machine)
- dossier_payment: RF1/RF2 payment records
- dossier_document: required document checklist
- dossier_transition: immutable state change log

Database enforcement:
- CHECK: statut_global in 16 valid states
- CHECK: type_paiement in valid payment types
- CHECK: RF2 payment mode must be ESPECES
- CHECK: RF1 payment mode must be CHEQUE/VIREMENT/CHEQUE_NOTAIRE
- RF2 price encryption trigger
- Soft-delete (KT-10) on all tables

Revision ID: 013
Revises: 012
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "013"
down_revision: Union[str, None] = "012"
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
    # 1. client
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "client",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("nif_client", sa.String(30), nullable=True),
        sa.Column("crm_status", sa.String(20), nullable=False,
                  server_default=sa.text("'PROSPECT'")),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("documents_status", JSONB, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. dossier_adv
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "dossier_adv",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Identity
        sa.Column("numero_dossier", sa.String(40), unique=True,
                  nullable=False, index=True),
        # Links
        sa.Column("client_id", UUID(as_uuid=True),
                  sa.ForeignKey("client.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("lot_id", UUID(as_uuid=True),
                  sa.ForeignKey("lot.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("devis_id", UUID(as_uuid=True), nullable=True),
        # Payment type
        sa.Column("type_paiement", sa.String(20), nullable=False),
        # Pricing
        sa.Column("prix_vente_rf1", sa.Numeric(15, 2), nullable=False),
        sa.Column("prix_vente_rf2", sa.Numeric(15, 2), nullable=True),
        sa.Column("prix_vente_rf2_encrypted", sa.Text, nullable=True),
        sa.Column("prix_vente_reel", sa.Numeric(15, 2), nullable=False),
        # State machine
        sa.Column("statut_global", sa.String(30), nullable=False,
                  index=True, server_default=sa.text("'DISPONIBLE'")),
        # RF2 securization
        sa.Column("statut_rf2", sa.String(30), nullable=True),
        sa.Column("montant_rf2_securise", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("montant_rf2_restant", sa.Numeric(15, 2), nullable=True),
        sa.Column("rf2_last_payment_at", sa.DateTime(timezone=True), nullable=True),
        # Dates
        sa.Column("date_reservation", sa.Date, nullable=True),
        sa.Column("date_engagement", sa.Date, nullable=True),
        sa.Column("date_signature_contrat", sa.Date, nullable=True),
        sa.Column("date_livraison_prevue", sa.Date, nullable=True),
        sa.Column("date_livraison_effective", sa.Date, nullable=True),
        # People
        sa.Column("agent_commercial_id", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("responsable_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("notaire_id", UUID(as_uuid=True), nullable=True),
        sa.Column("banque_id", UUID(as_uuid=True), nullable=True),
        # Credit
        sa.Column("montant_credit", sa.Numeric(15, 2), nullable=True),
        sa.Column("montant_apport", sa.Numeric(15, 2), nullable=True),
        sa.Column("fond_garantie_disponible", sa.Numeric(15, 2), nullable=True),
        sa.Column("credit_rejection_reason", sa.Text, nullable=True),
        # Own-funds
        sa.Column("montant_total_verse", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("seuil_30_pct_atteint", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        # Installment
        sa.Column("echeancier_id", UUID(as_uuid=True), nullable=True),
        # Documents
        sa.Column("documents_checklist", JSONB, nullable=True),
        # Notes
        sa.Column("notes", sa.Text, nullable=True),
        # System
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. dossier_payment
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "dossier_payment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dossier_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("payment_date", sa.Date, nullable=False, index=True),
        sa.Column("rf_type", sa.String(3), nullable=False),
        sa.Column("payment_mode", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("receipt_type", sa.String(20), nullable=True),
        sa.Column("receipt_ref", sa.String(100), nullable=True),
        sa.Column("receipt_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("payment_category", sa.String(30), nullable=False),
        sa.Column("credit_tier_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'ENREGISTRE'")),
        sa.Column("justification_path", sa.Text, nullable=True),
        sa.Column("journal_entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal_entry.id", ondelete="SET NULL"),
                  nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. dossier_document
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "dossier_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dossier_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("document_type", sa.String(60), nullable=False),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'REQUIS'")),
        sa.Column("received_date", sa.Date, nullable=True),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("last_relance_date", sa.Date, nullable=True),
        sa.Column("relance_count", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 5. dossier_transition (immutable state change log)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "dossier_transition",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dossier_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("from_status", sa.String(30), nullable=False),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("transition_trigger", sa.String(60), nullable=True),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transitioned_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("preconditions_met", JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 6. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════

    op.execute("""
        ALTER TABLE dossier_adv
        ADD CONSTRAINT chk_dadv_statut
        CHECK (statut_global IN (
            'DISPONIBLE', 'PRE_RESERVE', 'RESERVE', 'ENGAGE',
            'EN_COURS_CREDIT', 'EN_COURS_FONDS_PROPRES',
            'REJETE_BANQUE', 'PAIEMENT_EN_COURS',
            'CONTRAT_SIGNE', 'DEBLOCAGE_EN_COURS',
            'LIVRAISON_PRETE', 'LIVRE', 'CLOTURE',
            'DEFAUT_PAIEMENT',
            'ANNULE', 'ANNULE_RESERVATION', 'ANNULE_ENGAGEMENT',
            'INDISPONIBLE'
        ));
    """)

    op.execute("""
        ALTER TABLE dossier_adv
        ADD CONSTRAINT chk_dadv_type_paiement
        CHECK (type_paiement IN (
            'SPOT', 'CREDIT_BANCAIRE', 'FONDS_PROPRES', 'MIXTE'
        ));
    """)

    op.execute("""
        ALTER TABLE dossier_adv
        ADD CONSTRAINT chk_dadv_statut_rf2
        CHECK (
            statut_rf2 IS NULL
            OR statut_rf2 IN ('NON_SECURISE', 'PARTIELLEMENT_SECURISE', 'SECURISE')
        );
    """)

    # RF payment mode constraints on dossier_payment
    op.execute("""
        ALTER TABLE dossier_payment
        ADD CONSTRAINT chk_dpay_rf1_mode
        CHECK (
            rf_type != 'RF1'
            OR payment_mode IN ('CHEQUE', 'VIREMENT', 'CHEQUE_NOTAIRE')
        );
    """)

    op.execute("""
        ALTER TABLE dossier_payment
        ADD CONSTRAINT chk_dpay_rf2_mode
        CHECK (
            rf_type != 'RF2'
            OR payment_mode = 'ESPECES'
        );
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 7. RF2 ENCRYPTION TRIGGER on dossier_adv
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_dossier_rf2_encrypt()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.prix_vente_rf2 IS NOT NULL AND NEW.prix_vente_rf2 > 0 THEN
                NEW.prix_vente_rf2_encrypted := encode(
                    pgp_sym_encrypt(
                        NEW.prix_vente_rf2::text,
                        current_setting('app.rf2_encryption_key', true)
                    ),
                    'base64'
                );
                NEW.prix_vente_reel := COALESCE(NEW.prix_vente_rf1, 0) + NEW.prix_vente_rf2;
            ELSE
                NEW.prix_vente_rf2_encrypted := NULL;
                NEW.prix_vente_reel := COALESCE(NEW.prix_vente_rf1, 0);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_dossier_adv_rf2_encrypt
        BEFORE INSERT OR UPDATE ON dossier_adv
        FOR EACH ROW EXECUTE FUNCTION gfi_dossier_rf2_encrypt();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 8. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    all_tables = [
        "client", "dossier_adv", "dossier_payment",
        "dossier_document", "dossier_transition",
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
        "dossier_transition", "dossier_document",
        "dossier_payment", "dossier_adv", "client",
    ]
    for table in all_tables:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_dossier_adv_rf2_encrypt ON dossier_adv;"
    )
    op.execute("DROP FUNCTION IF EXISTS gfi_dossier_rf2_encrypt();")

    for table in all_tables:
        op.drop_table(table)
