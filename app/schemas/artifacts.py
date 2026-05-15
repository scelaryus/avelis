"""GFI Platform - Pydantic schemas for all canonical artifacts."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal


# ─── Evidence Anchor ─────────────────────────────────────────────────────────

class EvidenceAnchorSchema(BaseModel):
    doc_id: str
    page: int
    bbox: list[float] = Field(..., min_length=4, max_length=4, description="[x0, y0, x1, y1] normalized 0..1")
    text_snippet: Optional[str] = None
    field_name: Optional[str] = None
    confidence: Optional[float] = None
    ocr_block_index: Optional[int] = None


# ─── OCR Artifacts ───────────────────────────────────────────────────────────

class OCRBlockProvenance(BaseModel):
    engine: str
    engine_version: Optional[str] = None


class OCRBlock(BaseModel):
    text: str
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    confidence: float
    provenance: Optional[OCRBlockProvenance] = None
    source: Optional[str] = None  # OCR, TEXT_LAYER


class OCRTextArtifact(BaseModel):
    doc_id: str
    page: int
    source: Literal["OCR", "TEXT_LAYER", "MERGED"]
    blocks: list[OCRBlock]


# ─── Document Artifact ───────────────────────────────────────────────────────

class DocumentArtifact(BaseModel):
    doc_id: str
    filename: str
    mime_type: str
    file_size: int
    sha256: str
    storage_key: str
    page_count: int = 0
    doc_type_guess: Optional[str] = None
    doc_type_confidence: float = 0.0


# ─── Render Artifact ─────────────────────────────────────────────────────────

class RenderArtifact(BaseModel):
    doc_id: str
    page: int
    width: int
    height: int
    dpi: int
    format: str = "png"
    storage_key: str


# ─── Segment Artifact ────────────────────────────────────────────────────────

class SegmentRegion(BaseModel):
    segment_type: str  # header, table, footer, line_items, signature, text_block
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    confidence: float


class SegmentArtifact(BaseModel):
    doc_id: str
    page: int
    regions: list[SegmentRegion]


# ─── DocType Classification ──────────────────────────────────────────────────

class DocTypeClassification(BaseModel):
    doc_id: str
    doc_type: Literal[
        "INVOICE", "RECEIPT", "CONTRACT", "BANK_STATEMENT",
        "PAYROLL", "ADV_CONTRACT", "ADV_PAYMENT", "OTHER"
    ]
    confidence: float
    explanations: list[str] = []


# ─── Extracted Entity ────────────────────────────────────────────────────────

class ExtractedField(BaseModel):
    field_name: str
    value: Optional[str | float | int | bool | dict | list] = None
    confidence: float
    evidence_anchor: Optional[EvidenceAnchorSchema] = None


class ExtractedEntitySet(BaseModel):
    doc_id: str
    doc_type: str
    fields: list[ExtractedField]
    missing_fields: list[dict] = []  # [{field_name, reason}]
    line_items: Optional[list[dict]] = None  # table rows for invoices


# ─── Normalized Entity ───────────────────────────────────────────────────────

class NormalizedField(BaseModel):
    field_name: str
    original_value: Optional[str | float | int | bool] = None
    normalized_value: Optional[str | float | int | bool] = None
    normalization_applied: list[str] = []  # description of transforms


class NormalizedEntitySet(BaseModel):
    doc_id: str
    doc_type: str
    fields: list[NormalizedField]
    derived_checks: list[dict] = []  # e.g., {check: "HT+TVA=TTC", result: "OK"}
    line_items: Optional[list[dict]] = None


# ─── Verification Report ─────────────────────────────────────────────────────

class VerificationCheck(BaseModel):
    check_code: str
    result: Literal["OK", "WARN", "FAIL"]
    details: Optional[str] = None


class VerificationReport(BaseModel):
    doc_id: str
    status: Literal["PASS", "BLOCK"]
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    checks: list[VerificationCheck]


# ─── Matching Package ────────────────────────────────────────────────────────

class MatchCandidate(BaseModel):
    entity_type: str  # supplier, customer, account, project
    field_name: str
    extracted_value: str
    matched_id: Optional[str] = None
    matched_label: Optional[str] = None
    confidence: float
    method: str  # exact, fuzzy, similarity


class MatchingPackage(BaseModel):
    doc_id: str
    matches: list[MatchCandidate]
    unmatched: list[dict] = []


# ─── Proposed Ledger Package ─────────────────────────────────────────────────

class ProposedJournalLine(BaseModel):
    account_code: str
    label: str
    debit: float = 0.0
    credit: float = 0.0
    currency: str = "DZD"
    evidence_anchors: list[EvidenceAnchorSchema] = []
    cost_center_code: Optional[str] = None
    project_code: Optional[str] = None


class ProposedJournalEntry(BaseModel):
    entry_date: str  # ISO
    reference: Optional[str] = None
    description: str
    lines: list[ProposedJournalLine]
    assumptions: list[str] = []


class ProposedLedgerPackage(BaseModel):
    doc_id: str
    entries: list[ProposedJournalEntry]
    total_debit: float
    total_credit: float
    is_balanced: bool


# ─── Anomaly Report ──────────────────────────────────────────────────────────

class AnomalyItem(BaseModel):
    anomaly_code: str
    severity: Literal["INFO", "WARNING", "BLOCKING"]
    description: str
    details: dict = {}
    suggested_fix: Optional[str] = None


class AnomalyReport(BaseModel):
    doc_id: str
    workflow_id: Optional[str] = None
    anomalies: list[AnomalyItem]
    has_blocking: bool = False


# ─── Resolution Patch Options ────────────────────────────────────────────────

class PatchOperation(BaseModel):
    op: Literal["replace", "add", "remove"]
    path: str
    value: Optional[str | float | int | bool | dict | list] = None


class ResolutionOption(BaseModel):
    option_id: str
    description: str
    patches: list[PatchOperation]
    confidence: float
    requires_user_input: bool = False


class ResolutionPatchOptions(BaseModel):
    blocking_anomaly_codes: list[str]
    options: list[ResolutionOption]


# ─── Cost Center Snapshot ─────────────────────────────────────────────────────

class CostCenterLineItem(BaseModel):
    account_code: str
    account_label: str
    debit: float = 0.0
    credit: float = 0.0


class CostCenterSnapshot(BaseModel):
    cost_center_code: str
    cost_center_name: str
    period_label: str
    total_debit: float
    total_credit: float
    balance: float
    line_items: list[CostCenterLineItem]


# ─── HR Package ──────────────────────────────────────────────────────────────

class PayrollLineItem(BaseModel):
    label: str
    type: Literal["earning", "deduction", "employer_contribution"]
    amount: float


class HRPayrollPackage(BaseModel):
    employee_id: str
    employee_name: str
    period_label: str
    gross_salary: float
    items: list[PayrollLineItem]
    net_salary: float
    proposed_journal_entry: Optional[ProposedJournalEntry] = None


class HRPackage(BaseModel):
    tenant_id: str
    period_label: str
    payroll_proposals: list[HRPayrollPackage]


# ─── ADV Package ─────────────────────────────────────────────────────────────

class ADVPackage(BaseModel):
    tenant_id: str
    client_id: str
    contract_id: Optional[str] = None
    receivables: list[dict] = []
    payments: list[dict] = []
    proposed_journal_entries: list[ProposedJournalEntry] = []


# ─── Submission Package ──────────────────────────────────────────────────────

class SubmissionPackage(BaseModel):
    workflow_id: str
    doc_ids: list[str]
    ocr_artifact_ids: list[str] = []
    verification_report_id: Optional[str] = None
    proposed_ledger_package_id: str
    anomaly_report_id: Optional[str] = None
    evidence_anchor_ids: list[str] = []
    decisions: list[dict] = []
    is_ready: bool = False
    blocking_reasons: list[str] = []


# ─── Text Layer Detection ────────────────────────────────────────────────────

class TextLayerDetectionResult(BaseModel):
    doc_id: str
    has_text_layer: bool
    confidence: float
    reason: str


# ─── Workflow State (for orchestrator) ────────────────────────────────────────

class WorkflowState(BaseModel):
    workflow_id: str
    tenant_id: str
    actor_user_id: str
    doc_ids: list[str] = []
    status: Literal[
        "CREATED", "RUNNING", "BLOCKED", "READY_TO_COMMIT",
        "COMMITTED", "REJECTED", "FAILED"
    ] = "CREATED"
    artifacts: dict[str, list[str]] = {}  # {artifact_type: [artifact_id...]}
    blocking_reasons: list[str] = []
    errors: list[dict] = []
    warnings: list[dict] = []
    decisions: list[dict] = []
    current_node: Optional[str] = None
    node_history: list[dict] = []


# ─── Node Result (agent output) ──────────────────────────────────────────────

class NodeResult(BaseModel):
    status: Literal["OK", "BLOCK", "ERROR"]
    artifacts_created: list[str] = []
    warnings: list[dict] = []
    errors: list[dict] = []
    next: Optional[str] = None  # next node name override
