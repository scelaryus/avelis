"""
GFI v7.0 — BankReconciliation: bank statement import and matching.

Imports bank statements (CFONB/CSV), proposes automatic matching
using NLP analysis. Auto-accepts at confidence >= 95%.
Below 95% -> requires manual validation by Tresorier.

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


class BankStatement(GFIBase, Base):
    __tablename__ = "bank_statement"

    # ── Statement identity ───────────────────────────────────────────────
    bank_name = Column(String(100), nullable=False)
    account_number = Column(String(50), nullable=False)
    statement_date = Column(Date, nullable=False, index=True)
    import_format = Column(String(10), nullable=False)  # CFONB, CSV
    import_file_path = Column(Text, nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, server_default="'IMPORTED'")
    # IMPORTED, RECONCILING, RECONCILED, CLOSED

    total_debit = Column(Numeric(15, 2), nullable=False, server_default="0")
    total_credit = Column(Numeric(15, 2), nullable=False, server_default="0")
    line_count = Column(Numeric(5, 0), nullable=False, server_default="0")

    # ── Relationships ────────────────────────────────────────────────────
    movements = relationship(
        "BankMovement", back_populates="statement", lazy="select"
    )

    def __repr__(self):
        return f"<BankStatement {self.bank_name} {self.statement_date}>"


class BankMovement(GFIBase, Base):
    __tablename__ = "bank_movement"

    # ── Parent statement ─────────────────────────────────────────────────
    statement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bank_statement.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Movement data ────────────────────────────────────────────────────
    movement_date = Column(Date, nullable=False, index=True)
    value_date = Column(Date, nullable=True)
    label = Column(Text, nullable=False)
    reference = Column(String(100), nullable=True)
    amount = Column(Numeric(15, 2), nullable=False)
    direction = Column(String(1), nullable=False)  # D=debit, C=credit

    # ── Reconciliation ───────────────────────────────────────────────────
    reconciled = Column(String(1), nullable=False, server_default="'N'")
    matched_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journal_entry.id", ondelete="SET NULL"),
        nullable=True,
    )
    match_confidence = Column(Numeric(5, 2), nullable=True)
    match_method = Column(String(20), nullable=True)  # AUTO, MANUAL, NLP
    reconciled_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    reconciled_at = Column(
        __import__("sqlalchemy").DateTime(timezone=True), nullable=True
    )

    # ── NLP matching candidates (JSON array) ─────────────────────────────
    match_candidates = Column(JSONB, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    statement = relationship("BankStatement", back_populates="movements")
    matched_entry = relationship("JournalEntry")

    def __repr__(self):
        return (
            f"<BankMovement {self.movement_date} "
            f"{self.direction}{self.amount} '{self.label[:30]}'>"
        )
