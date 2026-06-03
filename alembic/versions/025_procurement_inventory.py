"""Procurement + inventory: full purchase cycle with SoD, multi-warehouse stock.

Tables:
- supplier: registry with performance scoring
- purchase_request: DA (demande d'achat)
- purchase_order: BC (bon de commande)
- goods_receipt: BR (bon de reception)
- warehouse: storage locations
- stock_item: inventory items with CUMP/FIFO
- stock_movement: every entry/exit traced

SoD enforced at each step via Python engine + audit trail.
Stock consumption feeds CC3 (materiaux).

Revision ID: 025
Revises: 024
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "025"
down_revision: Union[str, None] = "024"
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
    # 1. supplier
    op.create_table(
        "supplier",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("nif", sa.String(30), nullable=True),
        sa.Column("rc", sa.String(50), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("specialty", sa.String(100), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("bank_account", sa.String(50), nullable=True),
        sa.Column("performance_score", sa.Numeric(5, 2), nullable=False,
                  server_default=sa.text("50")),
        sa.Column("score_history", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        *_system_columns(),
    )

    # 2. purchase_request
    op.create_table(
        "purchase_request",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("request_number", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("requested_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=False),
        sa.Column("request_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("justification", sa.Text, nullable=True),
        sa.Column("estimated_budget", sa.Numeric(15, 2), nullable=True),
        sa.Column("urgency", sa.String(20), nullable=False, server_default=sa.text("'NORMAL'")),
        sa.Column("items", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'BROUILLON'")),
        sa.Column("validated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        *_system_columns(),
    )

    # 3. warehouse (before purchase_order for FK order)
    op.create_table(
        "warehouse",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("code", sa.String(20), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_system_columns(),
    )

    # 4. purchase_order
    op.create_table(
        "purchase_order",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("order_number", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("purchase_request_id", UUID(as_uuid=True),
                  sa.ForeignKey("purchase_request.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("supplier_id", UUID(as_uuid=True),
                  sa.ForeignKey("supplier.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("order_date", sa.Date, nullable=False),
        sa.Column("expected_delivery", sa.Date, nullable=True),
        sa.Column("total_ht", sa.Numeric(15, 2), nullable=False),
        sa.Column("tva_amount", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_ttc", sa.Numeric(15, 2), nullable=False),
        sa.Column("lines", JSONB, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'BROUILLON'")),
        sa.Column("created_by_user", UUID(as_uuid=True), nullable=False),
        sa.Column("validated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        *_system_columns(),
    )

    # 5. stock_item
    op.create_table(
        "stock_item",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("reference", sa.String(50), nullable=False, index=True),
        sa.Column("designation", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default=sa.text("'UNITE'")),
        sa.Column("warehouse_id", UUID(as_uuid=True),
                  sa.ForeignKey("warehouse.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("quantity_on_hand", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("quantity_reserved", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("quantity_available", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("valuation_method", sa.String(10), nullable=False, server_default=sa.text("'CUMP'")),
        sa.Column("unit_cost", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_value", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("min_stock", sa.Numeric(12, 3), nullable=True),
        sa.Column("max_stock", sa.Numeric(12, 3), nullable=True),
        sa.Column("reorder_point", sa.Numeric(12, 3), nullable=True),
        sa.Column("qr_code", sa.String(100), nullable=True, unique=True),
        *_system_columns(),
    )

    # 6. goods_receipt
    op.create_table(
        "goods_receipt",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("receipt_number", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("purchase_order_id", UUID(as_uuid=True),
                  sa.ForeignKey("purchase_order.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("supplier_id", UUID(as_uuid=True),
                  sa.ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("warehouse_id", UUID(as_uuid=True),
                  sa.ForeignKey("warehouse.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receipt_date", sa.Date, nullable=False, index=True),
        sa.Column("delivery_note_ref", sa.String(100), nullable=True),
        sa.Column("delivery_note_photo", sa.Text, nullable=True),
        sa.Column("lines", JSONB, nullable=False),
        sa.Column("quality_check", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'BROUILLON'")),
        sa.Column("received_by", UUID(as_uuid=True), nullable=False),
        sa.Column("validated_by", UUID(as_uuid=True), nullable=True),
        *_system_columns(),
    )

    # 7. stock_movement
    op.create_table(
        "stock_movement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("stock_item_id", UUID(as_uuid=True),
                  sa.ForeignKey("stock_item.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("warehouse_id", UUID(as_uuid=True),
                  sa.ForeignKey("warehouse.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("movement_date", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_cost", sa.Numeric(15, 2), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=True),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("responsible_user", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_system_columns(),
    )

    # CHECK constraints
    op.execute("""
        ALTER TABLE stock_movement
        ADD CONSTRAINT chk_sm_type
        CHECK (movement_type IN ('ENTREE', 'SORTIE', 'TRANSFERT', 'AJUSTEMENT'));
    """)

    # Triggers
    all_tables = [
        "supplier", "purchase_request", "purchase_order",
        "goods_receipt", "warehouse", "stock_item", "stock_movement",
    ]
    for table in all_tables:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    tables = [
        "stock_movement", "goods_receipt", "stock_item",
        "purchase_order", "warehouse", "purchase_request", "supplier",
    ]
    for table in tables:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    for table in tables:
        op.drop_table(table)
