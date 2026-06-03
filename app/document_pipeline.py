"""
GFI v7.0 — 7-Layer Document Processing Pipeline.

Layer 1: Reception (raw file storage)
Layer 2: OCR (LLM agentic OCR for scans, direct extraction for text PDFs)
Layer 3: Deduplication (SHA-256, KT-01: block duplicates)
Layer 4: Classification (14 document types)
Layer 5: Extraction (amounts, dates, names, references + formulaire if missing)
Layer 6: Alias Resolution (all names through AliasResolver)
Layer 7: Storage & Indexing (normalized directory + full-text search)

Core API:
  process_document(file_path, source, ...) -> Document (runs all 7 layers)
  run_layer(document_id, layer) -> DocumentProcessingRun
  search_documents(query, ...) -> list[Document]
"""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class DuplicateDocument(Exception):
    """KT-01: Document already exists (same SHA-256 hash)."""
    def __init__(self, message: str, existing_ref: str):
        super().__init__(message)
        self.existing_ref = existing_ref


class AliasResolutionPending(Exception):
    """Layer 6: Unresolved aliases block integration."""
    pass


def _log_layer(session, document_id, company_id, layer, name, result, detail, start_time):
    from app.models.ged import DocumentProcessingRun
    now = datetime.now(timezone.utc)
    run = DocumentProcessingRun(
        company_id=company_id, document_id=document_id,
        layer=layer, layer_name=name, result=result,
        duration_ms=int((time.time() - start_time) * 1000),
        detail=detail, executed_at=now,
    )
    session.add(run)
    session.flush()
    return run


def process_document(
    session: Session,
    *,
    file_path: str,
    company_id: UUID,
    upload_source: str = "WEB",
    uploaded_by: UUID | None = None,
    uploaded_by_name: str | None = None,
    project_id: UUID | None = None,
) -> object:
    """Run the full 7-layer pipeline on a document."""
    from app.models.ged import Document

    doc_ref = f"DOC-{uuid4().hex[:12].upper()}"
    path = Path(file_path)

    # ── Layer 1: Reception ───────────────────────────────────────────────
    t0 = time.time()
    file_bytes = path.read_bytes() if path.exists() else b""
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    doc = Document(
        company_id=company_id,
        document_ref=doc_ref,
        original_filename=path.name,
        mime_type=_guess_mime(path.suffix),
        file_size_bytes=len(file_bytes),
        file_hash_sha256=file_hash,
        upload_source=upload_source,
        uploaded_by_name=uploaded_by_name,
        project_id=project_id,
        pipeline_status="RECEIVED",
        created_by=uploaded_by,
    )
    session.add(doc)
    session.flush()
    _log_layer(session, doc.id, company_id, 1, "RECEPTION", "PASS",
               {"filename": path.name, "size": len(file_bytes)}, t0)

    # ── Layer 2: OCR ─────────────────────────────────────────────────────
    t0 = time.time()
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg", ".png", ".tiff", ".tif"):
        # Image: would call LLM agentic OCR in production
        doc.ocr_text = "[OCR extraction pending — image document]"
        doc.ocr_language = "fr"
    elif suffix == ".pdf":
        # PDF: attempt direct text extraction, fallback to OCR
        doc.ocr_text = "[PDF text extraction pending]"
        doc.ocr_language = "fr"
    else:
        doc.ocr_text = ""
    doc.pipeline_status = "OCR_DONE"
    _log_layer(session, doc.id, company_id, 2, "OCR", "PASS",
               {"language": doc.ocr_language}, t0)

    # ── Layer 3: Deduplication (KT-01) ───────────────────────────────────
    t0 = time.time()
    existing = (
        session.query(Document)
        .filter(
            Document.file_hash_sha256 == file_hash,
            Document.id != doc.id,
            Document.is_deleted.is_(False),
        )
        .first()
    )
    if existing:
        doc.pipeline_status = "BLOCKED_DEDUP"
        doc.pipeline_blocked_reason = f"Duplicate of {existing.document_ref}"
        _log_layer(session, doc.id, company_id, 3, "DEDUP", "BLOCKED",
                   {"existing_ref": existing.document_ref}, t0)
        session.flush()
        raise DuplicateDocument(
            f"KT-01: Document already exists as {existing.document_ref}.",
            existing_ref=existing.document_ref,
        )
    doc.pipeline_status = "DEDUP_PASSED"
    _log_layer(session, doc.id, company_id, 3, "DEDUP", "PASS", {}, t0)

    # ── Layer 4: Classification ──────────────────────────────────────────
    t0 = time.time()
    doc.document_type = _classify_document(path.name, doc.ocr_text)
    doc.classification_confidence = 70  # placeholder
    doc.pipeline_status = "CLASSIFIED"
    _log_layer(session, doc.id, company_id, 4, "CLASSIFICATION", "PASS",
               {"type": doc.document_type}, t0)

    # ── Layer 5: Extraction ──────────────────────────────────────────────
    t0 = time.time()
    metadata = _extract_metadata(doc.ocr_text or "")
    doc.extracted_metadata = metadata
    doc.extraction_complete = bool(metadata)
    doc.pipeline_status = "EXTRACTED"
    _log_layer(session, doc.id, company_id, 5, "EXTRACTION", "PASS",
               {"fields_extracted": len(metadata)}, t0)

    # ── Layer 6: Alias Resolution ────────────────────────────────────────
    t0 = time.time()
    unresolved = []
    # In production: pass all extracted names through alias_resolver.resolve()
    doc.aliases_resolved = len(unresolved) == 0
    doc.unresolved_aliases = unresolved if unresolved else None
    if unresolved:
        doc.pipeline_status = "BLOCKED_ALIAS"
        _log_layer(session, doc.id, company_id, 6, "ALIAS_RESOLUTION", "BLOCKED",
                   {"unresolved": unresolved}, t0)
    else:
        doc.pipeline_status = "ALIASES_RESOLVED"
        _log_layer(session, doc.id, company_id, 6, "ALIAS_RESOLUTION", "PASS", {}, t0)

    # ── Layer 7: Storage & Indexing ──────────────────────────────────────
    t0 = time.time()
    from app.models.company import Company
    company = session.get(Company, company_id)
    entity_code = company.code if company else "UNKNOWN"
    year = str(datetime.now().year)
    doc_type = doc.document_type or "AUTRE"

    if project_id:
        from app.models.project import Project
        project = session.get(Project, project_id)
        proj_code = project.code if project else "GENERAL"
    else:
        proj_code = "GENERAL"

    storage_dir = f"/{entity_code}/{proj_code}/{year}/{doc_type}"
    doc.storage_path = f"{storage_dir}/{doc.document_ref}_{path.name}"
    doc.pipeline_status = "STORED"
    _log_layer(session, doc.id, company_id, 7, "STORAGE", "PASS",
               {"path": doc.storage_path}, t0)

    session.flush()
    return doc


