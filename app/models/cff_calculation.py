"""
GFI v7.0 — CffCalculation: stores the decomposed CFF result.

Each CFF calculation stores all 5 components separately:
  TVA, TAP, IBS, stamp duty, and total.
Plus metadata: which company emitted, which received, the RF3 invoice ref.

Uses GFIBase (company_id = the EMITTING company, NOT the receiver).
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


class CffCalculation(GFIBase, Base):
    __tablename__ = "cff_calculation"

    # ── Source RF3 transaction ────────────────────────────────────────────
    financial_transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Emitter and receiver ─────────────────────────────────────────────
    # company_id (from GFIBase) = the EMITTING company
    receiver_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Destination project (for CC imputation) ──────────────────────────
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # ── Invoice data ─────────────────────────────────────────────────────
    invoice_date = Column(Date, nullable=False)
    invoice_ref = Column(String(100), nullable=True)
    montant_ht = Column(Numeric(15, 2), nullable=False)

    # ── 5-step decomposition (R-027) ─────────────────────────────────────
    # Step 1: TVA
    tva_rate = Column(Numeric(5, 2), nullable=False)  # 19%
    tva_amount = Column(Numeric(15, 2), nullable=False)

    # Step 2: TAP
    tap_rate = Column(Numeric(5, 2), nullable=False)  # 1% or 2%
    tap_amount = Column(Numeric(15, 2), nullable=False)

    # Step 3+4: IBS
    ibs_base = Column(Numeric(15, 2), nullable=False)  # HT - TAP
    ibs_rate = Column(Numeric(5, 2), nullable=False)    # 19% or 26%
    ibs_amount = Column(Numeric(15, 2), nullable=False)

    # Step 5: Stamp duty
    ttc_amount = Column(Numeric(15, 2), nullable=False)  # HT + TVA
    stamp_duty_amount = Column(Numeric(15, 2), nullable=False)
    stamp_duty_exempt = Column(String(1), nullable=False, server_default="'N'")

    # ── CFF total ────────────────────────────────────────────────────────
    cff_total = Column(Numeric(15, 2), nullable=False)

    # ── Verification flags ───────────────────────────────────────────────
    # V6: confirms percentages came from entreprise_associe (emitter)
    v6_source_verified = Column(String(1), nullable=False, server_default="'N'")
    # V7: confirms Yamina = 0 for protected companies
    v7_yamina_verified = Column(String(1), nullable=False, server_default="'N'")

    # ── Status ───────────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, server_default="'CALCULATED'")
    # CALCULATED, VERIFIED, IMPUTED, BLOCKED

    # ── Relationships ────────────────────────────────────────────────────
    transaction = relationship("FinancialTransaction")
    receiver = relationship(
        "Company",
        foreign_keys="[CffCalculation.receiver_company_id]",
    )
    project = relationship("Project")
    imputations = relationship(
        "CffImputation", back_populates="cff_calculation", lazy="select"
    )

    def __repr__(self):
        return (
            f"<CffCalculation {self.cff_total} DA "
            f"emitter={self.company_id} invoice={self.invoice_ref}>"
        )
