"""Treasury monthly closing: 7-step process + permanent period lock.

Tables:
- treasury_closing: tracks the 7-step closing process per entity
- closed_period: permanent lock registry (append-only)

Critical triggers:
- gfi_check_closed_period(): fires BEFORE INSERT/UPDATE on ALL financial
  tables. If the record date falls in a closed period -> REJECT with
  "Periode [M/Y] cloturee. Aucune modification autorisee."
  This is KT-04.
- closed_period is IMMUTABLE (no UPDATE, no DELETE)

Revision ID: 011
Revises: 010
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "011"
down_revision: Union[str, None] = "010"
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


# Financial tables with a date column that must respect closed periods.
# (table_name, date_column_name)
PERIOD_LOCKED_TABLES = [
    ("financial_transaction", "transaction_date"),
    ("journal_entry", "entry_date"),
    ("cca_movement", "movement_date"),
    ("cff_calculation", "invoice_date"),
    ("bank_movement", "movement_date"),
]


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. treasury_closing (GFIBase)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "treasury_closing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Period
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        # Status
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'INITIATED'")),
        # Step 1
        sa.Column("step1_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unreconciled_count", sa.Integer, nullable=True),
        sa.Column("unreconciled_details", JSONB, nullable=True),
        # Step 2
        sa.Column("step2_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("algo_a_result", sa.Numeric(15, 2), nullable=True),
        sa.Column("algo_b_result", sa.Numeric(15, 2), nullable=True),
        sa.Column("computation_delta", sa.Numeric(15, 2), nullable=True),
        # Balances
        sa.Column("opening_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("closing_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_credits", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_debits", sa.Numeric(15, 2), nullable=True),
        # Step 3
        sa.Column("daf_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daf_validated_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("daf_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        # Step 4
        sa.Column("tnm_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tnm_report_path", sa.Text, nullable=True),
        sa.Column("tnm_report_data", JSONB, nullable=True),
        # Step 5
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        # Step 6
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archive_ref", sa.String(100), nullable=True),
        # Step 7
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        # V10
        sa.Column("cc_total_imputed", sa.Numeric(15, 2), nullable=True),
        sa.Column("cc_treasury_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("cc_delta", sa.Numeric(15, 2), nullable=True),
        sa.Column("cc_discrepancy_flagged", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        # CCA snapshot
        sa.Column("cca_balances_snapshot", JSONB, nullable=True),
        # System columns
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. closed_period (append-only, permanent lock registry)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "closed_period",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("closing_id", UUID(as_uuid=True),
                  sa.ForeignKey("treasury_closing.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("locked_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
    )

    # Unique: one closed period per company+year+month
    op.execute("""
        ALTER TABLE closed_period
        ADD CONSTRAINT uq_closed_period_company_ym
        UNIQUE (company_id, period_year, period_month);
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 3. closed_period is IMMUTABLE (like audit_trail)
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_closed_period_immutable()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'Closed periods are permanent. UPDATE and DELETE are forbidden.'
            USING ERRCODE = 'P0001';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_closed_period_immutable
        BEFORE UPDATE OR DELETE ON closed_period
        FOR EACH ROW EXECUTE FUNCTION gfi_closed_period_immutable();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 4. PERIOD LOCK TRIGGER (KT-04)
    # ═════════════════════════════════════════════════════════════════════
    # This function checks if a record's date falls within a closed period.
    # Applied to all financial tables that have a date column.
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_check_closed_period()
        RETURNS TRIGGER AS $$
        DECLARE
            v_date DATE;
            v_company UUID;
            v_year INTEGER;
            v_month INTEGER;
        BEGIN
            -- Get the date and company from the record
            -- The trigger is created per-table with the correct column name
            v_date := NEW.gfi_period_check_date;
            v_company := NEW.company_id;
            v_year := EXTRACT(YEAR FROM v_date);
            v_month := EXTRACT(MONTH FROM v_date);

            IF EXISTS (
                SELECT 1 FROM closed_period
                WHERE company_id = v_company
                  AND period_year = v_year
                  AND period_month = v_month
            ) THEN
                RAISE EXCEPTION
                    'Periode %-% cloturee. Aucune modification autorisee.',
                    v_year, LPAD(v_month::text, 2, '0')
                USING ERRCODE = 'P0001';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create per-table trigger functions that set the correct date column.
    # Each table needs its own wrapper because the date column name varies.
    for table_name, date_col in PERIOD_LOCKED_TABLES:
        func_name = f"gfi_check_closed_period_{table_name}"
        op.execute(f"""
            CREATE OR REPLACE FUNCTION {func_name}()
            RETURNS TRIGGER AS $$
            DECLARE
                v_year INTEGER;
                v_month INTEGER;
            BEGIN
                v_year := EXTRACT(YEAR FROM NEW.{date_col});
                v_month := EXTRACT(MONTH FROM NEW.{date_col});

                IF EXISTS (
                    SELECT 1 FROM closed_period
                    WHERE company_id = NEW.company_id
                      AND period_year = v_year
                      AND period_month = v_month
                ) THEN
                    RAISE EXCEPTION
                        'Periode %-% cloturee. Aucune modification autorisee.',
                        v_year, LPAD(v_month::text, 2, '0')
                    USING ERRCODE = 'P0001';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)

        op.execute(f"""
            CREATE TRIGGER trg_{table_name}_period_lock
            BEFORE INSERT OR UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION {func_name}();
        """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE TRIGGER trg_treasury_closing_updated_at
        BEFORE UPDATE ON treasury_closing
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
    """)
    op.execute("SELECT gfi_apply_no_delete_trigger('treasury_closing');")


def downgrade() -> None:
    # Drop period lock triggers
    for table_name, _ in PERIOD_LOCKED_TABLES:
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table_name}_period_lock "
            f"ON {table_name};"
        )
        op.execute(
            f"DROP FUNCTION IF EXISTS gfi_check_closed_period_{table_name}();"
        )

    op.execute("DROP FUNCTION IF EXISTS gfi_check_closed_period();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_closed_period_immutable ON closed_period;"
    )
    op.execute("DROP FUNCTION IF EXISTS gfi_closed_period_immutable();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_treasury_closing_updated_at "
        "ON treasury_closing;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_treasury_closing_no_delete "
        "ON treasury_closing;"
    )

    op.drop_table("closed_period")
    op.drop_table("treasury_closing")
