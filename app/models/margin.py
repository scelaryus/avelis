"""
GFI v7.0 — MarginCalculation + QuotePartResult: project profitability
and per-associate profit distribution.

MarginCalculation stores the 6 margin indicators per project snapshot.
QuotePartResult stores the 3-step distribution for each associate.
"""

from sqlalchemy import Column, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class MarginCalculation(GFIBase, Base):
    """Snapshot of margin indicators for a project at a point in time."""

    __tablename__ = "margin_calculation"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    calculation_date = Column(Date, nullable=False, index=True)
    period_label = Column(String(20), nullable=True)  # e.g., "2026-03"

    # ── Revenue ──────────────────────────────────────────────────────────
    ca_rf1 = Column(Numeric(15, 2), nullable=False, server_default="0")
    ca_rf2 = Column(Numeric(15, 2), nullable=False, server_default="0")
    ca_total = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Costs by category ────────────────────────────────────────────────
    cc1_terrain = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc2_construction = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc3_materiaux = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc4_payroll = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc5_bbz = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc6_cff = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc7_inter_proj = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc8_compensation = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc9_assoc = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc10_commission = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc11_impots = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc14_frais_adm = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc15_frais_fin = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc16_divers = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Margin indicators ────────────────────────────────────────────────
    cout_direct = Column(Numeric(15, 2), nullable=False, server_default="0")
    marge_brute = Column(Numeric(15, 2), nullable=False, server_default="0")
    cout_total = Column(Numeric(15, 2), nullable=False, server_default="0")
    marge_nette = Column(Numeric(15, 2), nullable=False, server_default="0")
    marge_operationnelle = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Full breakdown (JSON) ────────────────────────────────────────────
    detail_json = Column(JSONB, nullable=True)

    project = relationship("Project")
    quote_parts = relationship(
        "QuotePartResult", back_populates="margin_calc", lazy="select"
    )

    def __repr__(self):
        return (
            f"<MarginCalculation {self.project_id} "
            f"marge_nette={self.marge_nette} DA>"
        )


class QuotePartResult(GFIBase, Base):
    """Per-associate 3-step distribution result."""

    __tablename__ = "quote_part_result"

    margin_calculation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("margin_calculation.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Percentages used ─────────────────────────────────────────────────
    pct_projet = Column(Numeric(7, 4), nullable=False)

    # ── Step 1: QP brute from project margin ─────────────────────────────
    qp_brute = Column(Numeric(15, 2), nullable=False)

    # ── Step 2: CFF deduction (using COMPANY %) ──────────────────────────
    cff_total_deducted = Column(Numeric(15, 2), nullable=False, server_default="0")
    qp_after_cff = Column(Numeric(15, 2), nullable=False)

    # ── Step 3: Personal items deduction ─────────────────────────────────
    cc9_withdrawals = Column(Numeric(15, 2), nullable=False, server_default="0")
    cc10_commissions = Column(Numeric(15, 2), nullable=False, server_default="0")
    qp_finale = Column(Numeric(15, 2), nullable=False)

    # ── Alternative views ────────────────────────────────────────────────
    qp_without_cff = Column(Numeric(15, 2), nullable=True)  # Table 2
    cff_cost_delta = Column(Numeric(15, 2), nullable=True)   # Table 1 - Table 2
    qp_operationnelle = Column(Numeric(15, 2), nullable=True)  # View B

    margin_calc = relationship("MarginCalculation", back_populates="quote_parts")
    associate = relationship("Associate")

    def __repr__(self):
        return (
            f"<QuotePartResult {self.associate_id} "
            f"qp_finale={self.qp_finale} DA>"
        )
