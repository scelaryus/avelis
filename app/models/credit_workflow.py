"""
GFI v7.0 — Credit workflow models: CreditTier, ExpertReport,
WireTransferOrder, GuaranteeFund.

9-step credit purchase workflow with 5 disbursement tiers
(20% + 15% + 35% + 25% + 5% = 100%).

All models use GFIBase (company_id = the selling entity).
"""

from sqlalchemy import (
    Boolean,
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


class CreditTier(GFIBase, Base):
    """Tracks each of the 5 disbursement tiers per credit dossier."""

    __tablename__ = "credit_tier"

    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Tier identity ────────────────────────────────────────────────────
    tier_number = Column(Integer, nullable=False)  # 0,1,2,3,4
    tier_label = Column(String(30), nullable=False)
    # TIER_20PCT, TIER_15PCT, TIER_35PCT, TIER_25PCT, TIER_5PCT
    percentage = Column(Numeric(5, 2), nullable=False)
    montant = Column(Numeric(15, 2), nullable=False)

    # ── Status ───────────────────────────────────────────────────────────
    # EN_ATTENTE, EXPERT_RECU, EXPERT_VALIDE, DEMANDE_SOUMISE,
    # VIREMENT_RECU, DEBLOQUE, BLOQUE
    status = Column(String(20), nullable=False, server_default="'EN_ATTENTE'")

    # ── Disbursement routing ─────────────────────────────────────────────
    # VIA_NOTAIRE (tier 0 and 4) or DIRECT (tiers 1,2,3)
    routing = Column(String(20), nullable=False)

    # ── Expert report link (tiers 1,2,3) ─────────────────────────────────
    expert_report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("expert_report.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Wire transfer order link (tiers 1,2,3) ──────────────────────────
    wire_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("wire_transfer_order.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Dates ────────────────────────────────────────────────────────────
    request_submitted_at = Column(DateTime(timezone=True), nullable=True)
    wire_received_at = Column(DateTime(timezone=True), nullable=True)
    debloque_at = Column(DateTime(timezone=True), nullable=True)

    # ── Payment link ─────────────────────────────────────────────────────
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Alert tracking ───────────────────────────────────────────────────
    wire_alert_sent_at = Column(DateTime(timezone=True), nullable=True)
    days_since_request = Column(Integer, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    dossier = relationship("DossierAdv")
    expert_report = relationship("ExpertReport")
    wire_order = relationship("WireTransferOrder")

    def __repr__(self):
        return (
            f"<CreditTier {self.tier_label} {self.percentage}% "
            f"{self.status}>"
        )


class ExpertReport(GFIBase, Base):
    """Construction expert report for tier disbursement validation."""

    __tablename__ = "expert_report"

    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Tier this report covers ──────────────────────────────────────────
    tier_percentage = Column(Numeric(5, 2), nullable=False)
    # 15, 35, or 25

    # ── Expert info ──────────────────────────────────────────────────────
    expert_name = Column(String(255), nullable=False)
    agrement_number = Column(String(50), nullable=True)
    site_visit_date = Column(Date, nullable=True)
    report_date = Column(Date, nullable=False)

    # ── Findings ─────────────────────────────────────────────────────────
    completion_percentage = Column(Numeric(5, 2), nullable=True)
    conformity = Column(Boolean, nullable=True)
    observations = Column(Text, nullable=True)
    document_url = Column(Text, nullable=True)

    # ── Validation (CRE-005) ─────────────────────────────────────────────
    # RECU, VALIDE, REJETE
    status = Column(String(20), nullable=False, server_default="'RECU'")
    validated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    validated_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    dossier = relationship("DossierAdv")
    project = relationship("Project")

    def __repr__(self):
        return (
            f"<ExpertReport tier={self.tier_percentage}% "
            f"{self.status} by {self.expert_name}>"
        )


class WireTransferOrder(GFIBase, Base):
    """Pre-signed wire transfer order for credit tier disbursement."""

    __tablename__ = "wire_transfer_order"

    dossier_adv_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Order details ────────────────────────────────────────────────────
    tier_percentage = Column(Numeric(5, 2), nullable=False)
    montant = Column(Numeric(15, 2), nullable=False)
    dossier_reference = Column(String(40), nullable=False)
    company_bank_account = Column(String(50), nullable=True)

    # ── Signing ──────────────────────────────────────────────────────────
    signature_date = Column(Date, nullable=True)
    scan_url = Column(Text, nullable=True)

    # EN_ATTENTE, SIGNE, EXECUTE
    status = Column(String(20), nullable=False, server_default="'EN_ATTENTE'")

    # ── Relationships ────────────────────────────────────────────────────
    dossier = relationship("DossierAdv")

    def __repr__(self):
        return (
            f"<WireTransferOrder {self.tier_percentage}% "
            f"{self.montant} DA {self.status}>"
        )


class GuaranteeFund(GFIBase, Base):
    """Guarantee fund availability per entity+project+bank."""

    __tablename__ = "guarantee_fund"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    bank_name = Column(String(100), nullable=False)

    # ── Fund amounts ─────────────────────────────────────────────────────
    garantie_totale = Column(Numeric(15, 2), nullable=False)
    garantie_utilisee = Column(Numeric(15, 2), nullable=False,
                                server_default="0")
    garantie_disponible = Column(Numeric(15, 2), nullable=False)

    def __repr__(self):
        return (
            f"<GuaranteeFund {self.bank_name} "
            f"dispo={self.garantie_disponible} DA>"
        )
