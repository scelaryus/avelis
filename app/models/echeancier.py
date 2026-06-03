"""
GFI v7.0 — Echeancier + Echeance: installment schedule for fonds propres.

An Echeancier is the full payment schedule for a dossier's remaining RF1
balance after the 30% initial payment. Each Echeance is one installment.

Rules:
  FP-001: 30% of prix_reel paid before engagement
  FP-003: Installments are RF1, cheque ONLY
  FP-004: Daily penalty calculation starting J+1 late
  FP-005: DEFAUT_PAIEMENT after 60 days blocks everything

Uses GFIBase (company_id = the selling entity).
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Echeancier(GFIBase, Base):
    """The full installment schedule for a fonds propres dossier."""

    __tablename__ = "echeancier"

    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Schedule parameters ──────────────────────────────────────────────
    solde_rf1 = Column(Numeric(15, 2), nullable=False)
    date_engagement = Column(Date, nullable=False)
    date_livraison_prevue = Column(Date, nullable=False)
    duree_mois = Column(Integer, nullable=False)
    # MENSUEL or BIMENSUEL
    frequence = Column(String(20), nullable=False, server_default="'MENSUEL'")
    nb_echeances = Column(Integer, nullable=False)
    montant_echeance = Column(Numeric(15, 2), nullable=False)
    montant_derniere = Column(Numeric(15, 2), nullable=False)

    # ── Penalty rate (annual, parameterizable per project) ───────────────
    taux_penalite_annuel = Column(
        Numeric(5, 2), nullable=False, server_default="5.00"
    )

    # ── Status ───────────────────────────────────────────────────────────
    # ACTIF, TERMINE, DEFAUT
    status = Column(String(20), nullable=False, server_default="'ACTIF'")

    # ── Totals (denormalized) ────────────────────────────────────────────
    total_paye = Column(Numeric(15, 2), nullable=False, server_default="0")
    total_penalites = Column(Numeric(15, 2), nullable=False, server_default="0")
    nb_retards = Column(Integer, nullable=False, server_default="0")

    # ── Relationships ────────────────────────────────────────────────────
    dossier = relationship("DossierAdv")
    echeances = relationship(
        "Echeance", back_populates="echeancier", lazy="select"
    )

    def __repr__(self):
        return (
            f"<Echeancier {self.nb_echeances}x {self.montant_echeance} DA "
            f"{self.frequence} {self.status}>"
        )


class Echeance(GFIBase, Base):
    """A single installment within an echeancier."""

    __tablename__ = "echeance"

    echeancier_id = Column(
        UUID(as_uuid=True),
        ForeignKey("echeancier.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Installment identity ─────────────────────────────────────────────
    numero = Column(Integer, nullable=False)
    date_echeance = Column(Date, nullable=False, index=True)
    montant = Column(Numeric(15, 2), nullable=False)

    # ── Status ───────────────────────────────────────────────────────────
    # A_VENIR, DUE, PAYEE, EN_RETARD, DEFAUT
    status = Column(String(20), nullable=False, server_default="'A_VENIR'")

    # ── Payment ──────────────────────────────────────────────────────────
    date_paiement = Column(Date, nullable=True)
    montant_paye = Column(Numeric(15, 2), nullable=True)
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Penalty (FP-004) ─────────────────────────────────────────────────
    jours_retard = Column(Integer, nullable=False, server_default="0")
    penalite_montant = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Relance tracking ─────────────────────────────────────────────────
    relance_j7_sent = Column(String(1), nullable=False, server_default="'N'")
    relance_j3_sent = Column(String(1), nullable=False, server_default="'N'")
    relance_j1_sent = Column(String(1), nullable=False, server_default="'N'")
    relance_j7r_sent = Column(String(1), nullable=False, server_default="'N'")
    relance_j15r_sent = Column(String(1), nullable=False, server_default="'N'")
    relance_j30r_sent = Column(String(1), nullable=False, server_default="'N'")
    mise_en_demeure_sent = Column(String(1), nullable=False, server_default="'N'")

    # ── Relationships ────────────────────────────────────────────────────
    echeancier = relationship("Echeancier", back_populates="echeances")

    def __repr__(self):
        return (
            f"<Echeance #{self.numero} {self.montant} DA "
            f"due={self.date_echeance} {self.status}>"
        )
