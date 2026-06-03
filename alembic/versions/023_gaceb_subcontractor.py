"""GACEB subcontractor: 120M advance, work situations, vehicle circuit, RAP.

Tables:
- gaceb_advance: in-kind advance tracking (120M + vehicles + apartments)
- work_situation: gross/deduction/net with 4-column display
- vehicle: 5-step circuit from purchase to resale

Seeds:
- 120M AMENFORT material advance on EDEN
- Range Rover (Ahmed, 4M) and VW Passat (Yazid, 6.5M)

Revision ID: 023
Revises: 022
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"
EDEN_PROJECT_ID = "30000000-0000-0000-0000-000000000001"
ETS_DK_ID = "10000000-0000-0000-0000-000000000001"
AHMED_ID = "20000000-0000-0000-0000-000000000001"
YAZID_ID = "20000000-0000-0000-0000-000000000003"


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
    # 1. gaceb_advance
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "gaceb_advance",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("advance_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("montant_initial", sa.Numeric(15, 2), nullable=False),
        sa.Column("montant_deduit", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("solde_restant", sa.Numeric(15, 2), nullable=False),
        sa.Column("journal_entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal_entry.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("account_debit", sa.String(20), nullable=True),
        sa.Column("account_credit", sa.String(20), nullable=True),
        sa.Column("impact_tresorerie", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. work_situation
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "work_situation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("situation_number", sa.Integer, nullable=False),
        sa.Column("situation_date", sa.Date, nullable=False, index=True),
        sa.Column("subcontractor_name", sa.String(255), nullable=False,
                  server_default=sa.text("'GACEB Abderazak'")),
        sa.Column("montant_brut", sa.Numeric(15, 2), nullable=False),
        sa.Column("deduction_avance", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("deduction_vehicules", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("deduction_appartements", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("retention_garantie_5pct", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("net_cash_verse", sa.Numeric(15, 2), nullable=False),
        sa.Column("solde_avance_apres", sa.Numeric(15, 2), nullable=True),
        sa.Column("contract_ref", sa.String(100), nullable=True),
        sa.Column("completion_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'SOUMISE'")),
        sa.Column("validated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_url", sa.Text, nullable=True),
        sa.Column("journal_entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal_entry.id", ondelete="SET NULL"),
                  nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. vehicle
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "vehicle",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("chassis_number", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("make", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("plate_number", sa.String(20), nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("purchase_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("purchase_project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="SET NULL"), nullable=True),
        sa.Column("purchase_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("registered_to_associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="SET NULL"), nullable=True),
        sa.Column("registration_date", sa.Date, nullable=True),
        sa.Column("cession_date", sa.Date, nullable=True),
        sa.Column("cession_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("cession_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("deduction_date", sa.Date, nullable=True),
        sa.Column("deduction_situation_id", UUID(as_uuid=True),
                  sa.ForeignKey("work_situation.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deduction_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("resale_date", sa.Date, nullable=True),
        sa.Column("resale_buyer", sa.String(255), nullable=True),
        sa.Column("resale_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("current_step", sa.String(20), nullable=False,
                  server_default=sa.text("'ACHETE'")),
        sa.Column("history", JSONB, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE vehicle
        ADD CONSTRAINT chk_vehicle_step
        CHECK (current_step IN ('ACHETE', 'IMMATRICULE', 'CEDE', 'DEDUIT', 'REVENDU'));
    """)

    op.execute("""
        ALTER TABLE work_situation
        ADD CONSTRAINT chk_ws_status
        CHECK (status IN ('SOUMISE', 'VALIDEE', 'PAYEE'));
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("gaceb_advance", "work_situation", "vehicle"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ═════════════════════════════════════════════════════════════════════
    # 6. SEED — 120M advance on EDEN
    # ═════════════════════════════════════════════════════════════════════
    op.execute(f"""
        INSERT INTO gaceb_advance (
            id, company_id, project_id, advance_type, description,
            montant_initial, montant_deduit, solde_restant,
            account_debit, account_credit, impact_tresorerie,
            created_by
        ) VALUES (
            'f4000000-0000-0000-0000-000000000001',
            '{ETS_DK_ID}', '{EDEN_PROJECT_ID}', 'MATERIEL_120M',
            'Avance materiel AMENFORT 120M DA - transfert actifs physiques, pas de cash.',
            120000000, 0, 120000000,
            '409100', '211800', false,
            '{SYSTEM_USER_ID}'
        );
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 7. SEED — Known vehicles
    # ═════════════════════════════════════════════════════════════════════
    op.execute(f"""
        INSERT INTO vehicle (
            id, company_id, chassis_number, make, model,
            purchase_amount, purchase_project_id,
            registered_to_associate_id,
            cession_value, current_step,
            history, created_by
        ) VALUES (
            'f4000000-0000-0000-0000-000000000002',
            '{ETS_DK_ID}', 'RR-CHASSIS-001', 'Range Rover', 'Sport',
            4000000, '{EDEN_PROJECT_ID}',
            '{AHMED_ID}',
            4000000, 'CEDE',
            '[{{"step":"ACHETE","amount":"4000000"}},{{"step":"IMMATRICULE","associate":"Ahmed"}},{{"step":"CEDE","to":"GACEB","value":"4000000"}}]'::jsonb,
            '{SYSTEM_USER_ID}'
        );
    """)

    op.execute(f"""
        INSERT INTO vehicle (
            id, company_id, chassis_number, make, model,
            purchase_amount, purchase_project_id,
            registered_to_associate_id,
            cession_value, current_step,
            history, created_by
        ) VALUES (
            'f4000000-0000-0000-0000-000000000003',
            '{ETS_DK_ID}', 'VW-CHASSIS-001', 'Volkswagen', 'Passat',
            6500000, '{EDEN_PROJECT_ID}',
            '{YAZID_ID}',
            6500000, 'CEDE',
            '[{{"step":"ACHETE","amount":"6500000"}},{{"step":"IMMATRICULE","associate":"Yazid"}},{{"step":"CEDE","to":"GACEB","value":"6500000"}}]'::jsonb,
            '{SYSTEM_USER_ID}'
        );
    """)


def downgrade() -> None:
    for table in ("vehicle", "work_situation", "gaceb_advance"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("vehicle")
    op.drop_table("work_situation")
    op.drop_table("gaceb_advance")
