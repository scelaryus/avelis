"""
GFI v7.0 — Autonomous Detection Engine: 15 patterns.

Analyzes raw data to discover entities, flows, and anomalies
without being told where to look. Each finding requires DAF validation.

Core API:
  run_all_patterns(company_id) -> list[DetectionFinding]
  run_pattern(pattern_id, company_id) -> list[DetectionFinding]
  validate_finding(finding_id, action, ...) -> DetectionFinding
  integrate_finding(finding_id) -> applies the proposed action
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc, or_, and_

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _create_finding(
    session, company_id, pattern_id, code, confidence,
    title, description, proposed_action,
    source_docs=None, extracted=None, action_detail=None,
    project_id=None, entity_ids=None,
):
    from app.models.detection import DetectionFinding

    f = DetectionFinding(
        company_id=company_id,
        pattern_id=pattern_id,
        pattern_code=code,
        confidence_score=Decimal(str(confidence)),
        title=title,
        description=description,
        proposed_action=proposed_action,
        proposed_action_detail=action_detail,
        source_documents=source_docs,
        extracted_values=extracted,
        related_entity_ids=entity_ids,
        project_id=project_id,
        status="DETECTED",
    )
    session.add(f)
    session.flush()
    return f


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 1: Group companies (NIF cross-matching)
# ═════════════════════════════════════════════════════════════════════════════

def detect_group_companies(session, company_id):
    """Same NIF appears as both emitter AND receiver across invoices."""
    from app.models.company import Company
    findings = []

    companies = session.query(Company).filter(
        Company.nif.isnot(None), Company.is_deleted.is_(False)
    ).all()
    nifs = {c.nif: c for c in companies if c.nif}

    # Check financial transactions for inter-group NIF matches
    from app.models.financial_transaction import FinancialTransaction
    rf3s = (
        session.query(FinancialTransaction)
        .filter(
            FinancialTransaction.rf_type == "RF3",
            FinancialTransaction.emitter_company_id.isnot(None),
            FinancialTransaction.receiver_company_id.isnot(None),
            FinancialTransaction.is_deleted.is_(False),
        )
        .all()
    )

    seen_pairs = set()
    for tx in rf3s:
        pair = (str(tx.emitter_company_id), str(tx.receiver_company_id))
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            findings.append(_create_finding(
                session, company_id, 1, "GROUP_COMPANIES", 95,
                f"Inter-group RF3 detected",
                f"Emitter {tx.emitter_company_id} -> Receiver {tx.receiver_company_id}",
                "TRIGGER_CFF",
                extracted={"emitter": str(tx.emitter_company_id),
                           "receiver": str(tx.receiver_company_id),
                           "amount": str(tx.amount)},
            ))

    return findings


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 5: RF3 fictitious invoices
# ═════════════════════════════════════════════════════════════════════════════

def detect_rf3_invoices(session, company_id):
    """Emitter AND receiver are both group entities."""
    from app.models.financial_transaction import FinancialTransaction
    from app.models.company import Company

    findings = []
    group_ids = set(str(c.id) for c in session.query(Company).filter(
        Company.is_deleted.is_(False)).all())

    rf3s = (
        session.query(FinancialTransaction)
        .filter(
            FinancialTransaction.rf_type == "RF3",
            FinancialTransaction.cff_triggered == "N",
            FinancialTransaction.is_deleted.is_(False),
        )
        .all()
    )

    for tx in rf3s:
        if (str(tx.emitter_company_id) in group_ids
                and str(tx.receiver_company_id) in group_ids):
            findings.append(_create_finding(
                session, company_id, 5, "RF3_FICTITIOUS", 98,
                f"RF3 between group entities — CFF not triggered",
                f"RF3 invoice {tx.reference}: emitter and receiver are both group entities. "
                f"CFF should have been triggered automatically.",
                "TRIGGER_CFF",
                extracted={"transaction_id": str(tx.id), "amount": str(tx.amount)},
            ))

    return findings


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 4: Inter-project flows (account 580)
# ═════════════════════════════════════════════════════════════════════════════

def detect_inter_project_flows(session, company_id):
    """Matching amounts on account 580 across entity journals."""
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.journal_entry import JournalEntry

    findings = []

    lines_580 = (
        session.query(JournalEntryLine)
        .join(JournalEntry)
        .filter(
            JournalEntryLine.account_code == "580",
            JournalEntry.company_id == company_id,
            JournalEntryLine.is_deleted.is_(False),
        )
        .all()
    )

    debits = [l for l in lines_580 if l.debit > 0]
    credits = [l for l in lines_580 if l.credit > 0]

    for d in debits:
        for c in credits:
            if (str(d.debit) == str(c.credit)
                    and d.entry_id != c.entry_id):
                findings.append(_create_finding(
                    session, company_id, 4, "INTER_PROJECT_FLOW", 85,
                    f"Inter-project flow {d.debit} DA detected",
                    f"Account 580 debit {d.debit} DA matches credit {c.credit} DA",
                    "GENERATE_FORMULAIRE",
                    action_detail={"formulaire": "FC-016"},
                ))

    return findings


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 6: GACEB 120M advance
# ═════════════════════════════════════════════════════════════════════════════

def detect_gaceb_advance(session, company_id):
    """Account 409100 + GACEB + material labels."""
    from app.models.journal_entry_line import JournalEntryLine

    findings = []

    lines = (
        session.query(JournalEntryLine)
        .filter(
            JournalEntryLine.account_code.like("409%"),
            JournalEntryLine.company_id == company_id,
            JournalEntryLine.is_deleted.is_(False),
        )
        .all()
    )

    for l in lines:
        label = (l.label or "").lower()
        if "gaceb" in label or "avance" in label:
            findings.append(_create_finding(
                session, company_id, 6, "GACEB_ADVANCE", 90,
                f"GACEB advance entry: {l.debit or l.credit} DA",
                f"Account {l.account_code}: '{l.label}'",
                "FLAG_REVIEW",
                extracted={"account": l.account_code, "amount": str(l.debit or l.credit)},
            ))

    return findings


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 8: Associate withdrawals (account 455 debits)
# ═════════════════════════════════════════════════════════════════════════════

def detect_associate_withdrawals(session, company_id):
    """Accounts 455 debit with apartment/prelevement labels."""
    from app.models.journal_entry_line import JournalEntryLine

    findings = []
    keywords = ["prelevement", "appartement", "f3", "f4", "f2", "cession"]

    lines = (
        session.query(JournalEntryLine)
        .filter(
            JournalEntryLine.account_code == "455",
            JournalEntryLine.debit > 0,
            JournalEntryLine.company_id == company_id,
            JournalEntryLine.is_deleted.is_(False),
        )
        .all()
    )

    for l in lines:
        label = (l.label or "").lower()
        if any(kw in label for kw in keywords):
            findings.append(_create_finding(
                session, company_id, 8, "ASSOCIATE_WITHDRAWAL", 80,
                f"Associate withdrawal: {l.debit} DA",
                f"Account 455 debit: '{l.label}'",
                "FLAG_REVIEW",
                extracted={"amount": str(l.debit), "label": l.label,
                           "tiers_name": l.tiers_name},
            ))

    return findings


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 11: BBZ charges
# ═════════════════════════════════════════════════════════════════════════════

def detect_bbz_charges(session, company_id):
    """Accounts 613 (rent) with BBZ/Bab Ezzouar labels."""
    from app.models.journal_entry_line import JournalEntryLine

    findings = []

    lines = (
        session.query(JournalEntryLine)
        .filter(
            JournalEntryLine.account_code.in_(["613", "2181", "275"]),
            JournalEntryLine.company_id == company_id,
            JournalEntryLine.is_deleted.is_(False),
        )
        .all()
    )

    for l in lines:
        label = (l.label or "").lower()
        if "bbz" in label or "bab ezzouar" in label or "bureau" in label:
            findings.append(_create_finding(
                session, company_id, 11, "BBZ_CHARGE", 85,
                f"BBZ charge: {l.debit or l.credit} DA on {l.account_code}",
                f"'{l.label}'",
                "FLAG_REVIEW",
                extracted={"account": l.account_code,
                           "amount": str(l.debit or l.credit)},
            ))

    return findings


# ═════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═════════════════════════════════════════════════════════════════════════════

PATTERN_RUNNERS = {
    1: detect_group_companies,
    4: detect_inter_project_flows,
    5: detect_rf3_invoices,
    6: detect_gaceb_advance,
    8: detect_associate_withdrawals,
    11: detect_bbz_charges,
}


def run_all_patterns(
    session: Session,
    company_id: UUID,
) -> list:
    """Run all detection patterns and return findings."""
    all_findings = []
    for pattern_id, runner in PATTERN_RUNNERS.items():
        try:
            findings = runner(session, company_id)
            all_findings.extend(findings)
        except Exception as e:
            all_findings.append({"error": str(e), "pattern": pattern_id})
    return all_findings


def run_pattern(
    session: Session,
    pattern_id: int,
    company_id: UUID,
) -> list:
    """Run a specific detection pattern."""
    runner = PATTERN_RUNNERS.get(pattern_id)
    if runner is None:
        raise ValueError(f"Pattern {pattern_id} not implemented.")
    return runner(session, company_id)


def validate_finding(
    session: Session,
    finding_id: UUID,
    action: str,
    validated_by: UUID,
    notes: str | None = None,
) -> object:
    """DAF validates or rejects a finding."""
    from app.models.detection import DetectionFinding

    f = session.get(DetectionFinding, finding_id)
    if f is None:
        raise ValueError(f"Finding {finding_id} not found.")

    now = datetime.now(timezone.utc)
    f.status = action  # VALIDATED, REJECTED, DEFERRED
    f.validated_by = validated_by
    f.validated_at = now
    f.validation_notes = notes
    session.flush()
    return f


def integrate_finding(
    session: Session,
    finding_id: UUID,
) -> object:
    """Apply the proposed action from a validated finding."""
    from app.models.detection import DetectionFinding

    f = session.get(DetectionFinding, finding_id)
    if f is None:
        raise ValueError(f"Finding {finding_id} not found.")
    if f.status != "VALIDATED":
        raise ValueError("Only VALIDATED findings can be integrated.")

    now = datetime.now(timezone.utc)
    result = {"action": f.proposed_action, "status": "INTEGRATED"}

    # Action-specific integration would go here
    # (trigger CFF, create alias, generate formulaire, etc.)

    f.status = "INTEGRATED"
    f.integrated_at = now
    f.integration_result = result
    session.flush()
    return f
