"""EDD (Etat Descriptif Detaille) real estate inventory system.

Tables:
- lot: every sellable unit with RF1/RF2 pricing and state machine
- lot_lock: pessimistic 15-minute locks for commercial agents

Database enforcement:
- CHECK: lot status must be in valid state set
- CHECK: lot typology must be in valid set
- RF2 price encryption trigger (reuses pgcrypto from migration 007)
- Auto-expire stale locks trigger
- Unique lot_ref per project constraint
- Soft-delete (KT-10) on both tables

Revision ID: 012
Revises: 011
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "012"
down_revision: Union[str, None] = "011"
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
    # 1. lot
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "lot",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Identity
        sa.Column("lot_ref", sa.String(50), nullable=False, index=True),
        sa.Column("typology", sa.String(30), nullable=False),
        # Physical
        sa.Column("surface_m2", sa.Numeric(8, 2), nullable=True),
        sa.Column("floor_number", sa.Integer, nullable=True),
        sa.Column("block", sa.String(20), nullable=True),
        sa.Column("orientation", sa.String(20), nullable=True),
        # Status
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'DISPONIBLE'")),
        # Pricing
        sa.Column("rf1_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("rf2_price_encrypted", sa.Text, nullable=True),
        sa.Column("rf2_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("real_price", sa.Numeric(15, 2), nullable=True),
        # Delivery
        sa.Column("expected_delivery_date", sa.Date, nullable=True),
        sa.Column("actual_delivery_date", sa.Date, nullable=True),
        # Client
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("client_id", UUID(as_uuid=True), nullable=True),
        # Associate withdrawal
        sa.Column("withdrawn_by_associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("withdrawal_value", sa.Numeric(15, 2), nullable=True),
        # Metadata
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        # System columns
        *_system_columns(),
    )

    # Unique lot_ref per project
    op.execute("""
        ALTER TABLE lot
        ADD CONSTRAINT uq_lot_project_ref
        UNIQUE (project_id, lot_ref);
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 2. lot_lock
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "lot_lock",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("lot_id", UUID(as_uuid=True),
                  sa.ForeignKey("lot.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("locked_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ttl_seconds", sa.Integer, nullable=False,
                  server_default=sa.text("900")),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        # System columns
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════

    op.execute("""
        ALTER TABLE lot
        ADD CONSTRAINT chk_lot_status
        CHECK (status IN (
            'DISPONIBLE', 'VERROUILLE', 'RESERVE', 'PROMIS',
            'VENDU', 'LIVRE', 'PRELEVEMENT', 'BLOQUE', 'ANNULE'
        ));
    """)

    op.execute("""
        ALTER TABLE lot
        ADD CONSTRAINT chk_lot_typology
        CHECK (typology IN (
            'F2', 'F3', 'F4', 'F5', 'DUPLEX',
            'LOCAL_COMMERCIAL', 'PARKING', 'CAVE'
        ));
    """)

    op.execute("""
        ALTER TABLE lot
        ADD CONSTRAINT chk_lot_orientation
        CHECK (
            orientation IS NULL
            OR orientation IN ('NORD', 'SUD', 'EST', 'OUEST', 'DOUBLE', 'N/A')
        );
    """)

    op.execute("""
        ALTER TABLE lot_lock
        ADD CONSTRAINT chk_lot_lock_status
        CHECK (status IN ('ACTIVE', 'RESERVED', 'EXPIRED', 'RELEASED'));
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 4. RF2 PRICE ENCRYPTION TRIGGER
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_lot_rf2_encrypt()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.rf2_price IS NOT NULL THEN
                NEW.rf2_price_encrypted := encode(
                    pgp_sym_encrypt(
                        NEW.rf2_price::text,
                        current_setting('app.rf2_encryption_key', true)
                    ),
                    'base64'
                );
                -- Compute real price = RF1 + RF2
                NEW.real_price := COALESCE(NEW.rf1_price, 0) + NEW.rf2_price;
            ELSE
                NEW.rf2_price_encrypted := NULL;
                NEW.real_price := NEW.rf1_price;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_lot_rf2_encrypt
        BEFORE INSERT OR UPDATE ON lot
        FOR EACH ROW EXECUTE FUNCTION gfi_lot_rf2_encrypt();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("lot", "lot_lock"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in ("lot_lock", "lot"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")

    op.execute("DROP TRIGGER IF EXISTS trg_lot_rf2_encrypt ON lot;")
    op.execute("DROP FUNCTION IF EXISTS gfi_lot_rf2_encrypt();")

    op.drop_table("lot_lock")
    op.drop_table("lot")
