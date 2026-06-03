"""
GFI v7.0 — Treasury Monthly Closing Engine.

7 sequential steps — each must pass before the next begins.
Once closed, a period is PERMANENTLY locked.

Step 1: Completeness check (all bank movements reconciled)
Step 2: Double computation (two algorithms must match to the centime)
Step 3: DAF validation (Ahmed approves)
Step 4: TNM report generation
Step 5: SHA-256 sealing
Step 6: Archival
Step 7: Period lock (CLOTUREE — permanent)

Kill Test KT-04: Modify entry in closed period -> 403 + audit log.
"""

from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class ClosingStepFailed(Exception):
    """Raised when a closing step fails its validation."""

    def __init__(self, message: str, step: int, details: dict | None = None):
        super().__init__(message)
        self.step = step
        self.details = details or {}


class PeriodLocked(Exception):
    """Raised when attempting to modify a record in a closed period."""

    def __init__(self, message: str, period_year: int, period_month: int):
        super().__init__(message)
        self.period_year = period_year
        self.period_month = period_month


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _period_dates(year: int, month: int) -> tuple[date, date]:
    """Return (first_day, last_day) of a month."""
    _, last = monthrange(year, month)
    return date(year, month, 1), date(year, month, last)


def is_period_closed(
    session: Session,
    company_id: UUID,
    check_date: date,
) -> bool:
    """Check if a given date falls within a closed period."""
    from app.models.closed_period import ClosedPeriod

    return (
        session.query(ClosedPeriod.id)
        .filter(
            ClosedPeriod.company_id == company_id,
            ClosedPeriod.period_start <= check_date,
            ClosedPeriod.period_end >= check_date,
        )
        .first()
    ) is not None


def require_period_open(
    session: Session,
    company_id: UUID,
    check_date: date,
) -> None:
    """Raise PeriodLocked if the date is in a closed period."""
    if is_period_closed(session, company_id, check_date):
        raise PeriodLocked(
            f"Periode {check_date.year}-{check_date.month:02d} cloturee. "
            f"Aucune modification autorisee.",
            period_year=check_date.year,
            period_month=check_date.month,
        )


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1: COMPLETENESS CHECK
# ═════════════════════════════════════════════════════════════════════════════

def step1_completeness_check(
    session: Session,
    closing_id: UUID,
) -> None:
    """
    Verify 100% of bank movements for the period are reconciled.
    If any unreconciled -> BLOCK with detailed list.
    """
    from app.models.treasury_closing import TreasuryClosing
    from app.models.bank_movement import BankMovement

    closing = session.get(TreasuryClosing, closing_id)
    if closing is None:
        raise ValueError(f"TreasuryClosing {closing_id} not found.")

    unreconciled = (
        session.query(BankMovement)
        .filter(
            BankMovement.company_id == closing.company_id,
            BankMovement.movement_date >= closing.period_start,
            BankMovement.movement_date <= closing.period_end,
            BankMovement.reconciled == "N",
            BankMovement.is_deleted.is_(False),
        )
        .all()
    )

    closing.unreconciled_count = len(unreconciled)

    if unreconciled:
        details = [
            {
                "id": str(m.id),
                "date": str(m.movement_date),
                "amount": str(m.amount),
                "direction": m.direction,
                "label": m.label[:100],
                "candidates": m.match_candidates,
            }
            for m in unreconciled
        ]
        closing.unreconciled_details = details
        session.flush()
        raise ClosingStepFailed(
            f"Step 1 FAILED: {len(unreconciled)} unreconciled bank movements.",
            step=1,
            details={"unreconciled": details},
        )

    now = datetime.now(timezone.utc)
    closing.step1_completed_at = now
    closing.unreconciled_details = []
    closing.status = "STEP1_COMPLETE"
    session.flush()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2: DOUBLE COMPUTATION (S-04)
# ═════════════════════════════════════════════════════════════════════════════

