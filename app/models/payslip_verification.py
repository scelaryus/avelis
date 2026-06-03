"""
GFI v7.0 — PayslipVerification: 6-level verification pipeline results.

Each payslip passes through L1-L6. Results stored per level.
LangGraph sequential sub-graph: L1->L2->L3->L4->L5->L6.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class PayslipVerification(GFIBase, Base):
    """Per-level verification result for a payslip."""

    __tablename__ = "payslip_verification"

    payslip_id = Column(
        UUID(as_uuid=True), ForeignKey("payslip.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Level ────────────────────────────────────────────────────────────
    level = Column(Integer, nullable=False)  # 1-6
    level_name = Column(String(50), nullable=False)

    # ── Result ───────────────────────────────────────────────────────────
    # PASS, FLAG, FAIL, PENDING, SKIPPED
    verdict = Column(String(10), nullable=False, server_default="'PENDING'")
    executed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # ── Detail ───────────────────────────────────────────────────────────
    checks_performed = Column(Integer, nullable=True)
    checks_passed = Column(Integer, nullable=True)
    checks_failed = Column(Integer, nullable=True)
    checks_flagged = Column(Integer, nullable=True)

    anomalies = Column(JSONB, nullable=True)
    # [{type, severity, description, expected, actual}]

    # ── L2 specific (LLM) ────────────────────────────────────────────────
    llm_raw_response = Column(Text, nullable=True)
    llm_confidence = Column(Numeric(5, 2), nullable=True)

    # ── L4 specific (statistical) ────────────────────────────────────────
    anomaly_score = Column(Numeric(8, 4), nullable=True)
    z_scores = Column(JSONB, nullable=True)

    # ── L6 specific (human) ──────────────────────────────────────────────
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)
    review_action = Column(String(20), nullable=True)
    # APPROVE, REJECT, REQUEST_INFO
    review_justification = Column(Text, nullable=True)

    payslip = relationship("Payslip")

    def __repr__(self):
        return f"<PayslipVerification L{self.level} {self.verdict}>"
