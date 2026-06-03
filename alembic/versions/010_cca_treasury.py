"""CCA (Comptes Courants Associes) treasury module.

Tables:
- cca_account: per-associate per-company CCA with running balance
- cca_movement: individual transactions (deposits, withdrawals, debts, etc.)
- cca_freeze: capital call freeze tracking (R-016)

Database enforcement:
- R-003 double withdrawal rule via trigger
- R-016 freeze check via trigger
- Mandatory justification check via trigger
- Balance auto-update trigger after movement insert
- Soft-delete (KT-10) on all 3 tables

Seeds: CCA accounts for the 4 founders across all entities they hold shares in.

Revision ID: 010
Revises: 009
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

COMPANY_IDS = {
    "ETS-DK":   "10000000-0000-0000-0000-000000000001",
    "SARL-DP":  "10000000-0000-0000-0000-000000000002",
    "SARL-DBPI":"10000000-0000-0000-0000-000000000003",
    "SARL-OC":  "10000000-0000-0000-0000-000000000004",
    "SARL-SEN": "10000000-0000-0000-0000-000000000005",
    "SARL-EP":  "10000000-0000-0000-0000-000000000006",
    "EURL-BIM": "10000000-0000-0000-0000-000000000007",
    "SARL-AMF": "10000000-0000-0000-0000-000000000008",
    "EURL-BAY": "10000000-0000-0000-0000-000000000009",
    "SARL-M60": "10000000-0000-0000-0000-00000000000a",
    "SARL-ARC": "10000000-0000-0000-0000-00000000000b",
    "SCI-DEN":  "10000000-0000-0000-0000-00000000000c",
}

ASSOCIATE_IDS = {
    "Ahmed":  "20000000-0000-0000-0000-000000000001",
    "Mohamed":"20000000-0000-0000-0000-000000000002",
    "Yazid":  "20000000-0000-0000-0000-000000000003",
    "Yamina": "20000000-0000-0000-0000-000000000004",
}

# CCA map: which associates have CCAs in which companies
# Ahmed: all 12. Mohamed/Yazid: all except EURL-BAY (ownership TBD).
# Yamina: only ETS-DK and SARL-DP.
ALL_COMPANIES = list(COMPANY_IDS.keys())
ALL_EXCEPT_BAY = [c for c in ALL_COMPANIES if c != "EURL-BAY"]
YAMINA_COMPANIES = ["ETS-DK", "SARL-DP"]

CCA_MAP = {
    "Ahmed": ALL_COMPANIES,
    "Mohamed": ALL_EXCEPT_BAY,
    "Yazid": ALL_EXCEPT_BAY,
    "Yamina": YAMINA_COMPANIES,
}

_cca_counter = 0


def _cca_uuid():
    global _cca_counter
    _cca_counter += 1
    return f"e1000000-0000-0000-0000-{_cca_counter:012x}"


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
    # 1. cca_account
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "cca_account",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("balance", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("freeze_reason", sa.String(255), nullable=True),
        sa.Column("scf_account_code", sa.String(20), nullable=False,
                  server_default=sa.text("'455'")),
        *_system_columns(),
        sa.UniqueConstraint("company_id", "associate_id",
                            name="uq_cca_account_company_associate"),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. cca_movement
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "cca_movement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("cca_account_id", UUID(as_uuid=True),
                  sa.ForeignKey("cca_account.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("movement_date", sa.Date, nullable=False, index=True),
        sa.Column("movement_type", sa.String(30), nullable=False, index=True),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(15, 2), nullable=False),
        sa.Column("justification_type", sa.String(40), nullable=False),
        sa.Column("justification_ref", sa.String(100), nullable=True),
        sa.Column("justification_path", sa.Text, nullable=True),
        sa.Column("rf_type", sa.String(3), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("cc_category", sa.String(10), nullable=True),
        sa.Column("source_document_type", sa.String(60), nullable=True),
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("journal_entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal_entry.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. cca_freeze
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "cca_freeze",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("cca_account_id", UUID(as_uuid=True),
                  sa.ForeignKey("cca_account.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("freeze_date", sa.Date, nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("capital_call_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("capital_call_ref", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("resolved_date", sa.Date, nullable=True),
        sa.Column("resolved_by_movement_id", UUID(as_uuid=True),
                  sa.ForeignKey("cca_movement.id", ondelete="SET NULL"),
                  nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE cca_movement
        ADD CONSTRAINT chk_cca_mv_type
        CHECK (movement_type IN (
            'DEPOT', 'RETRAIT', 'DISTRIBUTION', 'CFF_DEDUCTION',
            'DETTE_PERSONNELLE', 'COMMISSION', 'REMBOURSEMENT',
            'APPEL_FONDS', 'TRANSFERT'
        ));
    """)

    op.execute("""
        ALTER TABLE cca_movement
        ADD CONSTRAINT chk_cca_mv_justification
        CHECK (justification_type IS NOT NULL AND justification_type != '');
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════

    # R-003: Double withdrawal rule (database-level enforcement)
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_cca_withdrawal_check()
        RETURNS TRIGGER AS $$
        DECLARE
            v_balance NUMERIC(15,2);
            v_max_individual NUMERIC(15,2);
            v_entity_total NUMERIC(15,2);
            v_company_name TEXT;
        BEGIN
            IF NEW.movement_type = 'RETRAIT' AND NEW.amount < 0 THEN
                -- Get current CCA balance
                SELECT balance INTO v_balance
                FROM cca_account WHERE id = NEW.cca_account_id;

                -- Check CCA is not frozen
                IF EXISTS (
                    SELECT 1 FROM cca_account
                    WHERE id = NEW.cca_account_id AND status = 'FROZEN'
                ) THEN
                    RAISE EXCEPTION 'CCA gele — retrait interdit.'
                    USING ERRCODE = 'P0001';
                END IF;

                -- Condition 1: amount <= 50% of individual balance
                v_max_individual := v_balance * 0.50;
                IF ABS(NEW.amount) > v_max_individual THEN
                    RAISE EXCEPTION
                        'Montant maximum autorise : % DA (50%% du solde individuel de % DA).',
                        ROUND(v_max_individual, 2), ROUND(v_balance, 2)
                    USING ERRCODE = 'P0001';
                END IF;

                -- Condition 2: entity total must be positive
                SELECT COALESCE(SUM(balance), 0) INTO v_entity_total
                FROM cca_account
                WHERE company_id = NEW.company_id AND is_deleted = false;

                IF v_entity_total <= 0 THEN
                    SELECT legal_name INTO v_company_name
                    FROM company WHERE id = NEW.company_id;
                    RAISE EXCEPTION
                        'Solde global CCA de % negatif — retrait interdit.',
                        v_company_name
                    USING ERRCODE = 'P0001';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_cca_movement_withdrawal_check
        BEFORE INSERT ON cca_movement
        FOR EACH ROW EXECUTE FUNCTION gfi_cca_withdrawal_check();
    """)

    # Balance auto-update after movement
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_cca_update_balance()
        RETURNS TRIGGER AS $$
        BEGIN
            UPDATE cca_account
            SET balance = NEW.balance_after
            WHERE id = NEW.cca_account_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_cca_movement_update_balance
        AFTER INSERT ON cca_movement
        FOR EACH ROW EXECUTE FUNCTION gfi_cca_update_balance();
    """)

    # Standard triggers
    for table in ("cca_account", "cca_movement", "cca_freeze"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ═════════════════════════════════════════════════════════════════════
    # 6. SEED — CCA accounts for founders
    # ═════════════════════════════════════════════════════════════════════
    for assoc_name, companies in CCA_MAP.items():
        aid = ASSOCIATE_IDS[assoc_name]
        for company_code in companies:
            cid = COMPANY_IDS[company_code]
            uid = _cca_uuid()
            op.execute(f"""
                INSERT INTO cca_account (
                    id, company_id, associate_id, balance, status,
                    scf_account_code, created_by
                ) VALUES (
                    '{uid}', '{cid}', '{aid}', 0,
                    'ACTIVE', '455', '{SYSTEM_USER_ID}'
                );
            """)


def downgrade() -> None:
    for table in ("cca_freeze", "cca_movement", "cca_account"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")

    op.execute("DROP TRIGGER IF EXISTS trg_cca_movement_withdrawal_check ON cca_movement;")
    op.execute("DROP TRIGGER IF EXISTS trg_cca_movement_update_balance ON cca_movement;")
    op.execute("DROP FUNCTION IF EXISTS gfi_cca_withdrawal_check();")
    op.execute("DROP FUNCTION IF EXISTS gfi_cca_update_balance();")

    op.drop_table("cca_freeze")
    op.drop_table("cca_movement")
    op.drop_table("cca_account")
