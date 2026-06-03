"""
GFI v7.0 — DossierAdv: the central ADV sales dossier.

Tracks every real estate sale from first contact to final delivery.
16-state machine with 19 transitions and strict preconditions.

Every field from CDC-ADV section 1.3 is modelled here.

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class DossierAdv(GFIBase, Base):
    __tablename__ = "dossier_adv"

    # ── Dossier identity ─────────────────────────────────────────────────
    # Format: ADV-{YEAR}-{PROJECT_CODE}-{SEQ:04d}
    numero_dossier = Column(String(40), unique=True, nullable=False, index=True)

    # ── Links ────────────────────────────────────────────────────────────
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    lot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lot.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    devis_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Payment type ─────────────────────────────────────────────────────
    # SPOT, CREDIT_BANCAIRE, FONDS_PROPRES, MIXTE
    type_paiement = Column(String(20), nullable=False)

    # ── Pricing (RF classification) ──────────────────────────────────────
    prix_vente_rf1 = Column(Numeric(15, 2), nullable=False)
    prix_vente_rf2 = Column(Numeric(15, 2), nullable=True)
    prix_vente_rf2_encrypted = Column(Text, nullable=True)
    prix_vente_reel = Column(Numeric(15, 2), nullable=False)  # RF1 + RF2

    # ── State machine ────────────────────────────────────────────────────
    statut_global = Column(String(30), nullable=False, index=True,
                           server_default="'DISPONIBLE'")

    # ── RF2 securization tracking ────────────────────────────────────────
    statut_rf2 = Column(String(30), nullable=True)
    # NON_SECURISE, PARTIELLEMENT_SECURISE, SECURISE
    montant_rf2_securise = Column(Numeric(15, 2), nullable=False,
                                   server_default="0")
    montant_rf2_restant = Column(Numeric(15, 2), nullable=True)
    rf2_last_payment_at = Column(DateTime(timezone=True), nullable=True)

    # ── Key dates ────────────────────────────────────────────────────────
    date_reservation = Column(Date, nullable=True)
    date_engagement = Column(Date, nullable=True)
    date_signature_contrat = Column(Date, nullable=True)
    date_livraison_prevue = Column(Date, nullable=True)
    date_livraison_effective = Column(Date, nullable=True)

    # ── People ───────────────────────────────────────────────────────────
    agent_commercial_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    responsable_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    notaire_id = Column(UUID(as_uuid=True), nullable=True)
    banque_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Credit-specific ──────────────────────────────────────────────────
    montant_credit = Column(Numeric(15, 2), nullable=True)
    montant_apport = Column(Numeric(15, 2), nullable=True)  # 20% apport
    fond_garantie_disponible = Column(Numeric(15, 2), nullable=True)
    credit_rejection_reason = Column(Text, nullable=True)

    # ── Own-funds specific ───────────────────────────────────────────────
    montant_total_verse = Column(Numeric(15, 2), nullable=False,
                                  server_default="0")
    seuil_30_pct_atteint = Column(String(1), nullable=False,
                                    server_default="'N'")

    # ── Installment schedule link ────────────────────────────────────────
    echeancier_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Documents ────────────────────────────────────────────────────────
    documents_checklist = Column(JSONB, nullable=True)

    # ── Notes ────────────────────────────────────────────────────────────
    notes = Column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    client = relationship("Client")
    lot = relationship("Lot")
    project = relationship("Project")
    agent_commercial = relationship(
        "AuthUser", foreign_keys="[DossierAdv.agent_commercial_id]"
    )
    responsable_adv = relationship(
        "AuthUser", foreign_keys="[DossierAdv.responsable_adv_id]"
    )
    payments = relationship(
        "DossierPayment", back_populates="dossier", lazy="select"
    )

    def __repr__(self):
        return f"<DossierAdv {self.numero_dossier} {self.statut_global}>"
