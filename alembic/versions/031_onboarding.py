"""Onboarding: recruitment + documentation + access activation.

Tables:
- recruitment_request: F-REC-001 with validation chain
- candidate: pipeline from CV to hire
- onboarding_checklist: 7 mandatory documents verification
- equipment_assignment: from job position profile

Revision ID: 031
Revises: 030
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "031"
down_revision: Union[str, None] = "030"
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
    # 1. recruitment_request
    op.create_table(
        "recruitment_request",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("position_title", sa.String(255), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True),
                  sa.ForeignKey("department.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("job_position_id", UUID(as_uuid=True),
                  sa.ForeignKey("job_position.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("justification", sa.Text, nullable=False),
        sa.Column("contract_type", sa.String(20), nullable=False),
        sa.Column("cdd_reason", sa.Text, nullable=True),
        sa.Column("desired_start_date", sa.Date, nullable=False),
        sa.Column("salary_min", sa.Numeric(15, 2), nullable=False),
        sa.Column("salary_max", sa.Numeric(15, 2), nullable=False),
        sa.Column("num_positions", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("required_skills", JSONB, nullable=True),
        sa.Column("job_description_url", sa.Text, nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default=sa.text("'NORMAL'")),
        sa.Column("requested_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'BROUILLON'")),
        sa.Column("validated_recrutement_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_drh_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_dg_by", UUID(as_uuid=True), nullable=True),
        sa.Column("requires_dg_approval", sa.Boolean, nullable=False, server_default=sa.text("false")),
        *_system_columns(),
    )

    # 2. candidate
    op.create_table(
        "candidate",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("recruitment_request_id", UUID(as_uuid=True),
                  sa.ForeignKey("recruitment_request.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("cv_url", sa.Text, nullable=True),
        sa.Column("cv_extracted_data", JSONB, nullable=True),
        sa.Column("cv_similarity_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'RECU'")),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("psychometric_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("technical_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("interview_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("employee_id", UUID(as_uuid=True),
                  sa.ForeignKey("employee.id", ondelete="SET NULL"), nullable=True),
        *_system_columns(),
    )

    # 3. onboarding_checklist
    op.create_table(
        "onboarding_checklist",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True),
                  sa.ForeignKey("employee.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("document_code", sa.String(20), nullable=False),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("file_url", sa.Text, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("ocr_result", JSONB, nullable=True),
        sa.Column("ocr_passed", sa.Boolean, nullable=True),
        sa.Column("relance_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_relance_at", sa.DateTime(timezone=True), nullable=True),
        *_system_columns(),
    )

    # 4. equipment_assignment
    op.create_table(
        "equipment_assignment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True),
                  sa.ForeignKey("employee.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("equipment_type", sa.String(50), nullable=False),
        sa.Column("equipment_description", sa.String(255), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("assigned_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'EN_ATTENTE_STOCK'")),
        sa.Column("bon_sortie_ref", sa.String(50), nullable=True),
        sa.Column("bon_sortie_signed", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("restitution_date", sa.Date, nullable=True),
        *_system_columns(),
    )

    # CHECK: salary_min >= SNMG
    op.execute("""
        ALTER TABLE recruitment_request
        ADD CONSTRAINT chk_rr_snmg
        CHECK (salary_min >= 20000);
    """)

    # Triggers
    for table in ("recruitment_request", "candidate",
                   "onboarding_checklist", "equipment_assignment"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in ("equipment_assignment", "onboarding_checklist",
                   "candidate", "recruitment_request"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("equipment_assignment")
    op.drop_table("onboarding_checklist")
    op.drop_table("candidate")
    op.drop_table("recruitment_request")
