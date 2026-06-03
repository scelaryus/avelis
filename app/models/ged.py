"""
GFI v7.0 — GED (Gestion Electronique de Documents): Document, DocumentVersion,
DocumentProcessingRun. 7-layer pipeline for 400+ GB documentary heritage.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Document(GFIBase, Base):
    """Core document record with versioning and full-text search."""

    __tablename__ = "document"

    # ── Identity ─────────────────────────────────────────────────────────
    document_ref = Column(String(50), unique=True, nullable=False, index=True)
    original_filename = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # ── Dedup (Layer 3) ──────────────────────────────────────────────────
    file_hash_sha256 = Column(String(64), unique=True, nullable=False, index=True)

    # ── Classification (Layer 4) ─────────────────────────────────────────
    document_type = Column(String(30), nullable=True, index=True)
    # FACTURE_ACHAT, FACTURE_VENTE, CONTRAT, PV_REUNION, PV_RECEPTION,
    # RELEVE_BANCAIRE, SITUATION_TRAVAUX, BULLETIN_PAIE, CERTIFICAT_MEDICAL,
    # DECLARATION_FISCALE, ACTE_NOTARIE, STATUTS, PERMIS_CONSTRUIRE,
    # PLAN, PHOTO_CHANTIER, CORRESPONDANCE, AUTRE
    classification_confidence = Column(Numeric(5, 2), nullable=True)

    # ── Extraction (Layer 5) ─────────────────────────────────────────────
    extracted_metadata = Column(JSONB, nullable=True)
    # {amounts, dates, names, project_refs, entity_refs, account_numbers}
    extraction_complete = Column(Boolean, nullable=False, server_default="false")

    # ── Alias resolution (Layer 6) ───────────────────────────────────────
    aliases_resolved = Column(Boolean, nullable=False, server_default="false")
    unresolved_aliases = Column(JSONB, nullable=True)

    # ── Storage (Layer 7) ────────────────────────────────────────────────
    storage_path = Column(Text, nullable=True)
    # /{Entity}/{Project}/{Year}/{Type}/{File}

    # ── Context links ────────────────────────────────────────────────────
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    linked_entity_type = Column(String(50), nullable=True)
    linked_entity_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Pipeline status ──────────────────────────────────────────────────
    # RECEIVED, OCR_DONE, DEDUP_PASSED, CLASSIFIED, EXTRACTED,
    # ALIASES_RESOLVED, STORED, BLOCKED_DEDUP, BLOCKED_ALIAS, BLOCKED_EXTRACTION
    pipeline_status = Column(String(30), nullable=False, server_default="'RECEIVED'")
    pipeline_blocked_reason = Column(Text, nullable=True)

    # ── Source ────────────────────────────────────────────────────────────
    upload_source = Column(String(20), nullable=True)  # WEB, DRIVE, API
    uploaded_by_name = Column(String(255), nullable=True)

    # ── OCR text (Layer 2) ───────────────────────────────────────────────
    ocr_text = Column(Text, nullable=True)
    ocr_language = Column(String(10), nullable=True)  # fr, ar, mixed
    # Full-text search vector
    search_vector = Column(TSVECTOR, nullable=True)

    # ── Version tracking ─────────────────────────────────────────────────
    current_version = Column(Integer, nullable=False, server_default="1")

    project = relationship("Project")

    def __repr__(self):
        return f"<Document {self.document_ref} {self.document_type} {self.pipeline_status}>"


class DocumentVersion(GFIBase, Base):
    """Version history for documents. Modifications create new versions."""

    __tablename__ = "document_version"

    document_id = Column(
        UUID(as_uuid=True), ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    version_number = Column(Integer, nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False)
    storage_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    change_description = Column(Text, nullable=True)

    document = relationship("Document")

    def __repr__(self):
        return f"<DocumentVersion doc={self.document_id} v{self.version_number}>"


class DocumentProcessingRun(GFIBase, Base):
    """Log of each pipeline layer execution for a document."""

    __tablename__ = "document_processing_run"

    document_id = Column(
        UUID(as_uuid=True), ForeignKey("document.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    layer = Column(Integer, nullable=False)  # 1-7
    layer_name = Column(String(30), nullable=False)
    # PASS, FAIL, BLOCKED, SKIPPED
    result = Column(String(10), nullable=False)
    duration_ms = Column(Integer, nullable=True)
    detail = Column(JSONB, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=False)

    document = relationship("Document")

    def __repr__(self):
        return f"<DocumentProcessingRun L{self.layer} {self.result}>"
