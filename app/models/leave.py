"""
GFI v7.0 — Leave Management: LeaveRequest, LeaveBalance, LeaveVerification.

10 leave types with Algerian labor law compliance.
6-level verification for sick leave with L5 fraud detection.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class LeaveBalance(GFIBase, Base):
    """Per-employee annual leave balance."""

    __tablename__ = "leave_balance"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    year = Column(Integer, nullable=False)
    leave_type = Column(String(30), nullable=False)

    entitled_days = Column(Numeric(5, 1), nullable=False)
    used_days = Column(Numeric(5, 1), nullable=False, server_default="0")
    remaining_days = Column(Numeric(5, 1), nullable=False)
    carried_from_previous = Column(Numeric(5, 1), nullable=False, server_default="0")

    employee = relationship("Employee")

    def __repr__(self):
        return (
            f"<LeaveBalance {self.leave_type} {self.year} "
            f"remaining={self.remaining_days}>"
        )


class LeaveRequest(GFIBase, Base):
    """Leave request with full verification pipeline."""

    __tablename__ = "leave_request"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    leave_type = Column(String(30), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False)
    duration_days = Column(Numeric(5, 1), nullable=False)
    reason = Column(Text, nullable=True)

    # ── Documents ────────────────────────────────────────────────────────
    medical_certificate_url = Column(Text, nullable=True)
    supporting_document_url = Column(Text, nullable=True)
    certificate_ocr_result = Column(JSONB, nullable=True)

    # ── Pay impact ───────────────────────────────────────────────────────
    pay_impact = Column(String(20), nullable=False, server_default="'FULL'")
    # FULL, HALF_15D, CNAS_INDEMNITE, ZERO (sans solde)

    # ── Verification pipeline ────────────────────────────────────────────
    # BROUILLON, SOUMISE, EN_VERIFICATION, APPROUVEE_MANAGER,
    # APPROUVEE_DRH, APPROUVEE, REJETEE, ANNULEE
    status = Column(String(30), nullable=False, server_default="'BROUILLON'")

    approved_by_manager = Column(UUID(as_uuid=True), nullable=True)
    approved_by_manager_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_drh = Column(UUID(as_uuid=True), nullable=True)
    approved_by_drh_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # ── Fraud detection ──────────────────────────────────────────────────
    fraud_alert = Column(Boolean, nullable=False, server_default="false")
    fraud_details = Column(JSONB, nullable=True)

    # ── Replacement ──────────────────────────────────────────────────────
    replacement_employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
    )

    employee = relationship("Employee", foreign_keys=[employee_id])

    def __repr__(self):
        return f"<LeaveRequest {self.leave_type} {self.start_date}-{self.end_date} {self.status}>"


class LeaveVerification(GFIBase, Base):
    """Per-level verification result for sick leave (same pattern as payslip)."""

    __tablename__ = "leave_verification"

    leave_request_id = Column(
        UUID(as_uuid=True), ForeignKey("leave_request.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    level = Column(Integer, nullable=False)  # 1-6
    level_name = Column(String(50), nullable=False)
    # PASS, FLAG, FAIL, PENDING
    verdict = Column(String(10), nullable=False, server_default="'PENDING'")
    executed_at = Column(DateTime(timezone=True), nullable=True)
    anomalies = Column(JSONB, nullable=True)

    # L5-specific: badge fraud evidence
    badge_events_during_leave = Column(JSONB, nullable=True)
    fraud_confirmed = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self):
        return f"<LeaveVerification L{self.level} {self.verdict}>"