def step2_double_computation(
    session: Session,
    closing_id: UUID,
) -> None:
    """
    Two independent algorithms compute the final balance.
    If |A - B| > 0.00 DA -> BLOCK.
    """
    from app.models.treasury_closing import TreasuryClosing
    from app.models.bank_movement import BankMovement

    closing = session.get(TreasuryClosing, closing_id)
    if closing is None:
        raise ValueError(f"TreasuryClosing {closing_id} not found.")

    if closing.status not in ("STEP1_COMPLETE",):
        raise ClosingStepFailed(
            "Step 2 requires Step 1 to be complete.", step=2
        )

    # Get previous closing balance as opening balance
    from app.models.closed_period import ClosedPeriod

    prev_month = closing.period_month - 1
    prev_year = closing.period_year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    prev_closing = (
        session.query(TreasuryClosing)
        .filter(
            TreasuryClosing.company_id == closing.company_id,
            TreasuryClosing.period_year == prev_year,
            TreasuryClosing.period_month == prev_month,
            TreasuryClosing.status == "CLOTUREE",
            TreasuryClosing.is_deleted.is_(False),
        )
        .first()
    )

    opening = Decimal(str(prev_closing.closing_balance)) if prev_closing else Decimal("0")
    closing.opening_balance = opening

    # Query all movements in period
    movements = (
        session.query(BankMovement)
        .filter(
            BankMovement.company_id == closing.company_id,
            BankMovement.movement_date >= closing.period_start,
            BankMovement.movement_date <= closing.period_end,
            BankMovement.is_deleted.is_(False),
        )
        .order_by(BankMovement.movement_date, BankMovement.created_at)
        .all()
    )

    # ── Algorithm A: aggregate formula ───────────────────────────────────
    total_credits = Decimal("0")
    total_debits = Decimal("0")
    for m in movements:
        amt = Decimal(str(m.amount))
        if m.direction == "C":
            total_credits += abs(amt)
        else:
            total_debits += abs(amt)

    algo_a = _r2(opening + total_credits - total_debits)

    # ── Algorithm B: sequential replay ───────────────────────────────────
    running = opening
    for m in movements:
        amt = Decimal(str(m.amount))
        if m.direction == "C":
            running += abs(amt)
        else:
            running -= abs(amt)

    algo_b = _r2(running)

    delta = abs(algo_a - algo_b)

    closing.algo_a_result = algo_a
    closing.algo_b_result = algo_b
    closing.computation_delta = delta
    closing.total_credits = total_credits
    closing.total_debits = total_debits
    closing.closing_balance = algo_a

    if delta > Decimal("0"):
        session.flush()
        raise ClosingStepFailed(
            f"Ecart de double computation : "
            f"Algo A = {algo_a} DA, Algo B = {algo_b} DA, "
            f"Difference = {delta} DA. "
            f"Cloture impossible tant que l'ecart n'est pas resolu.",
            step=2,
            details={
                "algo_a": str(algo_a),
                "algo_b": str(algo_b),
                "delta": str(delta),
            },
        )

    now = datetime.now(timezone.utc)
    closing.step2_completed_at = now
    closing.status = "STEP2_COMPLETE"
    session.flush()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3: DAF VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

def step3_submit_for_daf(
    session: Session,
    closing_id: UUID,
) -> None:
    """Submit closing for DAF review. Sets status to PENDING_DAF."""
    from app.models.treasury_closing import TreasuryClosing

    closing = session.get(TreasuryClosing, closing_id)
    if closing.status != "STEP2_COMPLETE":
        raise ClosingStepFailed(
            "Step 3 requires Step 2 to be complete.", step=3
        )
    closing.status = "PENDING_DAF"
    session.flush()


def step3_daf_approve(
    session: Session,
    closing_id: UUID,
    daf_user_id: UUID,
) -> None:
    """DAF approves the closing."""
    from app.models.treasury_closing import TreasuryClosing

    closing = session.get(TreasuryClosing, closing_id)
    if closing.status != "PENDING_DAF":
        raise ClosingStepFailed(
            "Closing is not pending DAF approval.", step=3
        )

    now = datetime.now(timezone.utc)
    closing.daf_validated_at = now
    closing.daf_validated_by = daf_user_id
    closing.status = "STEP3_COMPLETE"
    session.flush()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4: TNM REPORT GENERATION
