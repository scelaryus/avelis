"""Project + construction site management.

Tables:
- project_task: task planning with completion and tier thresholds
- task_advancement: timestamped advancement records
- subcontractor_contract: agreements with performance scoring

Advancement % drives credit tier eligibility.
Work situation validation feeds CC2 + CC8.

Revision ID: 026
Revises: 025
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "026"
down_revision: Union[str, None] = "025"
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
    # 1. subcontractor_contract (before project_task for FK)
    op.create_table(
        "subcontractor_contract",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("supplier_id", UUID(as_uuid=True),
                  sa.ForeignKey("supplier.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        sa.Column("subcontractor_name", sa.String(255), nullable=False),
        sa.Column("contract_ref", sa.String(50), nullable=True),
        sa.Column("contract_date", sa.Date, nullable=True),
        sa.Column("scope", sa.Text, nullable=True),
        sa.Column("montant_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("montant_facture", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("montant_paye", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("score_quality", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_deadlines", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_safety", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_overall", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'ACTIF'")),
        *_system_columns(),
    )

    # 2. project_task
    op.create_table(
        "project_task",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("parent_task_id", UUID(as_uuid=True),
                  sa.ForeignKey("project_task.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(30), nullable=True),
        sa.Column("planned_start", sa.Date, nullable=True),
        sa.Column("planned_end", sa.Date, nullable=True),
        sa.Column("actual_start", sa.Date, nullable=True),
        sa.Column("actual_end", sa.Date, nullable=True),
        sa.Column("duration_days", sa.Integer, nullable=True),
        sa.Column("completion_pct", sa.Numeric(5, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("tier_threshold_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("budget_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("actual_cost", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'A_FAIRE'")),
        sa.Column("assigned_to", UUID(as_uuid=True), nullable=True),
        sa.Column("subcontractor_id", UUID(as_uuid=True),
                  sa.ForeignKey("subcontractor_contract.id", ondelete="SET NULL"),
                  nullable=True),
        *_system_columns(),
    )

    # 3. task_advancement
    op.create_table(
        "task_advancement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("task_id", UUID(as_uuid=True),
                  sa.ForeignKey("project_task.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("record_date", sa.Date, nullable=False, index=True),
        sa.Column("previous_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("new_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column("photo_urls", JSONB, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("validated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tier_triggered", sa.String(20), nullable=True),
        *_system_columns(),
    )

    # CHECK constraints
    op.execute("""
        ALTER TABLE project_task
        ADD CONSTRAINT chk_pt_completion
        CHECK (completion_pct >= 0 AND completion_pct <= 100);
    """)

    # Triggers
    for table in ("subcontractor_contract", "project_task", "task_advancement"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in ("task_advancement", "project_task", "subcontractor_contract"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("task_advancement")
    op.drop_table("project_task")
    op.drop_table("subcontractor_contract")
