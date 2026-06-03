"""043 — Supplier module: fournisseurs, contracts, payments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "supplier",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("code", sa.String(30), unique=True, nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("nif", sa.String(30), nullable=True),
        sa.Column("rc", sa.String(30), nullable=True),
        sa.Column("rib", sa.String(30), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), server_default="ACTIF"),
        sa.Column("total_contracts", sa.Numeric(15, 2), server_default="0"),
        sa.Column("total_paid", sa.Numeric(15, 2), server_default="0"),
        sa.Column("total_remaining", sa.Numeric(15, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    op.create_table(
        "supplier_contract",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("supplier.id"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("contract_number", sa.String(50), unique=True, nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("montant_ht", sa.Numeric(15, 2), nullable=False),
        sa.Column("tva_rate", sa.Numeric(5, 2), server_default="19.00"),
        sa.Column("montant_tva", sa.Numeric(15, 2), nullable=False),
        sa.Column("montant_ttc", sa.Numeric(15, 2), nullable=False),
        sa.Column("date_signature", sa.Date, nullable=True),
        sa.Column("date_debut", sa.Date, nullable=True),
        sa.Column("date_fin", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), server_default="ACTIF"),
        sa.Column("total_paid", sa.Numeric(15, 2), server_default="0"),
        sa.Column("remaining", sa.Numeric(15, 2), nullable=True),
        sa.Column("stock_items_received", sa.Integer, server_default="0"),
        sa.Column("stock_value_received", sa.Numeric(15, 2), server_default="0"),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_supplier_contract_supplier", "supplier_contract", ["supplier_id"])

    op.create_table(
        "supplier_payment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("supplier.id"), nullable=False),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("supplier_contract.id"), nullable=True),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("mode_reglement", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("date_paiement", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), server_default="ENCAISSE"),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column("proof_url", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_supplier_payment_supplier", "supplier_payment", ["supplier_id"])
    op.create_index("ix_supplier_payment_contract", "supplier_payment", ["contract_id"])

    # Add supplier/contract link to stock_item
    op.add_column("stock_item", sa.Column("supplier_id", UUID(as_uuid=True), nullable=True))
    op.add_column("stock_item", sa.Column("contract_id", UUID(as_uuid=True), nullable=True))


def downgrade():
    op.drop_column("stock_item", "contract_id")
    op.drop_column("stock_item", "supplier_id")
    op.drop_table("supplier_payment")
    op.drop_table("supplier_contract")
    op.drop_table("supplier")
