"""
GFI v7.0 — DossierDocument: required document tracking per dossier.

Each dossier has a checklist of required documents. This table tracks
each document's status: REQUIS, RECU, VERIFIE, REJETE, RELANCE.
"""

from sqlalchemy import Column, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class DossierDocument(GFIBase, Base):
    __tablename__ = "dossier_document"

    dossier_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    document_type = Column(String(60), nullable=False)
    document_name = Column(String(255), nullable=False)

    # REQUIS, RECU, VERIFIE, REJETE, RELANCE
    status = Column(String(20), nullable=False, server_default="'REQUIS'")

    received_date = Column(Date, nullable=True)
    file_path = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    last_relance_date = Column(Date, nullable=True)
    relance_count = Column(
        __import__("sqlalchemy").Integer, nullable=False,
        server_default="0"
    )

    dossier = relationship("DossierAdv")

    def __repr__(self):
        return f"<DossierDocument {self.document_type} {self.status}>"
