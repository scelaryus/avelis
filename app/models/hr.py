"""GFI Platform - HR domain models."""
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey,
    Enum as SAEnum, Numeric, Date, JSON, func
)
from app.database import Base
import enum


class EmploymentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    TERMINATED = "TERMINATED"
    ON_LEAVE = "ON_LEAVE"


class PayrollStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"


class Employee(Base):
    __tablename__ = "employees"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    employee_number = Column(String(50), nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    professional_address = Column(Text)
    activities = Column(Text)
    hire_date = Column(Date)
    upcoming_activity_due_date = Column(Date)
    termination_date = Column(Date)
    status = Column(SAEnum(EmploymentStatus), default=EmploymentStatus.ACTIVE)
    is_active = Column(Boolean, default=True)
    department = Column(String(100))
    position = Column(String(255))
    cost_center_code = Column(String(50))
    base_salary = Column(Numeric(18, 2))
    currency = Column(String(3), default="DZD")
    bank_account = Column(String(50))
    tax_id = Column(String(50))
    social_security_number = Column(String(50))
    # ── Extensions for SPI & Org hierarchy ──
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=True)
    manager_id = Column(String(36), ForeignKey("employees.id"), nullable=True)
    mentor_id = Column(String(36), ForeignKey("employees.id"), nullable=True)
    function_category = Column(String(50))  # SUPPORT, COMMERCIAL, etc.
    company = Column(String(255))  # company name from employee dataset
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # linked User account
    metadata_ = Column("metadata", JSON, default={})
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PayrollProposal(Base):
    __tablename__ = "payroll_proposals"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    period_id = Column(String(36), ForeignKey("accounting_periods.id"))
    period_label = Column(String(50))
    status = Column(SAEnum(PayrollStatus), default=PayrollStatus.DRAFT)
    gross_salary = Column(Numeric(18, 2))
    deductions = Column(JSON, default={})  # {type: amount}
    contributions = Column(JSON, default={})  # employer contributions
    net_salary = Column(Numeric(18, 2))
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id"))
    notes = Column(Text)
    created_by = Column(String(36), ForeignKey("users.id"))
    approved_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TaskApprovalStatus(str, enum.Enum):
    PENDING_ESTIMATE = "PENDING_ESTIMATE"  # assigned, awaiting employee estimate
    ESTIMATED = "ESTIMATED"               # employee submitted estimate
    APPROVED = "APPROVED"                  # manager approved estimate or overrode
    IN_PROGRESS = "IN_PROGRESS"            # employee working on it
    PROOF_SUBMITTED = "PROOF_SUBMITTED"    # employee uploaded proof
    AI_EVALUATED = "AI_EVALUATED"          # AI scored the proof
    VALIDATED = "VALIDATED"                # manager validated AI score → affects payroll
    REJECTED = "REJECTED"                  # manager rejected proof/estimate


class HRTask(Base):
    __tablename__ = "hr_tasks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"))
    employee_id = Column(String(36), ForeignKey("employees.id"))
    task_type = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    plan_date = Column(Date, nullable=False)
    required_role = Column(String(100))
    source_text = Column(Text)
    status = Column(String(50), default="pending")  # pending, in_progress, completed, cancelled
    assigned_to = Column(String(36), ForeignKey("users.id"))
    due_date = Column(Date)
    completed_at = Column(DateTime)
    completed_by = Column(String(36), ForeignKey("users.id"))
    created_by = Column(String(36), ForeignKey("users.id"))
    # ── Estimate & Approval workflow ──
    approval_status = Column(SAEnum(TaskApprovalStatus), default=TaskApprovalStatus.PENDING_ESTIMATE)
    employee_estimated_time = Column(Float)  # hours
    employee_estimated_price = Column(Numeric(18, 2))  # billable value
    estimated_at = Column(DateTime)
    manager_final_time = Column(Float)  # manager-approved hours
    manager_final_price = Column(Numeric(18, 2))  # manager-approved billable value
    manager_approved_at = Column(DateTime)
    manager_approved_by = Column(String(36), ForeignKey("users.id"))
    # ── Proof & AI evaluation ──
    proof_document_id = Column(String(36), ForeignKey("documents.id"))  # uploaded proof
    proof_uploaded_at = Column(DateTime)
    ai_score = Column(Float)  # 0-100 score from AI evaluation
    ai_note = Column(Text)    # AI textual assessment
    ai_evaluated_at = Column(DateTime)
    manager_validated = Column(Boolean, default=False)  # manager approved/rejected AI score
    manager_validated_at = Column(DateTime)
    # ── Manager rating & salary adjust ──
    manager_rating = Column(Integer)
    manager_feedback = Column(Text)
    rated_at = Column(DateTime)
    salary_adjustment_amount = Column(Numeric(18, 2), default=0)
    salary_adjustment_applied = Column(Boolean, default=False)
    metadata_ = Column("metadata", JSON, default={})
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TaskNotification(Base):
    __tablename__ = "task_notifications"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    task_id = Column(String(36), ForeignKey("hr_tasks.id"), nullable=False)
    employee_id = Column(String(36), ForeignKey("employees.id"))
    user_id = Column(String(36), ForeignKey("users.id"))
    title = Column(String(255), nullable=False)
    message = Column(Text)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
