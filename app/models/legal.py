"""
GFI v7.0 — Legal + Governance: ContractLifecycle, ShareTransfer,
PreemptionRight, CapitalCall.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class ContractLifecycle(GFIBase, Base):
    """All contract types: supplier, lease, subcontractor, employment, etc."""

    __tablename__ = "contract_lifecycle"

    contract_type = Column(String(30), nullable=False)
    # FOURNISSEUR, BAIL, SOUS_TRAITANT, EMPLOI, PRESTATION, AUTRE
    contract_ref = Column(String(50), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    counterparty_name = Column(String(255), nullable=False)
    counterparty_id = Column(UUID(as_uuid=True), nullable=True)

    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # ── Dates ────────────────────────────────────────────────────────────
    signature_date = Column(Date, nullable=True)
    effective_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True, index=True)
    termination_date = Column(Date, nullable=True)

    # ── Financial ────────────────────────────────────────────────────────
    montant = Column(Numeric(15, 2), nullable=True)
    periodicite_paiement = Column(String(20), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # BROUILLON, SIGNE, ACTIF, EXPIRE, RENOUVELE, RESILIE
    status = Column(String(20), nullable=False, server_default="'BROUILLON'")

    # ── Renewal ──────────────────────────────────────────────────────────
    auto_renewal = Column(Boolean, nullable=False, server_default="false")
    renewal_notice_days = Column(Integer, nullable=True)
    renewed_contract_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Alerts ───────────────────────────────────────────────────────────
    alert_30d_sent = Column(Boolean, nullable=False, server_default="false")
    alert_15d_sent = Column(Boolean, nullable=False, server_default="false")
    alert_7d_sent = Column(Boolean, nullable=False, server_default="false")

    # ── Documents ────────────────────────────────────────────────────────
    document_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ContractLifecycle {self.contract_type} {self.title[:30]} {self.status}>"


class ShareTransfer(GFIBase, Base):
    """Share transfer with preemption rights enforcement (R-017)."""

    __tablename__ = "share_transfer"

    # ── Transfer parties ─────────────────────────────────────────────────
    seller_associate_id = Column(
        UUID(as_uuid=True), ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    buyer_name = Column(String(255), nullable=False)
    buyer_associate_id = Column(
        UUID(as_uuid=True), ForeignKey("associate.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_internal_transfer = Column(Boolean, nullable=False, server_default="false")

    # ── What is being transferred ────────────────────────────────────────
    # ENTREPRISE or PROJET
    ownership_type = Column(String(20), nullable=False)
    target_entity_id = Column(UUID(as_uuid=True), nullable=False)
    # company_id or project_id depending on type
    percentage_transferred = Column(Numeric(7, 4), nullable=False)
    transfer_price = Column(Numeric(15, 2), nullable=True)

    # ── Dates ────────────────────────────────────────────────────────────
    request_date = Column(Date, nullable=False)
    preemption_deadline = Column(Date, nullable=False)
    preemption_period_days = Column(Integer, nullable=False, server_default="30")
    completion_date = Column(Date, nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # DEMANDE, PREEMPTION_EN_COURS, PREEMPTION_EXERCEE,
    # APPROUVE, EXECUTE, ANNULE, BLOQUE
    status = Column(String(30), nullable=False, server_default="'DEMANDE'")
    blocking_reason = Column(Text, nullable=True)

    # ── Post-transfer verification ───────────────────────────────────────
    sum_verified_100pct = Column(Boolean, nullable=True)  # KT-09

    seller = relationship("Associate", foreign_keys=[seller_associate_id])

    def __repr__(self):
        return (
            f"<ShareTransfer {self.percentage_transferred}% "
            f"from {self.seller_associate_id} {self.status}>"
        )


class PreemptionRight(GFIBase, Base):
    """Individual associate's response to a preemption notification."""

    __tablename__ = "preemption_right"

    share_transfer_id = Column(
        UUID(as_uuid=True), ForeignKey("share_transfer.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    associate_id = Column(
        UUID(as_uuid=True), ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    notified_at = Column(DateTime(timezone=True), nullable=False)
    deadline = Column(Date, nullable=False)
    # NOTIFIE, EXERCE, RENONCE, EXPIRE
    response = Column(String(20), nullable=False, server_default="'NOTIFIE'")
    response_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    associate = relationship("Associate")

    def __repr__(self):
        return f"<PreemptionRight {self.associate_id} {self.response}>"


class CapitalCall(GFIBase, Base):
    """Capital call with CCA freeze on non-payment (R-016)."""

    __tablename__ = "capital_call"

    associate_id = Column(
        UUID(as_uuid=True), ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    call_date = Column(Date, nullable=False)
    call_ref = Column(String(50), nullable=True)
    montant = Column(Numeric(15, 2), nullable=False)
    due_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)

    # ── Payment tracking ─────────────────────────────────────────────────
    montant_paye = Column(Numeric(15, 2), nullable=False, server_default="0")
    montant_restant = Column(Numeric(15, 2), nullable=False)

    # ── Status ───────────────────────────────────────────────────────────
    # EMIS, PARTIELLEMENT_PAYE, PAYE, IMPAYE, BLOQUE
    status = Column(String(20), nullable=False, server_default="'EMIS'")

    # ── CCA freeze link ──────────────────────────────────────────────────
    cca_freeze_id = Column(
        UUID(as_uuid=True), ForeignKey("cca_freeze.id", ondelete="SET NULL"),
        nullable=True,
    )

    associate = relationship("Associate")

    def __repr__(self):
        return f"<CapitalCall {self.montant} DA {self.status}>"
