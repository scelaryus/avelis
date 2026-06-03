"""
GFI v7.0 — FiscalDeclaration: auto-prepared tax declarations.

Supports:
  G50 (monthly): TVA decaisser, TAP, IBS installment
  CNAS (quarterly): employer + employee contributions
  CACOBATPH (annual): construction sector contributions (BTPH only)
  BILAN (annual): balance sheet + income statement + annexes

Each declaration is per-entity (company_id via GFIBase).
If a required tax rate is missing -> FC-005 blocks preparation.
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


class FiscalDeclaration(GFIBase, Base):
    __tablename__ = "fiscal_declaration"

    # ── Declaration identity ─────────────────────────────────────────────
    declaration_type = Column(String(20), nullable=False, index=True)
    # G50, CNAS, CACOBATPH, BILAN
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    fiscal_year = Column(String(4), nullable=False)

    # ── Status ───────────────────────────────────────────────────────────
    # DRAFT, PREPARED, VALIDATED, SUBMITTED, REJECTED
    status = Column(String(20), nullable=False, server_default="'DRAFT'")

    # ── Computed amounts (JSONB for flexibility across types) ────────────
    computed_data = Column(JSONB, nullable=False, server_default="'{}'")

    # ── G50 specific fields ──────────────────────────────────────────────
    tva_collected = Column(Numeric(15, 2), nullable=True)
    tva_deductible = Column(Numeric(15, 2), nullable=True)
    tva_a_decaisser = Column(Numeric(15, 2), nullable=True)
    tap_amount = Column(Numeric(15, 2), nullable=True)
    ibs_installment = Column(Numeric(15, 2), nullable=True)

    # ── CNAS specific fields ─────────────────────────────────────────────
    cnas_employee_total = Column(Numeric(15, 2), nullable=True)
    cnas_employer_total = Column(Numeric(15, 2), nullable=True)

    # ── Validation ───────────────────────────────────────────────────────
    validated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    validated_at = Column(
        __import__("sqlalchemy").DateTime(timezone=True), nullable=True
    )
    submission_ref = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<FiscalDeclaration {self.declaration_type} "
            f"{self.period_start}-{self.period_end} {self.status}>"
        )
