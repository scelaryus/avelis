"""042 — Stock module: storage zones, stock items with barcodes, movements."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "storage_zone",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
        sa.UniqueConstraint("company_id", "code", name="uq_storage_zone_code"),
    )

    op.create_table(
        "stock_item",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("zone_id", UUID(as_uuid=True), sa.ForeignKey("storage_zone.id"), nullable=True),
        sa.Column("code", sa.String(40), unique=True, nullable=False),
        sa.Column("barcode", sa.String(60), unique=True, nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("ai_detected_name", sa.String(300), nullable=True),
        sa.Column("ai_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), server_default="0"),
        sa.Column("unit", sa.String(20), server_default="UNITE"),
        sa.Column("unit_price", sa.Numeric(15, 2), server_default="0"),
        sa.Column("total_value", sa.Numeric(15, 2), server_default="0"),
        sa.Column("status", sa.String(20), server_default="ACTIF"),
        sa.Column("min_stock_alert", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_stock_item_code", "stock_item", ["code"])
    op.create_index("ix_stock_item_barcode", "stock_item", ["barcode"])
    op.create_index("ix_stock_item_zone", "stock_item", ["zone_id"])

    op.create_table(
        "stock_movement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("stock_item.id"), nullable=False),
        sa.Column("movement_type", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_stock_movement_item", "stock_movement", ["item_id"])


def downgrade():
    op.drop_table("stock_movement")
    op.drop_table("stock_item")
    op.drop_table("storage_zone")
