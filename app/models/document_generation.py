"""
GFI v7.0 — DocumentTemplate + GeneratedDocument + RelanceTracker.

14 auto-generated document types with strict RF2 visibility rules.
Daily relance automation for missing client documents.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class DocumentTemplate(Base):
    """Template definitions for auto-generated PDFs. System reference."""

    __tablename__ = "document_template"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=__import__("sqlalchemy").text("gen_random_uuid()"))
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(20), nullable=False)  # ADV, CREDIT, NOTAIRE, INTERNAL
    description = Column(Text, nullable=True)

    # ── Visibility ───────────────────────────────────────────────────────
    client_visible = Column(Boolean, nullable=False, server_default="true")
    rf2_content = Column(Boolean, nullable=False, server_default="false")
    # If rf2_content=true, document contains RF2 data -> restricted

    # ── Template file path ───────────────────────────────────────────────
    template_path = Column(Text, nullable=True)

    # ── Required fields (JSON schema) ────────────────────────────────────
    required_fields = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=__import__("sqlalchemy").func.now())
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self):
        return f"<DocumentTemplate {self.code}>"


class GeneratedDocument(GFIBase, Base):
    """An instance of a generated document linked to a dossier."""

    __tablename__ = "generated_document"

    # ── Template ─────────────────────────────────────────────────────────
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_template.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    template_code = Column(String(30), nullable=False, index=True)

    # ── Links ────────────────────────────────────────────────────────────
    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # ── Document data ────────────────────────────────────────────────────
    document_ref = Column(String(100), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    file_path = Column(Text, nullable=True)
    file_format = Column(String(10), nullable=False, server_default="'PDF'")

    # ── Content data (JSON of injected fields) ───────────────────────────
    content_data = Column(JSONB, nullable=True)

    # ── Visibility flags ─────────────────────────────────────────────────
    client_visible = Column(Boolean, nullable=False, server_default="true")
    rf2_content = Column(Boolean, nullable=False, server_default="false")

    # ── Status ───────────────────────────────────────────────────────────
    # GENERE, ENVOYE, SIGNE, ARCHIVE
    status = Column(String(20), nullable=False, server_default="'GENERE'")

    # ── Sent tracking ────────────────────────────────────────────────────
    sent_to_client = Column(Boolean, nullable=False, server_default="false")
    sent_to_bank = Column(Boolean, nullable=False, server_default="false")
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    template = relationship("DocumentTemplate")
    dossier = relationship("DossierAdv")

    def __repr__(self):
        return f"<GeneratedDocument {self.template_code} {self.status}>"


class RelanceTracker(GFIBase, Base):
    """Tracks relance (follow-up) status for each required document per dossier."""

    __tablename__ = "relance_tracker"

    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Document being tracked ───────────────────────────────────────────
    document_type = Column(String(60), nullable=False)
    document_name = Column(String(255), nullable=False)
    source = Column(String(20), nullable=False)  # CLIENT, BANK, EXPERT, NOTARY

    # ── Required since ───────────────────────────────────────────────────
    required_since = Column(Date, nullable=False)

    # ── Status ───────────────────────────────────────────────────────────
    # REQUIS, RELANCE_J3, RELANCE_J7, RELANCE_J14, BLOQUANT, RECU, VERIFIE
    status = Column(String(20), nullable=False, server_default="'REQUIS'")

    # ── Received ─────────────────────────────────────────────────────────
    received_date = Column(Date, nullable=True)
    file_path = Column(Text, nullable=True)

    # ── Relance history ──────────────────────────────────────────────────
    relance_j3_at = Column(DateTime(timezone=True), nullable=True)
    relance_j7_at = Column(DateTime(timezone=True), nullable=True)
    relance_j14_at = Column(DateTime(timezone=True), nullable=True)
    relance_j30_at = Column(DateTime(timezone=True), nullable=True)
    relance_count = Column(Integer, nullable=False, server_default="0")

    # ── Blocking ─────────────────────────────────────────────────────────
    blocks_operation = Column(String(40), nullable=True)
    # e.g., "VSP", "PALIER_15PCT", "ENGAGEMENT"

    dossier = relationship("DossierAdv")

    def __repr__(self):
        return f"<RelanceTracker {self.document_type} {self.status}>"
