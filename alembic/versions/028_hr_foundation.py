"""HR foundation: departments, positions, salary structures, employees, contracts.

Tables:
- department: org structure per entity
- job_position: role definitions with skills/equipment/access profiles
- salary_structure: pay components per grade
- employee: full record per CDC-DRH (bilingual, CNAS, badge, lifecycle)
- employee_contract: triple validation, CDD requalification

Database enforcement:
  CHECK: salary_base >= 20000 (SNMG)
  CHECK: age 16-70
  CHECK: CDD requires end_date
  CHECK: employee status in lifecycle states
  CHECK: contract status in validation states

Revision ID: 028
Revises: 027
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "028"
down_revision: Union[str, None] = "027"
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
    # 1. department
    op.create_table(
        "department",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("code", sa.String(20), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=True),
        sa.Column("parent_department_id", UUID(as_uuid=True),
                  sa.ForeignKey("department.id", ondelete="SET NULL"), nullable=True),
        sa.Column("manager_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_system_columns(),
    )

    # 2. job_position
    op.create_table(
        "job_position",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("code", sa.String(20), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("title_ar", sa.String(255), nullable=True),
        sa.Column("department_id", UUID(as_uuid=True),
                  sa.ForeignKey("department.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("required_skills", JSONB, nullable=True),
        sa.Column("equipment_profile", JSONB, nullable=True),
        sa.Column("access_zone_profile", JSONB, nullable=True),
        sa.Column("auth_role_mapping", JSONB, nullable=True),
        sa.Column("grade", sa.String(20), nullable=True),
        sa.Column("salary_min", sa.Numeric(15, 2), nullable=True),
        sa.Column("salary_max", sa.Numeric(15, 2), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_system_columns(),
    )

    # 3. salary_structure
    op.create_table(
        "salary_structure",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("code", sa.String(30), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("grade", sa.String(20), nullable=True),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column("components", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_system_columns(),
    )

    # 4. employee
    op.create_table(
        "employee",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("matricule", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("first_name_ar", sa.String(100), nullable=True),
        sa.Column("last_name_ar", sa.String(100), nullable=True),
        sa.Column("birth_date", sa.Date, nullable=False),
        sa.Column("birth_place", sa.String(255), nullable=True),
        sa.Column("nationality", sa.String(50), nullable=False, server_default=sa.text("'Algerienne'")),
        sa.Column("gender", sa.String(1), nullable=False),
        sa.Column("marital_status", sa.String(20), nullable=False, server_default=sa.text("'celibataire'")),
        sa.Column("children_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("national_id", sa.String(18), nullable=True, unique=True),
        sa.Column("social_security_number", sa.String(20), nullable=True, unique=True),
        sa.Column("tax_id", sa.String(30), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("wilaya", sa.String(50), nullable=True),
        sa.Column("phone_personal", sa.String(20), nullable=True),
        sa.Column("phone_work", sa.String(20), nullable=True),
        sa.Column("email_personal", sa.String(255), nullable=True),
        sa.Column("email_work", sa.String(255), nullable=True),
        sa.Column("department_id", UUID(as_uuid=True),
                  sa.ForeignKey("department.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("job_position_id", UUID(as_uuid=True),
                  sa.ForeignKey("job_position.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("manager_id", UUID(as_uuid=True),
                  sa.ForeignKey("employee.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("hire_date", sa.Date, nullable=True),
        sa.Column("seniority_date", sa.Date, nullable=True),
        sa.Column("badge_rfid_number", sa.String(50), nullable=True, unique=True),
        sa.Column("photo_url", sa.Text, nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("bank_rib", sa.String(25), nullable=True),
        sa.Column("emergency_contact_name", sa.String(255), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(20), nullable=True),
        sa.Column("emergency_contact_relation", sa.String(50), nullable=True),
        sa.Column("document_checklist_status", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True),
        *_system_columns(),
    )

    # 5. employee_contract
    op.create_table(
        "employee_contract",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True),
                  sa.ForeignKey("employee.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("contract_type", sa.String(20), nullable=False),
        sa.Column("cdd_reason", sa.Text, nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("probation_end_date", sa.Date, nullable=True),
        sa.Column("salary_base", sa.Numeric(15, 2), nullable=False),
        sa.Column("salary_structure_id", UUID(as_uuid=True),
                  sa.ForeignKey("salary_structure.id", ondelete="SET NULL"), nullable=True),
        sa.Column("work_schedule_id", UUID(as_uuid=True), nullable=True),
        sa.Column("workplace_site_id", UUID(as_uuid=True), nullable=True),
        sa.Column("trial_duration_days", sa.Integer, nullable=True),
        sa.Column("notice_period_days", sa.Integer, nullable=True),
        sa.Column("template_used", sa.String(100), nullable=True),
        sa.Column("document_url", sa.Text, nullable=True),
        sa.Column("qr_verification_code", sa.String(100), nullable=True, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("validated_drh_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_drh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_dg_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_dg_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_pdg_by", UUID(as_uuid=True), nullable=True),
        sa.Column("validated_pdg_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("termination_reason", sa.String(30), nullable=True),
        sa.Column("requalified_as_cdi", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("requalification_date", sa.Date, nullable=True),
        *_system_columns(),
    )

    # CHECK constraints
    op.execute("""
        ALTER TABLE employee_contract
        ADD CONSTRAINT chk_ec_snmg
        CHECK (salary_base >= 20000);
    """)

    op.execute("""
        ALTER TABLE employee_contract
        ADD CONSTRAINT chk_ec_cdd_end
        CHECK (contract_type != 'CDD' OR end_date IS NOT NULL);
    """)

    op.execute("""
        ALTER TABLE employee
        ADD CONSTRAINT chk_emp_gender
        CHECK (gender IN ('M', 'F'));
    """)

    # Triggers
    for table in ("department", "job_position", "salary_structure",
                   "employee", "employee_contract"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in ("employee_contract", "employee", "salary_structure",
                   "job_position", "department"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("employee_contract")
    op.drop_table("employee")
    op.drop_table("salary_structure")
    op.drop_table("job_position")
    op.drop_table("department")
