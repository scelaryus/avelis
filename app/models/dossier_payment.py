"""
GFI v7.0 — DossierPayment: individual payment records on a dossier.

Each payment is classified as RF1 or RF2:
- RF1: declared, cheque/virement only, official receipt
- RF2: undeclared, cash only, internal receipt

Receipts rule RF2-S04: official receipts only for amounts above RF2.
Cash balance rule RF2-S05: RF2 cash account can never go negative.

Uses GFIBase (company_id = the selling entity).
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class DossierPayment(GFIBase, Base):
    __tablename__ = "dossier_payment"

    # ── Parent dossier ───────────────────────────────────────────────────
    dossier_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Payment identity ─────────────────────────────────────────────────
    payment_date = Column(Date, nullable=False, index=True)
    rf_type = Column(String(3), nullable=False)  # RF1 or RF2
    payment_mode = Column(String(20), nullable=False)
    # ESPECES, CHEQUE, VIREMENT, CHEQUE_NOTAIRE

    # ── Amount ───────────────────────────────────────────────────────────
    amount = Column(Numeric(15, 2), nullable=False)

    # ── Receipt tracking ─────────────────────────────────────────────────
    receipt_type = Column(String(20), nullable=True)
    # OFFICIEL (RF1), INTERNE (RF2), AUCUN
    receipt_ref = Column(String(100), nullable=True)
    receipt_amount = Column(Numeric(15, 2), nullable=True)
    # RF2-S04: receipt amount may differ from payment (surplus over RF2)

    # ── Category ─────────────────────────────────────────────────────────
    payment_category = Column(String(30), nullable=False)
    # SPOT, APPORT_20, ECHEANCE, DEBLOCAGE_TIER, RF2_SECURISATION

    # ── Credit tier (if credit disbursement) ─────────────────────────────
    credit_tier_pct = Column(Numeric(5, 2), nullable=True)
    # 20, 15, 35, 25, 5

    # ── Status ───────────────────────────────────────────────────────────
    # ENREGISTRE, VALIDE, RAPPROCHE, ANNULE
    status = Column(String(20), nullable=False, server_default="'ENREGISTRE'")

    # ── Source document ──────────────────────────────────────────────────
    justification_path = Column(Text, nullable=True)
    journal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journal_entry.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    dossier = relationship("DossierAdv", back_populates="payments")

    def __repr__(self):
        return (
            f"<DossierPayment {self.rf_type} {self.amount} DA "
            f"{self.payment_category} on {self.payment_date}>"
        )
