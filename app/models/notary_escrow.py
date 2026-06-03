"""
GFI v7.0 — NotaryEscrow + EscrowMovement + EtatDetaille + EtatDetailleLine.

In Algerian real estate credit purchases, bank funds ALWAYS transit through
the project notary's escrow account — never directly to the developer.

Key invariants:
  FIN-005: solde_transitoire can NEVER be negative
  NOTAIRE-001: SUM(etat_detaille lines) MUST = montant_global (exact)
  CRE-004: 20% must transit via escrow (no direct bank->company)
  CRE-006: 5% release requires PV remise des cles
  48h alert: positive balance above expected 5% reserves for >48h

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


class NotaryEscrow(GFIBase, Base):
    """One escrow account per notary per project per entity."""

    __tablename__ = "notary_escrow"

    notaire_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Balance ──────────────────────────────────────────────────────────
    solde_transitoire = Column(
        Numeric(15, 2), nullable=False, server_default="0"
    )

    # ── Expected 5% reserves (sum of all active credit dossiers' 5%) ─────
    expected_5pct_reserve = Column(
        Numeric(15, 2), nullable=False, server_default="0"
    )

    # ── 48h alert tracking ───────────────────────────────────────────────
    last_zero_at = Column(DateTime(timezone=True), nullable=True)
    alert_48h_active = Column(String(1), nullable=False, server_default="'N'")

    # ── Notary info ──────────────────────────────────────────────────────
    notaire_name = Column(String(255), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    project = relationship("Project")
    movements = relationship(
        "EscrowMovement", back_populates="escrow", lazy="select"
    )

    def __repr__(self):
        return (
            f"<NotaryEscrow notaire={self.notaire_id} "
            f"project={self.project_id} solde={self.solde_transitoire}>"
        )


class EscrowMovement(GFIBase, Base):
    """Individual credit/debit on the escrow account."""

    __tablename__ = "escrow_movement"

    escrow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notary_escrow.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Movement details ─────────────────────────────────────────────────
    movement_date = Column(DateTime(timezone=True), nullable=False, index=True)
    movement_type = Column(String(10), nullable=False)  # CREDIT or DEBIT
    montant = Column(Numeric(15, 2), nullable=False)
    balance_after = Column(Numeric(15, 2), nullable=False)

    source = Column(String(255), nullable=True)
    destination = Column(String(255), nullable=True)

    # ── Linked dossier ───────────────────────────────────────────────────
    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    # ── Coded reason ─────────────────────────────────────────────────────
    # VSP_20PCT, PALIER_5PCT, LIBERATION_20PCT, LIBERATION_5PCT,
    # PALIER_15PCT, PALIER_35PCT, PALIER_25PCT, AUTRE
    motif = Column(String(30), nullable=False)

    # ── Cheque reference ─────────────────────────────────────────────────
    reference_cheque = Column(String(100), nullable=True)

    # ── Link to etat detaille line (if from a global cheque) ─────────────
    etat_detaille_id = Column(
        UUID(as_uuid=True),
        ForeignKey("etat_detaille.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    escrow = relationship("NotaryEscrow", back_populates="movements")
    dossier = relationship("DossierAdv")

    def __repr__(self):
        return (
            f"<EscrowMovement {self.movement_type} {self.montant} DA "
            f"{self.motif} on {self.movement_date}>"
        )


class EtatDetaille(GFIBase, Base):
    """Global notary cheque decomposition into per-dossier allocations."""

    __tablename__ = "etat_detaille"

    escrow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notary_escrow.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Global cheque ────────────────────────────────────────────────────
    cheque_global_reference = Column(String(100), nullable=False)
    montant_global = Column(Numeric(15, 2), nullable=False)
    date_cheque = Column(Date, nullable=False)
    notaire_id = Column(UUID(as_uuid=True), nullable=False)

    # ── Status ───────────────────────────────────────────────────────────
    # PENDING, VALIDATED, REJECTED
    status = Column(String(20), nullable=False, server_default="'PENDING'")

    # ── Sum of lines (denormalized for fast validation) ──────────────────
    sum_lignes = Column(Numeric(15, 2), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    escrow = relationship("NotaryEscrow")
    lines = relationship(
        "EtatDetailleLine", back_populates="etat_detaille", lazy="select"
    )

    def __repr__(self):
        return (
            f"<EtatDetaille {self.cheque_global_reference} "
            f"{self.montant_global} DA {self.status}>"
        )


class EtatDetailleLine(GFIBase, Base):
    """One line per dossier in an etat detaille."""

    __tablename__ = "etat_detaille_line"

    etat_detaille_id = Column(
        UUID(as_uuid=True),
        ForeignKey("etat_detaille.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False,
    )
    client_nom = Column(String(255), nullable=False)
    lot_reference = Column(String(50), nullable=False)
    montant_impute = Column(Numeric(15, 2), nullable=False)
    motif = Column(String(60), nullable=False)

    # ── Relationships ────────────────────────────────────────────────────
    etat_detaille = relationship("EtatDetaille", back_populates="lines")
    dossier = relationship("DossierAdv")

    def __repr__(self):
        return (
            f"<EtatDetailleLine {self.lot_reference} "
            f"{self.montant_impute} DA {self.motif}>"
        )
