"""
GFI v7.0 — Payment: iron-clad RF integrity on every payment.

All fields from CDC-ADV section 1.7. Every payment is classified RF1 or RF2
with database-level constraints enforcing mode de reglement compatibility.

6 blocking constraints (PAY-C01 to PAY-C06):
  C01: RF1 -> CHEQUE/VIREMENT/CHEQUE_NOTAIRE only
  C02: RF2 -> ESPECES only
  C03: SUM(RF1) <= prix_vente_rf1 (no overpayment)
  C04: SUM(RF2) <= prix_vente_rf2
  C05: SUM(RF1+RF2) <= prix_vente_reel
  C06: REJETE/ANNULE payments are immutable

Uses GFIBase (company_id = receiving entity).
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Payment(GFIBase, Base):
    __tablename__ = "payment"

    # ── Links ────────────────────────────────────────────────────────────
    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    lot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Payment classification ───────────────────────────────────────────
    type_paiement = Column(String(30), nullable=False)
    # SPOT, APPORT, DEBLOCAGE_BANQUE, DEBLOCAGE_NOTAIRE,
    # ECHEANCE_FP, RF2_ESPECES

    mode_reglement = Column(String(20), nullable=False)
    # CHEQUE, VIREMENT, ESPECES, CHEQUE_NOTAIRE

    type_rf = Column(String(3), nullable=False)  # RF1 or RF2

    # ── Amount ───────────────────────────────────────────────────────────
    montant = Column(Numeric(15, 2), nullable=False)
    devise = Column(String(3), nullable=False, server_default="'DZD'")

    # ── Payment details ──────────────────────────────────────────────────
    reference_reglement = Column(String(100), nullable=True)
    banque_emettrice = Column(String(100), nullable=True)
    date_paiement = Column(Date, nullable=False, index=True)
    date_valeur = Column(Date, nullable=True)
    date_encaissement_effectif = Column(Date, nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # EN_ATTENTE, ENCAISSE, REJETE, ANNULE
    statut = Column(String(20), nullable=False, server_default="'EN_ATTENTE'")

    # ── Credit tier (disbursement payments only) ─────────────────────────
    palier_deblocage = Column(Numeric(5, 2), nullable=True)
    # 20, 15, 35, 25, 5
    rapport_expert_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Justification ────────────────────────────────────────────────────
    piece_justificative_url = Column(Text, nullable=True)
    observations = Column(Text, nullable=True)

    # ── Maker/checker double validation ──────────────────────────────────
    validated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    validated_at = Column(DateTime(timezone=True), nullable=True)

    # ── Accounting link ──────────────────────────────────────────────────
    journal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journal_entry.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    dossier = relationship("DossierAdv")
    client = relationship("Client")
    lot = relationship("Lot")
    project = relationship("Project")

    def __repr__(self):
        return (
            f"<Payment {self.type_rf} {self.montant} DA "
            f"{self.mode_reglement} {self.statut}>"
        )
