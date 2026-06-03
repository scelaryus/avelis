"""
GFI v7.0 — TreasuryClosing: monthly treasury closing process.

Tracks the 7 sequential steps of the closing process:
  1. Completeness check (all bank movements reconciled)
  2. Double computation (two independent algorithms must match)
  3. DAF validation (Ahmed approves)
  4. TNM report generation (PDF)
  5. SHA-256 sealing (tamper-proof hash)
  6. Archival (DMS storage)
  7. Period lock (CLOTUREE — permanent, no modifications ever)

Uses GFIBase (company_id = the entity being closed).
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


class TreasuryClosing(GFIBase, Base):
    __tablename__ = "treasury_closing"

    # ── Period being closed ──────────────────────────────────────────────
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # ── Status ───────────────────────────────────────────────────────────
    # INITIATED, STEP1_COMPLETE, STEP2_COMPLETE, PENDING_DAF,
    # STEP4_COMPLETE, SEALED, ARCHIVED, CLOTUREE
    status = Column(String(20), nullable=False, server_default="'INITIATED'")

    # ── Step 1: Completeness ─────────────────────────────────────────────
    step1_completed_at = Column(DateTime(timezone=True), nullable=True)
    unreconciled_count = Column(Integer, nullable=True)
    unreconciled_details = Column(JSONB, nullable=True)

    # ── Step 2: Double computation ───────────────────────────────────────
    step2_completed_at = Column(DateTime(timezone=True), nullable=True)
    algo_a_result = Column(Numeric(15, 2), nullable=True)
    algo_b_result = Column(Numeric(15, 2), nullable=True)
    computation_delta = Column(Numeric(15, 2), nullable=True)

    # ── Balances ─────────────────────────────────────────────────────────
    opening_balance = Column(Numeric(15, 2), nullable=True)
    closing_balance = Column(Numeric(15, 2), nullable=True)
    total_credits = Column(Numeric(15, 2), nullable=True)
    total_debits = Column(Numeric(15, 2), nullable=True)

    # ── Step 3: DAF validation ───────────────────────────────────────────
    daf_validated_at = Column(DateTime(timezone=True), nullable=True)
    daf_validated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    daf_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)

    # ── Step 4: TNM report ───────────────────────────────────────────────
    tnm_generated_at = Column(DateTime(timezone=True), nullable=True)
    tnm_report_path = Column(Text, nullable=True)
    tnm_report_data = Column(JSONB, nullable=True)

    # ── Step 5: SHA-256 seal ─────────────────────────────────────────────
    sealed_at = Column(DateTime(timezone=True), nullable=True)
    sha256_hash = Column(String(64), nullable=True)

    # ── Step 6: Archival ─────────────────────────────────────────────────
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archive_ref = Column(String(100), nullable=True)

    # ── Step 7: Period lock ──────────────────────────────────────────────
    locked_at = Column(DateTime(timezone=True), nullable=True)

    # ── V10: CC reconciliation ───────────────────────────────────────────
    cc_total_imputed = Column(Numeric(15, 2), nullable=True)
    cc_treasury_total = Column(Numeric(15, 2), nullable=True)
    cc_delta = Column(Numeric(15, 2), nullable=True)
    cc_discrepancy_flagged = Column(String(1), nullable=False,
                                     server_default="'N'")

    # ── CCA balances snapshot ────────────────────────────────────────────
    cca_balances_snapshot = Column(JSONB, nullable=True)

    def __repr__(self):
        return (
            f"<TreasuryClosing {self.period_year}-{self.period_month:02d} "
            f"{self.status} @ {self.company_id}>"
        )
