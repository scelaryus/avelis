"""Company-based multi-tenancy, HR task workflow & ADV project scoping

Revision ID: 002_company_workflow
Revises: 001_initial
Create Date: 2025-06-01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_company_workflow"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tenant: add company fields ──
    op.add_column("tenants", sa.Column("code", sa.String(50), unique=True))
    op.add_column("tenants", sa.Column("logo_url", sa.String(500)))
    op.add_column("tenants", sa.Column("description", sa.Text))
    op.add_column("tenants", sa.Column("address", sa.Text))
    op.add_column("tenants", sa.Column("phone", sa.String(50)))
    op.add_column("tenants", sa.Column("email", sa.String(255)))
    op.add_column("tenants", sa.Column("is_active", sa.Boolean, server_default="true"))

    # ── User: tenant-scoped email uniqueness + employee link ──
    # Drop old global unique constraint on email
    try:
        op.drop_constraint("users_email_key", "users", type_="unique")
    except Exception:
        try:
            op.drop_index("ix_users_email", table_name="users")
        except Exception:
            pass

    op.create_unique_constraint("uq_user_tenant_email", "users", ["tenant_id", "email"])
    op.add_column("users", sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=True))

    # ── Employee: link back to user ──
    op.add_column("employees", sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True))

    # ── HR Tasks: full workflow columns ──
    op.add_column("hr_tasks", sa.Column("required_role", sa.String(100)))
    op.add_column("hr_tasks", sa.Column("plan_date", sa.Date))
    op.add_column("hr_tasks", sa.Column("entreprise_id", sa.String(36)))
    op.add_column("hr_tasks", sa.Column("manager_rating", sa.Integer))
    op.add_column("hr_tasks", sa.Column("manager_feedback", sa.Text))
    op.add_column("hr_tasks", sa.Column("salary_adjustment_amount", sa.Numeric(18, 2), server_default="0"))
    op.add_column("hr_tasks", sa.Column("salary_adjusted_at", sa.DateTime))

    # New approval workflow columns
    op.add_column("hr_tasks", sa.Column("approval_status", sa.String(30), server_default="PENDING_ESTIMATE"))
    op.add_column("hr_tasks", sa.Column("employee_estimated_time", sa.Float))
    op.add_column("hr_tasks", sa.Column("employee_estimated_price", sa.Numeric(18, 2)))
    op.add_column("hr_tasks", sa.Column("estimated_at", sa.DateTime))
    op.add_column("hr_tasks", sa.Column("manager_final_time", sa.Float))
    op.add_column("hr_tasks", sa.Column("manager_final_price", sa.Numeric(18, 2)))
    op.add_column("hr_tasks", sa.Column("manager_approved_at", sa.DateTime))
    op.add_column("hr_tasks", sa.Column("manager_approved_by", sa.String(36), sa.ForeignKey("users.id")))
    op.add_column("hr_tasks", sa.Column("proof_document_id", sa.String(36), sa.ForeignKey("documents.id")))
    op.add_column("hr_tasks", sa.Column("proof_uploaded_at", sa.DateTime))
    op.add_column("hr_tasks", sa.Column("ai_score", sa.Float))
    op.add_column("hr_tasks", sa.Column("ai_note", sa.Text))
    op.add_column("hr_tasks", sa.Column("ai_evaluated_at", sa.DateTime))
    op.add_column("hr_tasks", sa.Column("manager_validated", sa.Boolean, server_default="false"))
    op.add_column("hr_tasks", sa.Column("manager_validated_at", sa.DateTime))

    # ── Task Notifications ──
    op.create_table(
        "task_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("hr_tasks.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── ADV models: add entreprise_id / projet_id ──
    for table_name in ("clients", "contracts", "receivables", "payments"):
        op.add_column(table_name, sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=True))
        op.add_column(table_name, sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=True))


def downgrade() -> None:
    # ADV: remove project columns
    for table_name in ("payments", "receivables", "contracts", "clients"):
        op.drop_column(table_name, "projet_id")
        op.drop_column(table_name, "entreprise_id")

    # Task notifications
    op.drop_table("task_notifications")

    # HR Tasks: remove workflow columns
    for col in (
        "manager_validated_at", "manager_validated", "ai_evaluated_at", "ai_note",
        "ai_score", "proof_uploaded_at", "proof_document_id", "manager_approved_by",
        "manager_approved_at", "manager_final_price", "manager_final_time",
        "estimated_at", "employee_estimated_price", "employee_estimated_time",
        "approval_status", "salary_adjusted_at", "salary_adjustment_amount",
        "manager_feedback", "manager_rating", "entreprise_id", "plan_date",
        "required_role",
    ):
        op.drop_column("hr_tasks", col)

    # Employee: remove user_id
    op.drop_column("employees", "user_id")

    # User: remove employee_id, restore global unique email
    op.drop_column("users", "employee_id")
    op.drop_constraint("uq_user_tenant_email", "users", type_="unique")
    op.create_unique_constraint("users_email_key", "users", ["email"])

    # Tenant: remove company fields
    for col in ("is_active", "email", "phone", "address", "description", "logo_url", "code"):
        op.drop_column("tenants", col)
