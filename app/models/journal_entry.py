"""
GFI v7.0 — JournalEntry: an accounting entry header.

Rule R-002: 100% of entries are auto-generated from source documents.
Manual entry is REJECTED unless journal_type = OD with justification.

Every entry carries:
- rf_type: mandatory RF classification (RF1/RF2/RF3/RF4)
- source_document_type + source_document_id: what generated this entry
- entry_number: sequential, cloisoned by company+journal+year

Uses GFIBase (has company_id).
"""

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class JournalEntry(GFIBase, Base):
    __tablename__ = "journal_entry"

    # ── Journal link ─────────────────────────────────────────────────────
    journal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journal.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Entry identity ───────────────────────────────────────────────────
    # Format: {journal_code}-{year}-{seq} e.g., HA-2026-0001
    entry_number = Column(String(30), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    fiscal_year = Column(String(4), nullable=False)
    label = Column(Text, nullable=False)

    # ── RF classification (mandatory) ────────────────────────────────────
    rf_type = Column(String(3), nullable=False, index=True)

    # ── Source document (R-002 enforcement) ──────────────────────────────
    # What type of document generated this entry
    source_document_type = Column(String(60), nullable=False)
    # UUID of the source document
    source_document_id = Column(UUID(as_uuid=True), nullable=True)
    # For OD entries: uploaded justification path
    od_justification_path = Column(Text, nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # DRAFT, VALIDATED, POSTED, REVERSED
    status = Column(String(20), nullable=False, server_default="'DRAFT'")

    # ── Totals (denormalized for fast queries) ───────────────────────────
    total_debit = Column(Numeric(15, 2), nullable=False, server_default="0")
    total_credit = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Project link (optional) ──────────────────────────────────────────
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    journal = relationship("Journal", back_populates="entries")
    lines = relationship(
        "JournalEntryLine", back_populates="entry", lazy="select"
    )
    project = relationship("Project")

    def __repr__(self):
        return f"<JournalEntry {self.entry_number} {self.status}>"
