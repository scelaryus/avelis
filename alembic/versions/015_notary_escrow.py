"""Notary escrow account system.

Tables:
- notary_escrow: one per notary per project per entity
- escrow_movement: individual credits/debits
- etat_detaille: global cheque decomposition headers
- etat_detaille_line: per-dossier allocations

Database enforcement:
  FIN-005:     TRIGGER blocks debit if balance would go negative
  NOTAIRE-001: TRIGGER validates sum(lines) == montant_global on etat_detaille
  Movement type CHECK: CREDIT or DEBIT
  Motif CHECK: valid coded reasons
  Soft-delete (KT-10) on all tables

Revision ID: 015
Revises: 014
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "015"
down_revision: Union[str, None] = "014"
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
    # 1. notary_escrow
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "notary_escrow",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("notaire_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("solde_transitoire", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("expected_5pct_reserve", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("last_zero_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_48h_active", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("notaire_name", sa.String(255), nullable=True),
        *_system_columns(),
    )

    # Unique: one escrow per notary + project + entity
    op.execute("""
        ALTER TABLE notary_escrow
        ADD CONSTRAINT uq_escrow_notaire_project_company
        UNIQUE (notaire_id, project_id, company_id);
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 2. etat_detaille (must come before escrow_movement for FK)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "etat_detaille",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("escrow_id", UUID(as_uuid=True),
                  sa.ForeignKey("notary_escrow.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("cheque_global_reference", sa.String(100), nullable=False),
        sa.Column("montant_global", sa.Numeric(15, 2), nullable=False),
        sa.Column("date_cheque", sa.Date, nullable=False),
        sa.Column("notaire_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column("sum_lignes", sa.Numeric(15, 2), nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. escrow_movement
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "escrow_movement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("escrow_id", UUID(as_uuid=True),
                  sa.ForeignKey("notary_escrow.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("movement_date", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("movement_type", sa.String(10), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(15, 2), nullable=False),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("destination", sa.String(255), nullable=True),
        sa.Column("dossier_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("motif", sa.String(30), nullable=False),
        sa.Column("reference_cheque", sa.String(100), nullable=True),
        sa.Column("etat_detaille_id", UUID(as_uuid=True),
                  sa.ForeignKey("etat_detaille.id", ondelete="SET NULL"),
                  nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. etat_detaille_line
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "etat_detaille_line",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("etat_detaille_id", UUID(as_uuid=True),
                  sa.ForeignKey("etat_detaille.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dossier_adv_id", UUID(as_uuid=True),
                  sa.ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("client_nom", sa.String(255), nullable=False),
        sa.Column("lot_reference", sa.String(50), nullable=False),
        sa.Column("montant_impute", sa.Numeric(15, 2), nullable=False),
        sa.Column("motif", sa.String(60), nullable=False),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 5. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════

    op.execute("""
        ALTER TABLE escrow_movement
        ADD CONSTRAINT chk_escrow_mv_type
        CHECK (movement_type IN ('CREDIT', 'DEBIT'));
    """)

    op.execute("""
        ALTER TABLE escrow_movement
        ADD CONSTRAINT chk_escrow_mv_motif
        CHECK (motif IN (
            'VSP_20PCT', 'PALIER_5PCT', 'LIBERATION_20PCT', 'LIBERATION_5PCT',
            'PALIER_15PCT', 'PALIER_35PCT', 'PALIER_25PCT', 'AUTRE'
        ));
    """)

    op.execute("""
        ALTER TABLE escrow_movement
        ADD CONSTRAINT chk_escrow_mv_montant
        CHECK (montant > 0);
    """)

    op.execute("""
        ALTER TABLE etat_detaille_line
        ADD CONSTRAINT chk_edl_montant
        CHECK (montant_impute > 0);
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 6. TRIGGER: FIN-005 — escrow balance can never go negative
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_escrow_balance_check()
        RETURNS TRIGGER AS $$
        DECLARE
            v_current NUMERIC(15,2);
        BEGIN
            IF NEW.movement_type = 'DEBIT' THEN
                SELECT solde_transitoire INTO v_current
                FROM notary_escrow WHERE id = NEW.escrow_id;

                IF v_current - NEW.montant < 0 THEN
                    RAISE EXCEPTION
                        'FIN-005: Solde sequestre deviendrait negatif. '
                        'Solde actuel = % DA, debit = % DA.',
                        v_current, NEW.montant
                    USING ERRCODE = 'P0001';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_escrow_movement_balance_check
        BEFORE INSERT ON escrow_movement
        FOR EACH ROW EXECUTE FUNCTION gfi_escrow_balance_check();
    """)

    # Balance auto-update trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_escrow_update_balance()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.movement_type = 'CREDIT' THEN
                UPDATE notary_escrow
                SET solde_transitoire = solde_transitoire + NEW.montant
                WHERE id = NEW.escrow_id;
            ELSE
                UPDATE notary_escrow
                SET solde_transitoire = solde_transitoire - NEW.montant
                WHERE id = NEW.escrow_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_escrow_movement_update_balance
        AFTER INSERT ON escrow_movement
        FOR EACH ROW EXECUTE FUNCTION gfi_escrow_update_balance();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 7. TRIGGER: NOTAIRE-001 — etat detaille sum validation
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_etat_detaille_sum_check()
        RETURNS TRIGGER AS $$
        DECLARE
            v_sum NUMERIC(15,2);
            v_global NUMERIC(15,2);
        BEGIN
            IF NEW.status = 'VALIDATED' THEN
                SELECT COALESCE(SUM(montant_impute), 0) INTO v_sum
                FROM etat_detaille_line
                WHERE etat_detaille_id = NEW.id AND is_deleted = false;

                v_global := NEW.montant_global;

                IF v_sum != v_global THEN
                    RAISE EXCEPTION
                        'NOTAIRE-001: Ecart etat detaille : somme lignes = % DA '
                        '!= montant cheque = % DA.',
                        v_sum, v_global
                    USING ERRCODE = 'P0001';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_etat_detaille_sum_check
        AFTER INSERT OR UPDATE ON etat_detaille
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION gfi_etat_detaille_sum_check();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 8. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    all_tables = [
        "notary_escrow", "escrow_movement",
        "etat_detaille", "etat_detaille_line",
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
        "etat_detaille_line", "escrow_movement",
        "etat_detaille", "notary_escrow",
    ]
    for table in all_tables:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")

    op.execute("DROP TRIGGER IF EXISTS trg_etat_detaille_sum_check ON etat_detaille;")
    op.execute("DROP TRIGGER IF EXISTS trg_escrow_movement_balance_check ON escrow_movement;")
    op.execute("DROP TRIGGER IF EXISTS trg_escrow_movement_update_balance ON escrow_movement;")
    op.execute("DROP FUNCTION IF EXISTS gfi_etat_detaille_sum_check();")
    op.execute("DROP FUNCTION IF EXISTS gfi_escrow_balance_check();")
    op.execute("DROP FUNCTION IF EXISTS gfi_escrow_update_balance();")

    for table in all_tables:
        op.drop_table(table)
