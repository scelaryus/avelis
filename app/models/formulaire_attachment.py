"""
GFI v7.0 — FormulaireAttachment: file uploads attached to formulaires.

Supports PDF, DOCX, JPG, PNG, IFC, DWG, DXF uploads with size limits.
Each attachment can be verified by the AI document agent.
"""

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class FormulaireAttachment(GFIBase, Base):
    __tablename__ = "formulaire_attachment"

    formulaire_id = Column(
        UUID(as_uuid=True),
        ForeignKey("formulaire.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── File metadata ────────────────────────────────────────────────────
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    storage_path = Column(Text, nullable=False)

    # ── Field this attachment corresponds to ─────────────────────────────
    field_code = Column(String(60), nullable=True)

    # ── AI verification result for this specific document ────────────────
    ai_verification_status = Column(String(20), nullable=True)
    ai_verification_result = Column(JSONB, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    formulaire = relationship("Formulaire")

    def __repr__(self):
        return f"<FormulaireAttachment {self.filename} for {self.formulaire_id}>"
