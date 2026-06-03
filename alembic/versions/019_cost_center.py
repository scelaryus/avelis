"""Centre de Couts — the financial truth engine.

6-level hierarchy consolidating ALL flows (RF1+RF2+RF3+RF4).
Real-time ascending consolidation from level 5 to level 0.

Tables:
- cost_center_node: hierarchical nodes (6 levels)
- cost_center_entry: individual transaction imputations

Database enforcement:
  V1 verification trigger: after imputation, validate ascending integrity
  Unique code constraint on nodes
  RF type CHECK on entries
  Soft-delete (KT-10) on both tables

Revision ID: 019
Revises: 018
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "019"
down_revision: Union[str, None] = "018"
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
    # 1. cost_center_node
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "cost_center_node",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Hierarchy
        sa.Column("code", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("level", sa.Integer, nullable=False, index=True),
        sa.Column("parent_id", UUID(as_uuid=True),
                  sa.ForeignKey("cost_center_node.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("parent_code", sa.String(100), nullable=True),
        # Identity
        sa.Column("libelle", sa.String(255), nullable=False),
        sa.Column("node_type", sa.String(30), nullable=False),
        # Scope
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("categorie", sa.String(30), nullable=True),
        sa.Column("sous_categorie", sa.String(60), nullable=True),
        # Amounts per RF
        sa.Column("montant_rf1", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("montant_rf2", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("montant_rf3", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("montant_rf4", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("montant_total", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        # Flags
        sa.Column("impact_tresorerie", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. cost_center_entry
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "cost_center_entry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("node_id", UUID(as_uuid=True),
                  sa.ForeignKey("cost_center_node.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("node_code", sa.String(100), nullable=False),
        sa.Column("entry_date", sa.Date, nullable=False, index=True),
        sa.Column("rf_type", sa.String(3), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("libelle", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(60), nullable=True),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("impact_tresorerie", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE cost_center_node
        ADD CONSTRAINT chk_ccn_level
        CHECK (level >= 0 AND level <= 5);
    """)

    op.execute("""
        ALTER TABLE cost_center_entry
        ADD CONSTRAINT chk_cce_rf_type
        CHECK (rf_type IN ('RF1', 'RF2', 'RF3', 'RF4'));
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 4. STANDARD TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("cost_center_node", "cost_center_entry"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in ("cost_center_entry", "cost_center_node"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("cost_center_entry")
    op.drop_table("cost_center_node")
