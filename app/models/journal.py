"""
GFI v7.0 — Journal: per-entity accounting journals.

Each of the 12 entities has its OWN set of journals:
  HA (Achats), VT (Ventes), BQ (Banque), CA (Caisse), OD (Operations Diverses)

Journal isolation is enforced by company_id — the same journal code
(e.g., HA) can exist in multiple companies without collision.

Uses GFIBase (has company_id).
"""

from sqlalchemy import Column, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Journal(GFIBase, Base):
    __tablename__ = "journal"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "code",
            name="uq_journal_company_code",
        ),
    )

    code = Column(String(10), nullable=False, index=True)
    # HA, VT, BQ, CA, OD
    name = Column(String(100), nullable=False)
    journal_type = Column(String(20), nullable=False)
    # ACHAT, VENTE, BANQUE, CAISSE, OD
    description = Column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    entries = relationship("JournalEntry", back_populates="journal", lazy="select")

    def __repr__(self):
        return f"<Journal {self.code} @ company={self.company_id}>"
