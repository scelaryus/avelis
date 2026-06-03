"""
GFI v7.0 — JournalSequence: per-entity, per-journal, per-year numbering.

Numbering is STRICTLY cloisoned: HA-2026-0001 in ETS-DK is independent
of HA-2026-0001 in SARL-DP.

Uses GFIBase (has company_id).
"""

from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, GFIBase


class JournalSequence(GFIBase, Base):
    __tablename__ = "journal_sequence"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "journal_code", "fiscal_year",
            name="uq_journal_seq_company_journal_year",
        ),
    )

    journal_code = Column(String(10), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    last_number = Column(Integer, nullable=False, server_default="0")

    def __repr__(self):
        return (
            f"<JournalSequence {self.journal_code}-{self.fiscal_year} "
            f"last={self.last_number} @ company={self.company_id}>"
        )
