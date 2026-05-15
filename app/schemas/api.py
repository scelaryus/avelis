"""GFI Platform - API request/response schemas.

Aligned with ORM models in app/models/core.py, hr.py, adv.py.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from uuid import UUID


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str
    company_id: Optional[str] = None  # kept for backward compat


class UserCreate(BaseModel):
    tenant_id: UUID
    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "viewer"
    employee_id: Optional[UUID] = None


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    employee_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None
    company: Optional[dict] = None  # {id, name, code, logo_url}


class CompanyResponse(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}


# ─── Document ────────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    sha256: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    storage_key: Optional[str] = None
    uploaded_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    is_duplicate: bool = False
    realite_financiere: Optional[str] = None  # RF1/RF2/RF3/RF4
    # AI classification fields
    doc_type: Optional[str] = None
    doc_type_confidence: Optional[float] = None
    extracted_montant: Optional[float] = None
    extracted_montant_ht: Optional[float] = None
    extracted_tva: Optional[float] = None
    extracted_date: Optional[str] = None
    extracted_reference: Optional[str] = None
    extracted_emetteur: Optional[str] = None
    extracted_destinataire: Optional[str] = None
    classification_reasoning: Optional[str] = None
    module_routed_to: Optional[str] = None
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    statut_ingestion: Optional[str] = None
    ged_path: Optional[str] = None
    adv_record_id: Optional[str] = None
    champs_manquants: Optional[list] = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


# ─── Workflow ────────────────────────────────────────────────────────────────

class WorkflowResponse(BaseModel):
    id: UUID
    status: str
    graph_type: str
    doc_ids: list = []
    artifacts: dict = {}
    blocking_reasons: list = []
    errors: list = []
    warnings: list = []
    current_node: Optional[str] = None
    node_history: list = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_detail: Optional[str] = None

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int
    page: int
    page_size: int


# ─── Accounting ──────────────────────────────────────────────────────────────

class COACreate(BaseModel):
    code: str
    label: str
    account_type: Optional[str] = None
    parent_code: Optional[str] = None


class COAResponse(BaseModel):
    id: UUID
    code: str
    label: str
    account_type: Optional[str] = None
    parent_code: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    id: UUID
    workflow_id: Optional[UUID] = None
    entry_date: Optional[datetime] = None
    reference: Optional[str] = None
    description: Optional[str] = None
    status: str
    source_doc_ids: list[str] = []
    lines: list = []

    model_config = {"from_attributes": True}


class JournalEntryListResponse(BaseModel):
    items: list[JournalEntryResponse]
    total: int
    page: int
    page_size: int


class JournalLineCreate(BaseModel):
    account_code: str
    label: Optional[str] = None
    debit: float = 0
    credit: float = 0
    cost_center_code: Optional[str] = None
    project_code: Optional[str] = None


class JournalEntryCreate(BaseModel):
    entry_date: date
    reference: Optional[str] = None
    description: Optional[str] = None
    entreprise_id: Optional[str] = None
    journal_id: Optional[str] = None
    period_id: Optional[str] = None
    realite_financiere: Optional[str] = None  # RF1/RF2/RF3/RF4
    source_doc_ids: list[str] = Field(default=[], description="Document IDs that justify this entry")
    lines: list[JournalLineCreate] = Field(..., min_length=1)


class DocumentCorrection(BaseModel):
    """Correction of AI-classified document fields."""
    doc_type: Optional[str] = None
    extracted_montant: Optional[float] = None
    extracted_montant_ht: Optional[float] = None
    extracted_tva: Optional[float] = None
    extracted_date: Optional[str] = None
    extracted_reference: Optional[str] = None
    extracted_emetteur: Optional[str] = None
    extracted_destinataire: Optional[str] = None


class PeriodCreate(BaseModel):
    name: str
    start_date: datetime
    end_date: datetime


class PeriodResponse(BaseModel):
    id: UUID
    name: str
    start_date: datetime
    end_date: datetime
    is_closed: bool = False

    model_config = {"from_attributes": True}


# ─── HR ──────────────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    employee_number: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    professional_address: Optional[str] = None
    activities: Optional[str] = None
    hire_date: Optional[date] = None
    upcoming_activity_due_date: Optional[date] = None
    department: Optional[str] = None
    position: Optional[str] = None
    manager_name: Optional[str] = None
    mentor_name: Optional[str] = None
    company: Optional[str] = None
    is_active: bool = True
    status: Optional[str] = None
    cost_center_code: Optional[str] = None
    base_salary: Optional[float] = None
    currency: str = "DZD"
    social_security_number: Optional[str] = None


class EmployeeResponse(BaseModel):
    id: UUID
    employee_number: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    professional_address: Optional[str] = None
    activities: Optional[str] = None
    user_id: Optional[UUID] = None
    is_active: bool = True
    status: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    manager_name: Optional[str] = None
    mentor_name: Optional[str] = None
    company: Optional[str] = None
    base_salary: Optional[float] = None
    hire_date: Optional[date] = None
    upcoming_activity_due_date: Optional[date] = None
    social_security_number: Optional[str] = None
    created_at: Optional[datetime] = None
    # SPI / Paie fields (GFI v7)
    prime_spi_plafond: Optional[float] = None
    avenant_spi_signe: bool = False
    solde_bonus_malus: Optional[float] = None
    spi_courant: Optional[float] = None
    mois_consecutifs_sous_50: int = 0
    mois_consecutifs_sous_70: int = 0
    statut_rh: Optional[str] = None
    est_commercial: bool = False
    objectif_ventes_mensuel: Optional[float] = None
    palier_commercial: Optional[str] = None

    model_config = {"from_attributes": True}


class PayrollResponse(BaseModel):
    id: UUID
    employee_id: UUID
    period_label: Optional[str] = None
    status: Optional[str] = None
    gross_salary: Optional[float] = None
    net_salary: Optional[float] = None
    deductions: dict = {}
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── ADV ─────────────────────────────────────────────────────────────────────

# ClientCreate and ContractCreate and PaymentCreate moved to bottom with project fields


class ClientResponse(BaseModel):
    id: UUID
    code: str
    name: str
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    ice: Optional[str] = None
    is_active: bool = True
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    payment_terms_days: Optional[int] = 30
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ContractResponse(BaseModel):
    id: UUID
    client_id: UUID
    contract_number: str
    title: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    total_amount: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaymentResponse(BaseModel):
    id: UUID
    client_id: UUID
    amount: float
    payment_date: date
    payment_method: Optional[str] = None
    payment_ref: Optional[str] = None
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}



# ─── HR Task Workflow ────────────────────────────────────────────────────────

class TaskEstimateBody(BaseModel):
    estimated_time: float = Field(..., gt=0, description="Hours estimated")
    estimated_price: float = Field(..., ge=0, description="Billable value estimated")


class TaskApproveBody(BaseModel):
    approved: bool = True
    final_time: Optional[float] = None   # if None, keep employee estimate
    final_price: Optional[float] = None  # if None, keep employee estimate
    feedback: Optional[str] = None


class TaskValidateBody(BaseModel):
    validated: bool = True  # manager approves or rejects AI result


class CreateEmployeeAccountBody(BaseModel):
    employee_id: str
    email: Optional[str] = None
    password: str = Field(..., min_length=6)
    role: str = "employee"


class UpdateUserRoleBody(BaseModel):
    role: str


# ─── User Permissions ────────────────────────────────────────────────────────

class ModulePermissionItem(BaseModel):
    """Single module permission entry."""
    module: str
    can_read: bool = False
    can_write: bool = False


class SetUserPermissionsBody(BaseModel):
    """Bulk-set per-user module permissions."""
    permissions: list[ModulePermissionItem] = Field(
        ..., min_length=1, description="List of module permissions to set",
    )


class UserPermissionResponse(BaseModel):
    module: str
    can_read: bool
    can_write: bool

    model_config = {"from_attributes": True}


class UserDetailResponse(BaseModel):
    """Extended user response with employee info and permissions."""
    id: str
    tenant_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    permissions: list[UserPermissionResponse] = []
    created_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    id: str
    task_id: str
    title: str
    message: Optional[str] = None
    is_read: bool
    task_title: Optional[str] = None
    created_at: Optional[datetime] = None


# ─── ADV Project-scoped ──────────────────────────────────────────────────────

class ClientCreate(BaseModel):
    code: Optional[str] = None  # Auto-generated if not provided
    name: str
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    ice: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    payment_terms_days: int = 30
    account_code: Optional[str] = None
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None


class ContractCreate(BaseModel):
    client_id: UUID
    contract_number: str
    title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_amount: Optional[float] = None
    currency: str = "DZD"
    terms: dict = {}
    notes: Optional[str] = None
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None


class ReceivableCreate(BaseModel):
    client_id: UUID
    contract_id: Optional[UUID] = None
    invoice_ref: str
    amount: float
    due_date: date
    currency: str = "DZD"
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    realite_financiere: str = "RF1"


class ReceivableResponse(BaseModel):
    id: UUID
    client_id: UUID
    contract_id: Optional[UUID] = None
    invoice_ref: Optional[str] = None
    amount: float
    amount_paid: float = 0
    remaining: float = 0
    due_date: Optional[date] = None
    status: Optional[str] = None
    is_overdue: bool = False
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaymentCreate(BaseModel):
    client_id: UUID
    receivable_id: Optional[UUID] = None
    payment_ref: Optional[str] = None
    amount: float
    payment_date: date
    payment_method: Optional[str] = None
    bank_ref: Optional[str] = None
    notes: Optional[str] = None
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    realite_financiere: str = "RF1"  # RF1=Réel Déclaré, RF2=Réel Non Déclaré, RF3=Fictif

