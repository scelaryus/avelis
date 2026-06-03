"""Meta-IA: auto-generative module proposals with double DAF validation.

Tables:
- meta_ia_proposal: structured proposals with lifecycle
- meta_ia_sandbox: isolated test environments

No auto-generated module touches production without double approval.

Revision ID: 038
Revises: 037
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "038"
down_revision: Union[str, None] = "037"
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
    op.create_table(
        "meta_ia_proposal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("detection_trigger", sa.Text, nullable=False),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("proposed_functionality", sa.Text, nullable=False),
        sa.Column("data_consumed", JSONB, nullable=True),
        sa.Column("outputs_produced", JSONB, nullable=True),
        sa.Column("interacting_modules", JSONB, nullable=True),
        sa.Column("estimated_complexity", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'DETECTED'")),
        sa.Column("exploration_approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("exploration_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deployment_approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("deployment_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        *_system_columns(),
    )

    op.create_table(
        "meta_ia_sandbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("meta_ia_proposal.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("sandbox_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'CREATING'")),
        sa.Column("test_data_config", JSONB, nullable=True),
        sa.Column("test_results", JSONB, nullable=True),
        sa.Column("test_passed", sa.Boolean, nullable=True),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_schema", JSONB, nullable=True),
        sa.Column("generated_rules", JSONB, nullable=True),
        *_system_columns(),
    )

    for t in ("meta_ia_proposal", "meta_ia_sandbox"):
        op.execute(f"""CREATE TRIGGER trg_{t}_updated_at BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{t}');")


def downgrade() -> None:
    for t in ("meta_ia_sandbox", "meta_ia_proposal"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_updated_at ON {t};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_no_delete ON {t};")
    op.drop_table("meta_ia_sandbox")
    op.drop_table("meta_ia_proposal")