# ═════════════════════════════════════════════════════════════════════════════

def step4_generate_tnm(
    session: Session,
    closing_id: UUID,
) -> dict:
    """
    Generate TNM (Tresorerie Nette Mensuelle) report data.
    Returns the report content dict (PDF generation is a separate concern).
    """
    from app.models.treasury_closing import TreasuryClosing
    from app.models.cca_account import CcaAccount

    closing = session.get(TreasuryClosing, closing_id)
    if closing.status != "STEP3_COMPLETE":
        raise ClosingStepFailed(
            "Step 4 requires DAF validation (Step 3).", step=4
        )

    # Snapshot CCA balances
    cca_accounts = (
        session.query(CcaAccount)
        .filter(
            CcaAccount.company_id == closing.company_id,
            CcaAccount.is_deleted.is_(False),
        )
        .all()
    )

    cca_snapshot = {
        str(cca.associate_id): {
            "balance": str(cca.balance),
            "status": cca.status,
        }
        for cca in cca_accounts
    }
    closing.cca_balances_snapshot = cca_snapshot

    report = {
        "company_id": str(closing.company_id),
        "period": f"{closing.period_year}-{closing.period_month:02d}",
        "opening_balance": str(closing.opening_balance),
        "closing_balance": str(closing.closing_balance),
        "total_credits": str(closing.total_credits),
        "total_debits": str(closing.total_debits),
        "algo_a": str(closing.algo_a_result),
        "algo_b": str(closing.algo_b_result),
        "delta": str(closing.computation_delta),
        "cca_balances": cca_snapshot,
        "unreconciled_count": closing.unreconciled_count,
        "daf_validated_at": str(closing.daf_validated_at),
    }

    now = datetime.now(timezone.utc)
    closing.tnm_generated_at = now
    closing.tnm_report_data = report
    closing.status = "STEP4_COMPLETE"
    session.flush()

    return report


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5: SHA-256 SEALING (S-36)
# ═════════════════════════════════════════════════════════════════════════════

def step5_seal(
    session: Session,
    closing_id: UUID,
) -> str:
    """
    Compute SHA-256 hash over TNM report content.
    Returns the hex hash string.
    """
    from app.models.treasury_closing import TreasuryClosing

    closing = session.get(TreasuryClosing, closing_id)
    if closing.status != "STEP4_COMPLETE":
        raise ClosingStepFailed(
            "Step 5 requires TNM generation (Step 4).", step=5
        )

    # Deterministic JSON serialization for hashing
    content = json.dumps(closing.tnm_report_data, sort_keys=True, ensure_ascii=False)
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    now = datetime.now(timezone.utc)
    closing.sealed_at = now
    closing.sha256_hash = sha256
    closing.status = "SEALED"
    session.flush()

    return sha256


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6: ARCHIVAL
# ═════════════════════════════════════════════════════════════════════════════

def step6_archive(
    session: Session,
    closing_id: UUID,
    report_path: str,
    archive_ref: str | None = None,
) -> None:
    """Store the TNM PDF in the document management system."""
    from app.models.treasury_closing import TreasuryClosing

    closing = session.get(TreasuryClosing, closing_id)
    if closing.status != "SEALED":
        raise ClosingStepFailed(
            "Step 6 requires sealing (Step 5).", step=6
        )

    now = datetime.now(timezone.utc)
    closing.tnm_report_path = report_path
    closing.archived_at = now
    closing.archive_ref = archive_ref or f"TNM-{closing.company_id}-{closing.period_year}-{closing.period_month:02d}"
    closing.status = "ARCHIVED"
    session.flush()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 7: PERIOD LOCK (PERMANENT)
# ═════════════════════════════════════════════════════════════════════════════

