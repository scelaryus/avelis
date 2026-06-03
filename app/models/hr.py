"""
GFI v7.0 — HR Foundation: Employee, Contract, Department, JobPosition,
SalaryStructure, SalaryComponent.

Employee lifecycle: draft -> onboarding -> active -> suspended -> offboarding -> archived
Contract: draft -> pending_validation -> validated_drh -> validated_dg -> validated_pdg -> active
CDD requalification: auto CDI if continues past end_date without renewal.
22 DRH AI agents coordinate via LangGraph event cascade.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Department(GFIBase, Base):
    """Organizational department within an entity."""

    __tablename__ = "department"

    code = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    name_ar = Column(String(255), nullable=True)
    parent_department_id = Column(
        UUID(as_uuid=True), ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True,
    )
    manager_id = Column(UUID(as_uuid=True), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    parent = relationship("Department", remote_side="Department.id")

    def __repr__(self):
        return f"<Department {self.code} {self.name}>"


class JobPosition(GFIBase, Base):
    """Job position definition with skills, equipment, and access profiles."""

    __tablename__ = "job_position"

    code = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    title_ar = Column(String(255), nullable=True)
    department_id = Column(
        UUID(as_uuid=True), ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    required_skills = Column(JSONB, nullable=True)
    equipment_profile = Column(JSONB, nullable=True)
    access_zone_profile = Column(JSONB, nullable=True)
    auth_role_mapping = Column(JSONB, nullable=True)
    # e.g., ["CHEF_CHANTIER"] -> auto-assigned on hire

    grade = Column(String(20), nullable=True)
    salary_min = Column(Numeric(15, 2), nullable=True)
    salary_max = Column(Numeric(15, 2), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    def __repr__(self):
        return f"<JobPosition {self.code} {self.title}>"


class SalaryStructure(GFIBase, Base):
    """Salary structure: defines pay components per grade/entity."""

    __tablename__ = "salary_structure"

    code = Column(String(30), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    grade = Column(String(20), nullable=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    components = Column(JSONB, nullable=False)
    # [{code, name, type: FIXE/VARIABLE/PRIME, amount_or_rate, taxable, cnas_subject}]
    is_active = Column(Boolean, nullable=False, server_default="true")

    def __repr__(self):
        return f"<SalaryStructure {self.code} {self.name}>"


class Employee(GFIBase, Base):
    """Full employee record per CDC-DRH section 1.3.1."""

    __tablename__ = "employee"

    # ── Identity ─────────────────────────────────────────────────────────
    matricule = Column(String(20), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    first_name_ar = Column(String(100), nullable=True)
    last_name_ar = Column(String(100), nullable=True)

    birth_date = Column(Date, nullable=False)
    birth_place = Column(String(255), nullable=True)
    nationality = Column(String(50), nullable=False, server_default="'Algerienne'")
    gender = Column(String(1), nullable=False)  # M or F

    # ── Family ───────────────────────────────────────────────────────────
    marital_status = Column(String(20), nullable=False, server_default="'celibataire'")
    children_count = Column(Integer, nullable=False, server_default="0")

    # ── Official IDs ─────────────────────────────────────────────────────
    national_id = Column(String(18), nullable=True, unique=True)
    social_security_number = Column(String(20), nullable=True, unique=True)
    tax_id = Column(String(30), nullable=True)

    # ── Contact ──────────────────────────────────────────────────────────
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    wilaya = Column(String(50), nullable=True)
    phone_personal = Column(String(20), nullable=True)
    phone_work = Column(String(20), nullable=True)
    email_personal = Column(String(255), nullable=True)
    email_work = Column(String(255), nullable=True)

    # ── Assignment ───────────────────────────────────────────────────────
    department_id = Column(
        UUID(as_uuid=True), ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    job_position_id = Column(
        UUID(as_uuid=True), ForeignKey("job_position.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    manager_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Dates ────────────────────────────────────────────────────────────
    hire_date = Column(Date, nullable=True)
    seniority_date = Column(Date, nullable=True)

    # ── Badge ────────────────────────────────────────────────────────────
    badge_rfid_number = Column(String(50), nullable=True, unique=True)
    photo_url = Column(Text, nullable=True)

    # ── Banking ──────────────────────────────────────────────────────────
    bank_name = Column(String(100), nullable=True)
    bank_rib = Column(String(25), nullable=True)

    # ── Emergency contact ────────────────────────────────────────────────
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    emergency_contact_relation = Column(String(50), nullable=True)

    # ── Documents ────────────────────────────────────────────────────────
    document_checklist_status = Column(JSONB, nullable=True)

    # ── Lifecycle ────────────────────────────────────────────────────────
    # DRAFT, ONBOARDING, ACTIVE, SUSPENDED, OFFBOARDING, ARCHIVED
    status = Column(String(20), nullable=False, server_default="'DRAFT'")

    # ── Auth link ────────────────────────────────────────────────────────
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    department = relationship("Department")
    job_position = relationship("JobPosition")
    manager = relationship("Employee", remote_side="Employee.id")

    def __repr__(self):
        return f"<Employee {self.matricule} {self.first_name} {self.last_name}>"


class EmployeeContract(GFIBase, Base):
    """Employment contract with triple validation and CDD requalification."""

    __tablename__ = "employee_contract"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Type ─────────────────────────────────────────────────────────────
    contract_type = Column(String(20), nullable=False)
    # CDI, CDD, CHANTIER, STAGE, INTERIM
    cdd_reason = Column(Text, nullable=True)
    # MANDATORY if CDD (Article 12, Loi 90-11)

    # ── Dates ────────────────────────────────────────────────────────────
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    # MANDATORY for CDD/CHANTIER/STAGE
    probation_end_date = Column(Date, nullable=True)

    # ── Salary ───────────────────────────────────────────────────────────
    salary_base = Column(Numeric(15, 2), nullable=False)
    # >= 20000 (SNMG)
    salary_structure_id = Column(
        UUID(as_uuid=True), ForeignKey("salary_structure.id", ondelete="SET NULL"),
        nullable=True,
    )
    work_schedule_id = Column(UUID(as_uuid=True), nullable=True)
    workplace_site_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Notice / trial ───────────────────────────────────────────────────
    trial_duration_days = Column(Integer, nullable=True)
    notice_period_days = Column(Integer, nullable=True)

    # ── Document ─────────────────────────────────────────────────────────
    template_used = Column(String(100), nullable=True)
    document_url = Column(Text, nullable=True)
    qr_verification_code = Column(String(100), nullable=True, unique=True)

    # ── Triple validation: DRH -> DG -> PDG ──────────────────────────────
    # DRAFT, PENDING_VALIDATION, VALIDATED_DRH, VALIDATED_DG,
    # VALIDATED_PDG, ACTIVE, SUSPENDED, TERMINATED, ARCHIVED
    status = Column(String(20), nullable=False, server_default="'DRAFT'")

    validated_drh_by = Column(UUID(as_uuid=True), nullable=True)
    validated_drh_at = Column(DateTime(timezone=True), nullable=True)
    validated_dg_by = Column(UUID(as_uuid=True), nullable=True)
    validated_dg_at = Column(DateTime(timezone=True), nullable=True)
    validated_pdg_by = Column(UUID(as_uuid=True), nullable=True)
    validated_pdg_at = Column(DateTime(timezone=True), nullable=True)

    # ── Termination ──────────────────────────────────────────────────────
    termination_date = Column(Date, nullable=True)
    termination_reason = Column(String(30), nullable=True)
    # FIN_CDD, FIN_CHANTIER, DEMISSION, LICENCIEMENT_FAUTE,
    # LICENCIEMENT_ECONOMIQUE, RETRAITE, DECES, ACCORD_MUTUEL

    # ── CDD requalification flag ─────────────────────────────────────────
    requalified_as_cdi = Column(Boolean, nullable=False, server_default="false")
    requalification_date = Column(Date, nullable=True)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<EmployeeContract {self.contract_type} {self.status}>"
