"""Fonds propres (own-funds) payment workflow.

Tables:
- echeancier: installment schedule header
- echeance: individual installments with penalty tracking

Database enforcement:
  FP-001: 30% threshold check (Python engine)
  FP-003: CHECK installments are RF1 cheque only (via payment constraints)
  FP-004: Penalty formula enforced in monitoring job
  FP-005: DEFAUT_PAIEMENT blocks all lot operations
  Installment status CHECK constraint
  Frequency CHECK constraint

Revision ID: 017
Revises: 016
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "017"
down_revision: Union[str, None] = "016"
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
    # 1. echeancier
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "echeancier",
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
                  nullable=False),
        sa.Column("solde_rf1", sa.Numeric(15, 2), nullable=False),
        sa.Column("date_engagement", sa.Date, nullable=False),
        sa.Column("date_livraison_prevue", sa.Date, nullable=False),
        sa.Column("duree_mois", sa.Integer, nullable=False),
        sa.Column("frequence", sa.String(20), nullable=False,
                  server_default=sa.text("'MENSUEL'")),
        sa.Column("nb_echeances", sa.Integer, nullable=False),
        sa.Column("montant_echeance", sa.Numeric(15, 2), nullable=False),
        sa.Column("montant_derniere", sa.Numeric(15, 2), nullable=False),
        sa.Column("taux_penalite_annuel", sa.Numeric(5, 2), nullable=False,
                  server_default=sa.text("5.00")),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'ACTIF'")),
        sa.Column("total_paye", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("total_penalites", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("nb_retards", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. echeance
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "echeance",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("echeancier_id", UUID(as_uuid=True),
                  sa.ForeignKey("echeancier.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("date_echeance", sa.Date, nullable=False, index=True),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'A_VENIR'")),
        sa.Column("date_paiement", sa.Date, nullable=True),
        sa.Column("montant_paye", sa.Numeric(15, 2), nullable=True),
        sa.Column("payment_id", UUID(as_uuid=True),
                  sa.ForeignKey("payment.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("jours_retard", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        sa.Column("penalite_montant", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        # Relance flags
        sa.Column("relance_j7_sent", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("relance_j3_sent", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("relance_j1_sent", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("relance_j7r_sent", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("relance_j15r_sent", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("relance_j30r_sent", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("mise_en_demeure_sent", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE echeancier
        ADD CONSTRAINT chk_ech_frequence
        CHECK (frequence IN ('MENSUEL', 'BIMENSUEL'));
    """)

    op.execute("""
        ALTER TABLE echeancier
        ADD CONSTRAINT chk_ech_status
        CHECK (status IN ('ACTIF', 'TERMINE', 'DEFAUT'));
    """)

    op.execute("""
        ALTER TABLE echeance
        ADD CONSTRAINT chk_echeance_status
        CHECK (status IN ('A_VENIR', 'DUE', 'PAYEE', 'EN_RETARD', 'DEFAUT'));
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 4. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("echeancier", "echeance"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in ("echeance", "echeancier"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("echeance")
    op.drop_table("echeancier")
