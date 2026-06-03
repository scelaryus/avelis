"""
GFI v7.0 — AssociateWithdrawal, InterProjectFlow, FoundingCapital.

Tracks apartment withdrawals (CC9), inter-project flows (CC7),
and the 4 founding capital ODs that started EDEN.
"""

from sqlalchemy import (
    Column, Date, ForeignKey, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class AssociateWithdrawal(GFIBase, Base):
    """CC9: Associate apartment withdrawal from a project."""

    __tablename__ = "associate_withdrawal"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Withdrawn assets ─────────────────────────────────────────────────
    description = Column(Text, nullable=False)
    lot_references = Column(JSONB, nullable=True)
    # e.g., ["F3-EDEN-012", "F2-EDEN-034"]
    valeur_attribution = Column(Numeric(15, 2), nullable=False)
    withdrawal_date = Column(Date, nullable=True)

    # ── Subsequent disposition ───────────────────────────────────────────
    # GARDE, VENDU, CEDE, LOUE, INCONNU
    disposition = Column(String(20), nullable=True)
    ceded_to = Column(String(255), nullable=True)
    sale_price = Column(Numeric(15, 2), nullable=True)
    buyer_name = Column(String(255), nullable=True)
    net_benefit = Column(Numeric(15, 2), nullable=True)
    # sale_price - valeur_attribution - fees

    # ── CC/CCA links ─────────────────────────────────────────────────────
    cc_entry_id = Column(UUID(as_uuid=True), nullable=True)
    cca_movement_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Formulaire if data missing ───────────────────────────────────────
    formulaire_ref = Column(String(20), nullable=True)
    # FC-017 (Yamina status), FC-018 (Mohamed), etc.

    project = relationship("Project")
    associate = relationship("Associate")

    def __repr__(self):
        return (
            f"<AssociateWithdrawal {self.associate_id} "
            f"{self.valeur_attribution} DA from {self.project_id}>"
        )


class InterProjectFlow(GFIBase, Base):
    """CC7: Money flowing between projects via the common cash pool."""

    __tablename__ = "inter_project_flow"

    # ── Source and destination ────────────────────────────────────────────
    source_project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    dest_project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Amount and date ──────────────────────────────────────────────────
    montant = Column(Numeric(15, 2), nullable=False)
    flow_date = Column(Date, nullable=True)
    description = Column(Text, nullable=False)

    # ── Nature (determined via FC-016) ───────────────────────────────────
    # PRET, INVESTISSEMENT, INDETERMINE
    nature = Column(String(20), nullable=False, server_default="'INDETERMINE'")
    taux_interet = Column(Numeric(5, 2), nullable=True)
    duree_mois = Column(__import__("sqlalchemy").Integer, nullable=True)
    formulaire_ref = Column(String(20), nullable=True)  # FC-016

    # ── CC mirror entries ────────────────────────────────────────────────
    # Debit on source project, credit on dest project
    cc_debit_entry_id = Column(UUID(as_uuid=True), nullable=True)
    cc_credit_entry_id = Column(UUID(as_uuid=True), nullable=True)

    source_project = relationship("Project", foreign_keys=[source_project_id])
    dest_project = relationship("Project", foreign_keys=[dest_project_id])

    def __repr__(self):
        return (
            f"<InterProjectFlow {self.montant} DA "
            f"{self.source_project_id} -> {self.dest_project_id}>"
        )


class FoundingCapital(GFIBase, Base):
    """The 4 ODs that founded EDEN — first entries on each associate's CCA."""

    __tablename__ = "founding_capital"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── OD details ───────────────────────────────────────────────────────
    od_reference = Column(String(20), nullable=False)  # OD-001, OD-002, etc.
    montant = Column(Numeric(15, 2), nullable=True)
    # NULL until confirmed (FC-015 for AMENFORT sale amount)
    source_description = Column(Text, nullable=False)
    capital_date = Column(Date, nullable=True)

    # ── Source entity (where the money came from) ────────────────────────
    # AMENFORT for Ahmed/Mohamed/Lyazid; EURL_ABC_SI for Yamina
    source_entity = Column(String(100), nullable=False)
    is_amenfort_linked = Column(
        __import__("sqlalchemy").Boolean, nullable=False, server_default="false"
    )

    # ── Links ────────────────────────────────────────────────────────────
    cc_entry_id = Column(UUID(as_uuid=True), nullable=True)
    cca_movement_id = Column(UUID(as_uuid=True), nullable=True)
    formulaire_ref = Column(String(20), nullable=True)  # FC-015

    project = relationship("Project")
    associate = relationship("Associate")

    def __repr__(self):
        return (
            f"<FoundingCapital {self.od_reference} {self.associate_id} "
            f"from {self.source_entity}>"
        )
