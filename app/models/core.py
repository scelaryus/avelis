"""GFI Platform - SQLAlchemy ORM Models for core domain."""
import uuid as _uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey,
    Enum as SAEnum, JSON, Numeric, UniqueConstraint, Index, func, TypeDecorator,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# â”€â”€â”€ Custom type: String(36) that auto-converts UUID objects to str â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class UUIDString(TypeDecorator):
    """A String(36) column that transparently converts UUID objects to str."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and not isinstance(value, str):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        return value


# â”€â”€â”€ Enums â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class DocType(str, enum.Enum):
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    CONTRACT = "CONTRACT"
    BANK_STATEMENT = "BANK_STATEMENT"
    PAYROLL = "PAYROLL"
    ADV_CONTRACT = "ADV_CONTRACT"
    ADV_PAYMENT = "ADV_PAYMENT"
    CHEQUE = "CHEQUE"
    BON_COMMANDE = "BON_COMMANDE"
    DEVIS = "DEVIS"
    AVOIR = "AVOIR"
    BULLETIN_PAIE = "BULLETIN_PAIE"
    QUITTANCE = "QUITTANCE"
    ATTESTATION = "ATTESTATION"
    BON_LIVRAISON = "BON_LIVRAISON"
    OTHER = "OTHER"


class ArtifactType(str, enum.Enum):
    DOCUMENT = "DOCUMENT"
    RENDER = "RENDER"
    SEGMENT = "SEGMENT"
    OCR_TEXT = "OCR_TEXT"
    EXTRACTED_ENTITY_SET = "EXTRACTED_ENTITY_SET"
    NORMALIZED_ENTITY_SET = "NORMALIZED_ENTITY_SET"
    VERIFICATION_REPORT = "VERIFICATION_REPORT"
    MATCHING_PACKAGE = "MATCHING_PACKAGE"
    PROPOSED_LEDGER_PACKAGE = "PROPOSED_LEDGER_PACKAGE"
    ANOMALY_REPORT = "ANOMALY_REPORT"
    RESOLUTION_PATCH_OPTIONS = "RESOLUTION_PATCH_OPTIONS"
    COST_CENTER_SNAPSHOT = "COST_CENTER_SNAPSHOT"
    HR_PACKAGE = "HR_PACKAGE"
    ADV_PACKAGE = "ADV_PACKAGE"
    SUBMISSION_PACKAGE = "SUBMISSION_PACKAGE"


class WorkflowStatus(str, enum.Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    READY_TO_COMMIT = "READY_TO_COMMIT"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class JournalEntryStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"


class AnomalySeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


# â”€â”€â”€ Tenants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Tenant(Base):
    """Tenant = Company.  Each company is fully isolated."""
    __tablename__ = "tenants"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True)  # short code for display / URL
    logo_url = Column(String(500))
    description = Column(Text)
    address = Column(Text)
    phone = Column(String(50))
    email = Column(String(255))
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default={})
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# â”€â”€â”€ Users & RBAC â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="viewer")  # admin, accountant, hr_manager, sales, viewer, employee
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=True)  # link to Employee record
    is_active = Column(Boolean, default=True)
    mfa_secret = Column(String(64), nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )


# â”€â”€â”€ Documents â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Document(Base):
    __tablename__ = "documents"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    mime_type = Column(String(100))
    file_size = Column(Integer)
    sha256 = Column(String(64), nullable=False, index=True)
    storage_key = Column(String(500), nullable=False)
    doc_type = Column(SAEnum(DocType), default=DocType.OTHER)
    doc_type_confidence = Column(Float, default=0.0)
    page_count = Column(Integer, default=0)
    has_text_layer = Column(Boolean, default=False)
    text_layer_confidence = Column(Numeric(5, 4), default=0)
    metadata_ = Column("metadata", JSON, default={})
    uploaded_by = Column(String(36), ForeignKey("users.id"))
    # AI-extracted fields (populated on upload by document classifier)
    extracted_montant = Column(Numeric(18, 2), nullable=True)
    extracted_montant_ht = Column(Numeric(18, 2), nullable=True)
    extracted_tva = Column(Numeric(18, 2), nullable=True)
    extracted_date = Column(String(20), nullable=True)
    extracted_reference = Column(String(200), nullable=True)
    extracted_emetteur = Column(String(300), nullable=True)  # issuer / sender
    extracted_destinataire = Column(String(300), nullable=True)  # recipient
    classification_reasoning = Column(Text, nullable=True)
    import_session_id = Column(String(36), ForeignKey("import_sessions.id"), nullable=True, index=True)
    legal_case_id = Column(String(36), ForeignKey("legal_cases.id"), nullable=True, index=True)
    legal_folder_id = Column(String(36), ForeignKey("legal_case_folders.id"), nullable=True, index=True)
    module_routed_to = Column(String(50), nullable=True)  # comptabilite, adv, hr, documents
    realite_financiere = Column(String(3), nullable=True)  # RF1=Réel Déclaré, RF2=Réel Non Déclaré, RF3=Fictif
    # ── Organizational fields — link document to an entity & project ──
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True, index=True)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True, index=True)
    # ── Section 14: Pipeline status ──
    statut_ingestion = Column(String(20), default="INGERE")  # INGERE, A_COMPLETER, TRAITE, ERREUR
    champs_manquants = Column(JSON, default=[])  # ["montant", "date"] — fields AI couldn't extract
    # ── Section 15: Full-text search ──
    extracted_text = Column(Text, nullable=True)  # OCR/PDF text for full-text search
    ged_path = Column(String(500), nullable=True)  # Normalized: /{Entity}/{Project}/{Year}/{DocType}/{File}
    version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_documents_tenant_sha256", "tenant_id", "sha256"),
        Index("ix_documents_import_session", "import_session_id"),
    )


# â”€â”€â”€ Artifacts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Artifact(Base):
    __tablename__ = "artifacts"
    id = Column(UUIDString, primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=True)
    doc_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    artifact_type = Column(SAEnum(ArtifactType), nullable=False)
    data = Column(JSON, nullable=False)
    sha256 = Column(String(64))
    storage_key = Column(String(500))  # for large blobs in object storage
    algo_version = Column(String(50))
    ruleset_version = Column(String(50))
    model_version = Column(String(50))
    inputs_hash = Column(String(64))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_artifacts_type_doc", "artifact_type", "doc_id"),
        Index("ix_artifacts_workflow", "workflow_id"),
        Index("ix_artifacts_cache", "doc_id", "artifact_type", "inputs_hash"),
    )


# â”€â”€â”€ Workflows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    actor_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(SAEnum(WorkflowStatus), default=WorkflowStatus.CREATED)
    graph_type = Column(String(50), default="document_to_ledger")  # document_to_ledger, adv, hr
    doc_ids = Column(JSON, default=[])
    artifacts = Column(JSON, default={})  # {artifact_type: [artifact_id...]}
    blocking_reasons = Column(JSON, default=[])
    errors = Column(JSON, default=[])
    warnings = Column(JSON, default=[])
    decisions = Column(JSON, default=[])
    current_node = Column(String(100))
    node_history = Column(JSON, default=[])
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# â”€â”€â”€ Accounting â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(20), nullable=False)
    label = Column(String(255), nullable=False)
    account_type = Column(String(50))  # asset, liability, equity, revenue, expense
    parent_code = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_coa_tenant_code"),
    )


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(50), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True, index=True)
    journal_id = Column(String(36), ForeignKey("journaux.id"), nullable=True, index=True)
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=True)
    entry_date = Column(DateTime, nullable=False)
    reference = Column(String(100))
    description = Column(Text)
    status = Column(SAEnum(JournalEntryStatus), default=JournalEntryStatus.PROPOSED)
    period_id = Column(String(36), ForeignKey("accounting_periods.id"))
    realite_financiere = Column(String(4))  # RF1/RF2/RF3/RF4
    source_doc_ids = Column(JSON, default=[])
    evidence_anchor_ids = Column(JSON, default=[])
    assumptions = Column(JSON, default=[])
    committed_by = Column(String(36), ForeignKey("users.id"))
    committed_at = Column(DateTime)
    auto_generated = Column(Boolean, default=False)  # True if system-generated (R-002)
    created_at = Column(DateTime, server_default=func.now())


class JournalLine(Base):
    __tablename__ = "journal_lines"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    entry_id = Column(String(36), ForeignKey("journal_entries.id"), nullable=False)
    line_no = Column(Integer, default=0)
    account_code = Column(String(20), nullable=False)
    label = Column(String(500))
    debit = Column(Numeric(18, 2), default=0)
    credit = Column(Numeric(18, 2), default=0)
    currency = Column(String(3), default="DZD")
    evidence_anchors = Column(JSON, default=[])
    cost_center_code = Column(String(50))
    project_code = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())


# â”€â”€â”€ Evidence Anchors â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class EvidenceAnchor(Base):
    __tablename__ = "evidence_anchors"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    doc_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    page = Column(Integer, nullable=False)
    bbox = Column(JSON)  # [x0, y0, x1, y1] normalized 0..1
    text_snippet = Column(Text)
    field_name = Column(String(100))
    confidence = Column(Float)
    ocr_block_index = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


# â”€â”€â”€ Anomalies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AnomalyRecord(Base):
    __tablename__ = "anomaly_records"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=False)
    doc_id = Column(String(36), ForeignKey("documents.id"))
    anomaly_code = Column(String(100), nullable=False)
    severity = Column(SAEnum(AnomalySeverity), nullable=False)
    description = Column(Text)
    details = Column(JSON, default={})
    is_resolved = Column(Boolean, default=False)
    resolution = Column(JSON)
    resolved_by = Column(String(36), ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())


# â”€â”€â”€ Audit Log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(String(100))
    old_value = Column(JSON)
    new_value = Column(JSON)
    ip_address = Column(String(45))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_tenant_date", "tenant_id", "created_at"),
    )


# â”€â”€â”€ Cost Centers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CostCenter(Base):
    __tablename__ = "cost_centers"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    parent_code = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_cc_tenant_code"),
    )


class CostCenterAllocation(Base):
    __tablename__ = "cost_center_allocations"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    cost_center_code = Column(String(50), nullable=False)
    period_id = Column(String(36), ForeignKey("accounting_periods.id"))
    total_debit = Column(Numeric(18, 2), default=0)
    total_credit = Column(Numeric(18, 2), default=0)
    snapshot_data = Column(JSON, default={})
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Import Sessions (Table #11) — bulk upload tracking
# ────────────────────────────────────────────────────────────────────────────

class ImportSessionStatus(str, enum.Enum):
    EN_COURS = "EN_COURS"
    TERMINE = "TERMINE"
    ERREUR = "ERREUR"
    PARTIEL = "PARTIEL"


class ImportSourceType(str, enum.Enum):
    PC_FOLDER = "PC_FOLDER"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"


class ImportSession(Base):
    """Tracks bulk file import sessions with AI processing."""
    __tablename__ = "import_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    source_type = Column(SAEnum(ImportSourceType), nullable=False, default=ImportSourceType.PC_FOLDER)
    source_path = Column(String(500), nullable=True)  # folder path or Google Drive folder ID
    processing_mode = Column(String(50), default="FULL_AUTO")  # FULL_AUTO | CLASSIFY_ONLY
    nombre_fichiers = Column(Integer, nullable=False, default=0)
    fichiers_traites = Column(Integer, default=0)
    fichiers_erreur = Column(Integer, default=0)
    fichiers_dupliques = Column(Integer, default=0)
    statut = Column(SAEnum(ImportSessionStatus), default=ImportSessionStatus.EN_COURS)
    erreurs = Column(JSON, default=[])
    resultats = Column(JSON, default=[])  # per-file results: [{filename, doc_id, status, doc_type, routed_to}]
    date_import = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Versions Documents (Table #13) — document versioning
# ────────────────────────────────────────────────────────────────────────────

class VersionDocument(Base):
    """Document version history."""
    __tablename__ = "versions_documents"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    numero_version = Column(Integer, nullable=False)
    hash_sha256 = Column(String(64), nullable=False)
    chemin_fichier = Column(String(500))
    taille_octets = Column(Integer)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("document_id", "numero_version", name="uq_doc_version"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Archivage Physique (Table #14) — physical document storage location
# ────────────────────────────────────────────────────────────────────────────

class ArchivagePhysique(Base):
    """Physical archive location for documents."""
    __tablename__ = "archivage_physique"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    emplacement = Column(String(200))
    armoire = Column(String(50))
    etagere = Column(String(50))
    boite = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Document Segments (Table #48) — large file segmentation
# ────────────────────────────────────────────────────────────────────────────

class DocumentSegment(Base):
    """Segments of large documents processed by AI models."""
    __tablename__ = "document_segments"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    numero_segment = Column(Integer, nullable=False)
    nombre_total_segments = Column(Integer, nullable=False)
    page_debut = Column(Integer)
    page_fin = Column(Integer)
    onglet_excel = Column(String(100))
    ligne_debut = Column(Integer)
    ligne_fin = Column(Integer)
    modele_ia_utilise = Column(String(50), nullable=False)
    texte_extrait = Column(Text)
    donnees_extraites = Column(JSON)
    certitude_globale = Column(Numeric(5, 2))
    temps_traitement_ms = Column(Integer)
    tokens_utilises = Column(Integer)
    est_consolide = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("document_id", "numero_segment", name="uq_doc_segment"),
        Index("ix_segment_document", "document_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# IA Extraction Log (Table #49) — AI request traceability
# ────────────────────────────────────────────────────────────────────────────

class IAExtractionLog(Base):
    """AI extraction request log for traceability and cost tracking."""
    __tablename__ = "ia_extraction_log"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    segment_id = Column(String(36), ForeignKey("document_segments.id"), nullable=True)
    modele = Column(String(50), nullable=False)
    type_requete = Column(String(50), nullable=False)  # EXTRACTION, CLASSIFICATION, VALIDATION
    prompt_resume = Column(Text)
    reponse_json = Column(JSON)
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    cout_estime = Column(Numeric(8, 4))  # USD
    temps_ms = Column(Integer)
    succes = Column(Boolean, default=True)
    erreur = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_ia_log_document", "document_id"),
        Index("ix_ia_log_date", "created_at"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Vérifications Hash (Table #36) — SHA-256 non-regression
# ────────────────────────────────────────────────────────────────────────────

class VerificationHash(Base):
    """SHA-256 hash verification for non-regression on closed records."""
    __tablename__ = "verifications_hash"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    table_cible = Column(String(100), nullable=False)
    enregistrement_id = Column(String(36), nullable=False)
    hash_sha256 = Column(String(64), nullable=False)
    donnees_hashees = Column(JSON)
    est_cloture = Column(Boolean, default=False)
    date_cloture = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_verif_hash_table", "table_cible", "enregistrement_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# User Permissions — per-user, per-module read/write access control
# ────────────────────────────────────────────────────────────────────────────

class UserPermission(Base):
    """Per-user module-level access override.

    When a user has UserPermission rows, those take precedence over the
    role-based default permissions in rbac.py.  If no rows exist the
    system falls back to the role matrix.
    """
    __tablename__ = "user_permissions"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    module = Column(String(100), nullable=False)
    can_read = Column(Boolean, default=False)
    can_write = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "module", name="uq_user_permission_module"),
        Index("ix_user_permissions_user", "user_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Workflow Dossiers (Table #30) — 7-phase pipeline
# ────────────────────────────────────────────────────────────────────────────

class WorkflowDossierStatut(str, enum.Enum):
    EN_COURS = "EN_COURS"
    BLOQUE = "BLOQUE"
    TERMINE = "TERMINE"


class WorkflowDossier(Base):
    """Document processing pipeline (7 phases)."""
    __tablename__ = "workflow_dossiers"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    phase_actuelle = Column(Integer, nullable=False, default=0)
    score_actuel = Column(Integer, default=0)
    statut = Column(SAEnum(WorkflowDossierStatut), default=WorkflowDossierStatut.EN_COURS)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("phase_actuelle >= 0 AND phase_actuelle <= 6",
                         name="ck_wd_phase_range"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Workflow Phases Log (Table #31) — transition history
# ────────────────────────────────────────────────────────────────────────────

class WorkflowPhaseLog(Base):
    """Workflow phase transition history."""
    __tablename__ = "workflow_phases_log"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    dossier_id = Column(String(36), ForeignKey("workflow_dossiers.id"), nullable=False)
    phase = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)  # PRODUCTION, VERIFICATION, TEST
    score = Column(Integer)
    resultat = Column(JSON)
    erreurs = Column(Text)
    duree_ms = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_wf_phase_log_dossier", "dossier_id", "phase"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Demandes de Complétion (Table #32) — intelligent blocking
# ────────────────────────────────────────────────────────────────────────────

class PrioriteCompletion(str, enum.Enum):
    NORMALE = "NORMALE"
    IMPORTANTE = "IMPORTANTE"
    CRITIQUE = "CRITIQUE"


class StatutCompletion(str, enum.Enum):
    DETECTE = "DETECTE"
    BLOQUE = "BLOQUE"
    NOTIFIE_4H = "NOTIFIE_4H"
    NOTIFIE_24H = "NOTIFIE_24H"
    NOTIFIE_72H = "NOTIFIE_72H"
    EN_RESOLUTION = "EN_RESOLUTION"
    RESOLU = "RESOLU"
    AUDIT = "AUDIT"


class DemandeCompletion(Base):
    """Intelligent blocking & completion requests."""
    __tablename__ = "demandes_completion"
    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    dossier_id = Column(String(36), ForeignKey("workflow_dossiers.id"), nullable=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    type_demande = Column(String(50), nullable=False)  # SAISIE_CHAMP, UPLOAD_FICHIER, VALIDATION_CHOIX
    champ_manquant = Column(String(100))
    message = Column(Text, nullable=False)
    format_attendu = Column(String(200))
    priorite = Column(SAEnum(PrioriteCompletion), default=PrioriteCompletion.NORMALE)
    statut = Column(SAEnum(StatutCompletion), default=StatutCompletion.DETECTE)
    reponse = Column(Text)
    demandeur_id = Column(String(36), ForeignKey("users.id"))
    repondeur_id = Column(String(36), ForeignKey("users.id"))
    fichier_joint_id = Column(String(36), ForeignKey("documents.id"))
    date_detection = Column(DateTime)
    date_resolution = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_demande_statut", "statut"),
        Index("ix_demande_dossier", "dossier_id"),
    )
