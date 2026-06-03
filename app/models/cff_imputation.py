"""
GFI v7.0 — CffImputation: per-associate CFF distribution.

Each CFF calculation is distributed to the associates of the EMITTING
company, using their percentages in THAT company (entreprise_associe).

Triple imputation: each row records the amount imputed to one associate,
derived from:
  1. The emitting company's ownership (entreprise_associe)
  2. Booked on the destination project's cost center (CC6)
  3. Reduces the associate's net quote-part

Uses GFIBase (company_id = the EMITTING company).
"""

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class CffImputation(GFIBase, Base):
    __tablename__ = "cff_imputation"

    # ── Parent CFF calculation ───────────────────────────────────────────
    cff_calculation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cff_calculation.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Associate receiving the imputation ───────────────────────────────
    associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Ownership percentage used (snapshot from entreprise_associe) ─────
    percentage_used = Column(Numeric(7, 4), nullable=False)

    # ── Imputed amount ───────────────────────────────────────────────────
    amount = Column(Numeric(15, 2), nullable=False)

    # ── Source verification (V6) ─────────────────────────────────────────
    # Which table was used: must always be 'entreprise_associe'
    percentage_source = Column(
        String(30), nullable=False, server_default="'entreprise_associe'"
    )

    # ── Relationships ────────────────────────────────────────────────────
    cff_calculation = relationship(
        "CffCalculation", back_populates="imputations"
    )
    associate = relationship("Associate")

    def __repr__(self):
        return (
            f"<CffImputation {self.amount} DA "
            f"({self.percentage_used}%) to {self.associate_id}>"
        )
