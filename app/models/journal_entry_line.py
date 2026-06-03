"""
GFI v7.0 — JournalEntryLine: individual debit/credit lines within an entry.

Each line debits OR credits exactly one SCF account.
The sum of debits MUST equal the sum of credits within an entry
(enforced by DB trigger).

Uses GFIBase (has company_id).
"""

from sqlalchemy import Column, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class JournalEntryLine(GFIBase, Base):
    __tablename__ = "journal_entry_line"

    # ── Parent entry ─────────────────────────────────────────────────────
    entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journal_entry.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Account ──────────────────────────────────────────────────────────
    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("account.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_code = Column(String(20), nullable=False)  # denormalized

    # ── Amount (exactly one of debit/credit is non-zero) ─────────────────
    debit = Column(Numeric(15, 2), nullable=False, server_default="0")
    credit = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Label (line-level detail) ────────────────────────────────────────
    label = Column(Text, nullable=True)

    # ── Third-party reference ────────────────────────────────────────────
    tiers_type = Column(String(20), nullable=True)  # CLIENT, FOURNISSEUR, ASSOCIE
    tiers_id = Column(UUID(as_uuid=True), nullable=True)
    tiers_name = Column(String(255), nullable=True)

    # ── Line number within entry ─────────────────────────────────────────
    line_number = Column(Numeric(3, 0), nullable=False)

    # ── Relationships ────────────────────────────────────────────────────
    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account")

    def __repr__(self):
        d = f"D{self.debit}" if self.debit else ""
        c = f"C{self.credit}" if self.credit else ""
        return f"<JournalEntryLine {self.account_code} {d}{c}>"
