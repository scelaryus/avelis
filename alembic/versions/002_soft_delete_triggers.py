"""Block physical DELETE on financial tables via database trigger (KT-10).

Any attempt to DELETE a row from a financial table will raise an exception.
The application must use soft delete (is_deleted = true) instead.

New financial tables added later MUST be registered in this trigger by creating
a new migration that calls: gfi_apply_no_delete_trigger('new_table_name');

Revision ID: 002
Revises: 001
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All financial tables that must block physical DELETE.
# This list will grow as the schema evolves.
FINANCIAL_TABLES = [
    "company",
    "associate",
]


def upgrade() -> None:
    # ── 1. Create the reusable trigger function ──────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_block_physical_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Physical deletion forbidden on financial tables. Use soft delete.'
                USING ERRCODE = 'P0001';
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ── 2. Helper to apply the trigger to any table ──────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_apply_no_delete_trigger(target_table TEXT)
        RETURNS VOID AS $$
        BEGIN
            EXECUTE format(
                'CREATE TRIGGER trg_%I_no_delete
                 BEFORE DELETE ON %I
                 FOR EACH ROW EXECUTE FUNCTION gfi_block_physical_delete();',
                target_table, target_table
            );
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ── 3. Apply to all current financial tables ─────────────────────────
    for table in FINANCIAL_TABLES:
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in FINANCIAL_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.execute("DROP FUNCTION IF EXISTS gfi_apply_no_delete_trigger(TEXT);")
    op.execute("DROP FUNCTION IF EXISTS gfi_block_physical_delete();")
