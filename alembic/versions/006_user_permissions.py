"""Add user_permissions table for per-user, per-module access control.

Revision ID: 006_user_permissions
Revises: 005_bim_edd_v2
Create Date: 2026-03-12
"""

revision = "006_user_permissions"
down_revision = "005_bim_edd_v2"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("can_read", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("can_write", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "module", name="uq_user_permission_module"),
    )
    op.create_index("ix_user_permissions_user", "user_permissions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_permissions_user", table_name="user_permissions")
    op.drop_table("user_permissions")
