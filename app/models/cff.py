"""GFI v7.0 — CFF (Charges Fiscales & Financières) models.

Tables:
  - cff_factures: CFF calculation per enterprise invoice
  - cff_imputation_associes: distribution to associates by enterprise %
"""
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Date,
    ForeignKey, Numeric, Index, func,
)
from app.database import Base


class CFFFacture(Base):
    """CFF calculation for a single invoice/period.

    CFF = TVA + IBS + TAP + CNAS + Timbre
    Distributed to associates by their % in the ENTERPRISE (never project).
    """
    __tablename__ = "cff_factures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))
    periode_mois = Column(String(7))  # YYYY-MM
    montant_ht = Column(Numeric(18, 2), nullable=False)
    cff_tva = Column(Numeric(18, 2), nullable=False, default=0)
    cff_ibs = Column(Numeric(18, 2), nullable=False, default=0)
    cff_tap = Column(Numeric(18, 2), nullable=False, default=0)
    cff_cnas = Column(Numeric(18, 2), nullable=False, default=0)
    cff_timbre = Column(Numeric(18, 2), nullable=False, default=0)
    cff_total = Column(Numeric(18, 2), nullable=False, default=0)
    reference_facture = Column(String(200))
    description = Column(Text)
    hash_sha256 = Column(String(64))
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_cff_facture_entreprise", "entreprise_id"),
    )


class CFFImputationAssocie(Base):
    """CFF distribution to an associate — based on % ENTERPRISE (never project).

    Key invariant: pourcentage_entreprise comes from entreprise_associes table.
    """
    __tablename__ = "cff_imputation_associes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    facture_id = Column(String(36), ForeignKey("cff_factures.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    pourcentage_entreprise = Column(Numeric(6, 4), nullable=False)
    montant_impute = Column(Numeric(18, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_cff_imputation_facture", "facture_id"),
        Index("ix_cff_imputation_associe", "associe_id"),
    )