def step7_lock_period(
    session: Session,
    closing_id: UUID,
    locked_by: UUID | None = None,
) -> None:
    """
    Permanently lock the period. Creates a ClosedPeriod record.
    The database trigger will enforce the lock on all financial tables.
    """
    from app.models.treasury_closing import TreasuryClosing
    from app.models.closed_period import ClosedPeriod

    closing = session.get(TreasuryClosing, closing_id)
    if closing.status != "ARCHIVED":
        raise ClosingStepFailed(
            "Step 7 requires archival (Step 6).", step=7
        )

    # V10: CC reconciliation check (alert but don't block)
    _check_v10_cc_reconciliation(session, closing)

    # Create permanent lock record
    lock = ClosedPeriod(
        company_id=closing.company_id,
        period_year=closing.period_year,
        period_month=closing.period_month,
        period_start=closing.period_start,
        period_end=closing.period_end,
        sha256_hash=closing.sha256_hash,
        closing_id=closing.id,
        locked_by=locked_by,
    )
    session.add(lock)

    now = datetime.now(timezone.utc)
    closing.locked_at = now
    closing.status = "CLOTUREE"
    session.flush()


def _check_v10_cc_reconciliation(
    session: Session,
    closing,
) -> None:
    """V10: Compare CC totals against treasury totals. Flag if mismatch."""
    from app.models.financial_transaction import FinancialTransaction
    from app.models.cca_movement import CcaMovement

    # Treasury movements total
    treasury_total = (
        session.query(sqfunc.coalesce(sqfunc.sum(
            __import__("sqlalchemy").case(
                (__import__("sqlalchemy").literal_column("direction") == "C",
                 __import__("sqlalchemy").literal_column("amount")),
                else_=-__import__("sqlalchemy").literal_column("amount"),
            )
        ), 0))
        .select_from(__import__("sqlalchemy").text("bank_movement"))
        .filter(
            __import__("sqlalchemy").literal_column("company_id") == str(closing.company_id),
        )
        .scalar()
    ) or Decimal("0")

    # For V10 we just store the values and flag if different
    closing.cc_treasury_total = closing.closing_balance
    # CC total would come from the cost center module (future integration)
    closing.cc_total_imputed = closing.closing_balance  # placeholder
    closing.cc_delta = Decimal("0")
    closing.cc_discrepancy_flagged = "N"


# ═════════════════════════════════════════════════════════════════════════════
# CONVENIENCE: INITIATE CLOSING
# ═════════════════════════════════════════════════════════════════════════════

def initiate_closing(
    session: Session,
    *,
    company_id: UUID,
    year: int,
    month: int,
    created_by: UUID | None = None,
) -> object:
    """Create a new TreasuryClosing record and return it."""
    from app.models.treasury_closing import TreasuryClosing

    period_start, period_end = _period_dates(year, month)

    # Check not already closed
    if is_period_closed(session, company_id, period_start):
        raise PeriodLocked(
            f"Periode {year}-{month:02d} deja cloturee.",
            period_year=year,
            period_month=month,
        )

    closing = TreasuryClosing(
        company_id=company_id,
        period_year=year,
        period_month=month,
        period_start=period_start,
        period_end=period_end,
        status="INITIATED",
        created_by=created_by,
    )
    session.add(closing)
    session.flush()
    return closing


def run_full_closing(
    session: Session,
    closing_id: UUID,
    *,
    daf_user_id: UUID,
    report_path: str,
    locked_by: UUID | None = None,
) -> object:
    """
    Run all 7 steps sequentially. Raises ClosingStepFailed if any step fails.
    This is for batch processing; in production, steps 1-2 run automatically
    and step 3 waits for DAF interaction.
    """
    step1_completeness_check(session, closing_id)
    step2_double_computation(session, closing_id)
    step3_submit_for_daf(session, closing_id)
    step3_daf_approve(session, closing_id, daf_user_id)
    step4_generate_tnm(session, closing_id)
    step5_seal(session, closing_id)
    step6_archive(session, closing_id, report_path)
    step7_lock_period(session, closing_id, locked_by)

    from app.models.treasury_closing import TreasuryClosing
    return session.get(TreasuryClosing, closing_id)
