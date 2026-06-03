"""041 — ADV connected tables: credit tiers, echeancier, escrow, transitions, documents.

These tables power the DossierDetail tabs that were previously placeholder UI.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgcrypto for gen_random_uuid() on older PG versions
    # ── Credit Tier (5 disbursement tiers per credit dossier) ─────────────
    op.create_table(
        "credit_tier_c",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), sa.ForeignKey("dossier_adv.id"), nullable=False),
        sa.Column("tier_number", sa.Integer, nullable=False),
        sa.Column("tier_label", sa.String(30), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("routing", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="EN_ATTENTE"),
        sa.Column("expert_report_id", UUID(as_uuid=True), nullable=True),
        sa.Column("wire_order_id", UUID(as_uuid=True), nullable=True),
        sa.Column("request_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wire_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("debloque_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_credit_tier_c_dossier", "credit_tier_c", ["dossier_id"])

    # ── Expert Report ─────────────────────────────────────────────────────
    op.create_table(
        "expert_report_c",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), sa.ForeignKey("dossier_adv.id"), nullable=False),
        sa.Column("tier_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("expert_name", sa.String(255), nullable=False),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("completion_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("conformity", sa.Boolean, nullable=True),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column("document_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="RECU"),
        sa.Column("validated_by", sa.String(100), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # ── Wire Transfer Order ───────────────────────────────────────────────
    op.create_table(
        "wire_transfer_order_c",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), sa.ForeignKey("dossier_adv.id"), nullable=False),
        sa.Column("tier_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), server_default="EN_ATTENTE"),
        sa.Column("signature_date", sa.Date, nullable=True),
        sa.Column("scan_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # ── Echeancier ────────────────────────────────────────────────────────
    op.create_table(
        "echeancier_c",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), sa.ForeignKey("dossier_adv.id"), nullable=False),
        sa.Column("solde_rf1", sa.Numeric(15, 2), nullable=False),
        sa.Column("date_engagement", sa.Date, nullable=False),
        sa.Column("date_livraison_prevue", sa.Date, nullable=False),
        sa.Column("duree_mois", sa.Integer, nullable=False),
        sa.Column("frequence", sa.String(20), server_default="MENSUEL"),
        sa.Column("nb_echeances", sa.Integer, nullable=False),
        sa.Column("montant_echeance", sa.Numeric(15, 2), nullable=False),
        sa.Column("montant_derniere", sa.Numeric(15, 2), nullable=False),
        sa.Column("taux_penalite_annuel", sa.Numeric(5, 2), server_default="5.00"),
        sa.Column("status", sa.String(20), server_default="ACTIF"),
        sa.Column("total_paye", sa.Numeric(15, 2), server_default="0"),
        sa.Column("total_penalites", sa.Numeric(15, 2), server_default="0"),
        sa.Column("nb_retards", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_echeancier_c_dossier", "echeancier_c", ["dossier_id"])

    # ── Echeance (single installment) ─────────────────────────────────────
    op.create_table(
        "echeance_c",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("echeancier_id", UUID(as_uuid=True), sa.ForeignKey("echeancier_c.id"), nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("date_echeance", sa.Date, nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), server_default="A_VENIR"),
        sa.Column("date_paiement", sa.Date, nullable=True),
        sa.Column("montant_paye", sa.Numeric(15, 2), nullable=True),
        sa.Column("payment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("jours_retard", sa.Integer, server_default="0"),
        sa.Column("penalite_montant", sa.Numeric(15, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_echeance_c_echeancier", "echeance_c", ["echeancier_id"])
    op.create_index("ix_echeance_c_date", "echeance_c", ["date_echeance"])

    # ── Notary Escrow ─────────────────────────────────────────────────────
    op.create_table(
        "notary_escrow_c",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("notaire_name", sa.String(255), nullable=True),
        sa.Column("solde_transitoire", sa.Numeric(15, 2), server_default="0"),
        sa.Column("expected_5pct_reserve", sa.Numeric(15, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # ── Escrow Movement ───────────────────────────────────────────────────
    op.create_table(
        "escrow_movement_c",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("escrow_id", UUID(as_uuid=True), sa.ForeignKey("notary_escrow_c.id"), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), sa.ForeignKey("dossier_adv.id"), nullable=True),
        sa.Column("movement_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("movement_type", sa.String(10), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(15, 2), nullable=False),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("destination", sa.String(255), nullable=True),
        sa.Column("motif", sa.String(30), nullable=False),
        sa.Column("reference_cheque", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_escrow_movement_c_escrow", "escrow_movement_c", ["escrow_id"])
    op.create_index("ix_escrow_movement_c_dossier", "escrow_movement_c", ["dossier_id"])

    # ── Dossier Transition Log ────────────────────────────────────────────
    op.create_table(
        "dossier_transition_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), sa.ForeignKey("dossier_adv.id"), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=False),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("triggered_by", sa.String(200), nullable=True),
        sa.Column("blockers_overridden", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_transition_log_dossier", "dossier_transition_log", ["dossier_id"])

    # ── Document Checklist ────────────────────────────────────────────────
    op.create_table(
        "dossier_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("dossier_id", UUID(as_uuid=True), sa.ForeignKey("dossier_adv.id"), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("required", sa.Boolean, server_default="true"),
        sa.Column("received", sa.Boolean, server_default="false"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_url", sa.Text, nullable=True),
        sa.Column("relance_count", sa.Integer, server_default="0"),
        sa.Column("last_relance_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_dossier_document_dossier", "dossier_document", ["dossier_id"])


def downgrade():
    op.drop_table("dossier_document")
    op.drop_table("dossier_transition_log")
    op.drop_table("escrow_movement_c")
    op.drop_table("notary_escrow_c")
    op.drop_table("echeance_c")
    op.drop_table("echeancier_c")
    op.drop_table("wire_transfer_order_c")
    op.drop_table("expert_report_c")
    op.drop_table("credit_tier_c")