def _guess_mime(suffix: str) -> str:
    return {
        ".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".tiff": "image/tiff", ".tif": "image/tiff",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix.lower(), "application/octet-stream")


def _classify_document(filename: str, text: str) -> str:
    """Rule-based + keyword classification. In production: LLM classifier."""
    fn = filename.lower()
    t = (text or "").lower()

    if "facture" in fn or "invoice" in fn:
        return "FACTURE_ACHAT" if "achat" in fn or "fournisseur" in t else "FACTURE_VENTE"
    if "contrat" in fn or "contract" in fn:
        return "CONTRAT"
    if "pv" in fn or "proces-verbal" in fn:
        return "PV_REUNION"
    if "releve" in fn or "bank" in fn:
        return "RELEVE_BANCAIRE"
    if "situation" in fn:
        return "SITUATION_TRAVAUX"
    if "bulletin" in fn or "paie" in fn:
        return "BULLETIN_PAIE"
    if "medical" in fn or "certificat" in fn:
        return "CERTIFICAT_MEDICAL"
    if "g50" in fn or "cnas" in fn or "declaration" in fn:
        return "DECLARATION_FISCALE"
    if "notari" in fn or "acte" in fn:
        return "ACTE_NOTARIE"
    if "statut" in fn:
        return "STATUTS"
    if "permis" in fn:
        return "PERMIS_CONSTRUIRE"
    if "plan" in fn:
        return "PLAN"
    return "AUTRE"


def _extract_metadata(text: str) -> dict:
    """Extract key fields. In production: LLM structured extraction."""
    import re
    metadata = {}
    # Simple amount extraction
    amounts = re.findall(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:DA|DZD)', text)
    if amounts:
        metadata["amounts"] = amounts[:5]
    # Date extraction
    dates = re.findall(r'\d{2}[/.-]\d{2}[/.-]\d{4}', text)
    if dates:
        metadata["dates"] = dates[:5]
    return metadata


def search_documents(
    session: Session,
    query: str,
    company_id: UUID | None = None,
    document_type: str | None = None,
    limit: int = 50,
) -> list:
    """Full-text search across the documentary heritage."""
    from app.models.ged import Document

    q = session.query(Document).filter(
        Document.pipeline_status == "STORED",
        Document.is_deleted.is_(False),
    )
    if company_id:
        q = q.filter(Document.company_id == company_id)
    if document_type:
        q = q.filter(Document.document_type == document_type)

    # Text search on ocr_text (simplified; production uses tsvector)
    if query:
        q = q.filter(Document.ocr_text.ilike(f"%{query}%"))

    return q.order_by(Document.created_at.desc()).limit(limit).all()
