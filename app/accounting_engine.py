"""
GFI v7.0 — Accounting Engine: auto-generation of journal entries.

Rule R-002: 100% of entries are auto-generated from source documents.
Manual entry is REJECTED. Exception: OD with uploaded justification.

This module is the RECEPTOR of all financial flows — it does not create
information, it receives it from other modules and structures it into
SCF-compliant journal entries.

Core API:
  generate_entry(source_type, source_data, ...) -> JournalEntry
  get_next_entry_number(company_id, journal_code, year) -> str
  validate_entry_balance(entry_id) -> bool
  prepare_g50(company_id, period) -> FiscalDeclaration
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class ManualEntryForbidden(Exception):
    """Raised when a user tries to create a manual journal entry (R-002)."""

    pass


class EntryBalanceError(Exception):
    """Raised when debit != credit in a journal entry."""

    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── Source document types that auto-generate entries ─────────────────────────
SOURCE_TYPES = {
    "PURCHASE_INVOICE_RF1",
    "SALES_INVOICE_RF1",
    "SUPPLIER_PAYMENT",
    "CLIENT_COLLECTION",
    "RF3_FICTITIOUS_INVOICE",
    "EXPENSE_REPORT",
    "PAYROLL",
    "WORK_SITUATION",
    "CCA_MOVEMENT",
    "INTER_PROJECT_FLOW",
    "GACEB_ADVANCE",
    "VEHICLE_CESSION",
    "CFF_CALCULATION",
    "OD_MANUAL",
}

# ── Journal code mapping by source type ──────────────────────────────────────
SOURCE_TO_JOURNAL = {
    "PURCHASE_INVOICE_RF1": "HA",
    "SALES_INVOICE_RF1": "VT",
    "SUPPLIER_PAYMENT": "BQ",
    "CLIENT_COLLECTION": "BQ",
    "RF3_FICTITIOUS_INVOICE": "VT",
    "EXPENSE_REPORT": "OD",
    "PAYROLL": "OD",
    "WORK_SITUATION": "HA",
    "CCA_MOVEMENT": "OD",
    "INTER_PROJECT_FLOW": "OD",
    "GACEB_ADVANCE": "OD",
    "VEHICLE_CESSION": "OD",
    "CFF_CALCULATION": "OD",
    "OD_MANUAL": "OD",
}

# ── RF type mapping ──────────────────────────────────────────────────────────
SOURCE_TO_RF = {
    "PURCHASE_INVOICE_RF1": "RF1",
    "SALES_INVOICE_RF1": "RF1",
    "SUPPLIER_PAYMENT": "RF1",
    "CLIENT_COLLECTION": "RF1",
    "RF3_FICTITIOUS_INVOICE": "RF3",
    "EXPENSE_REPORT": "RF1",
    "PAYROLL": "RF1",
    "WORK_SITUATION": "RF1",
    "CCA_MOVEMENT": "RF1",
    "INTER_PROJECT_FLOW": "RF1",
    "GACEB_ADVANCE": "RF1",
    "VEHICLE_CESSION": "RF1",
    "CFF_CALCULATION": "RF3",
}


def get_next_entry_number(
    session: Session,
    company_id: UUID,
    journal_code: str,
    fiscal_year: int,
) -> str:
    """
    Generate the next sequential entry number for a journal.
    Format: {journal_code}-{year}-{seq:04d}
    Strictly cloisoned by company_id + journal_code + year.
    """
    from app.models.journal_sequence import JournalSequence

    seq = (
        session.query(JournalSequence)
        .filter(
            JournalSequence.company_id == company_id,
            JournalSequence.journal_code == journal_code,
            JournalSequence.fiscal_year == fiscal_year,
            JournalSequence.is_deleted.is_(False),
        )
        .with_for_update()
        .first()
    )

    if seq is None:
        seq = JournalSequence(
            company_id=company_id,
            journal_code=journal_code,
            fiscal_year=fiscal_year,
            last_number=0,
        )
        session.add(seq)
        session.flush()

    seq.last_number += 1
    next_num = seq.last_number
    session.flush()

    return f"{journal_code}-{fiscal_year}-{next_num:04d}"


def _get_or_create_journal(
    session: Session,
    company_id: UUID,
    journal_code: str,
) -> object:
    """Get or auto-create a journal for the given company."""
    from app.models.journal import Journal

    journal = (
        session.query(Journal)
        .filter(
            Journal.company_id == company_id,
            Journal.code == journal_code,
            Journal.is_deleted.is_(False),
        )
        .first()
    )

    if journal is None:
        journal_names = {
            "HA": ("Journal des Achats", "ACHAT"),
            "VT": ("Journal des Ventes", "VENTE"),
            "BQ": ("Journal de Banque", "BANQUE"),
            "CA": ("Journal de Caisse", "CAISSE"),
            "OD": ("Journal des OD", "OD"),
        }
        name, jtype = journal_names.get(journal_code, (journal_code, "OD"))
        journal = Journal(
            company_id=company_id,
            code=journal_code,
            name=name,
            journal_type=jtype,
        )
        session.add(journal)
        session.flush()

    return journal


def _resolve_account(session: Session, account_code: str) -> object:
    """Look up an account by its SCF code."""
    from app.models.account import Account

    account = (
        session.query(Account)
        .filter(
            Account.code == account_code,
            Account.is_deleted.is_(False),
        )
        .first()
    )
    if account is None:
        raise ValueError(f"SCF account '{account_code}' not found.")
    return account


def generate_entry(
    session: Session,
    *,
    source_type: str,
    source_id: UUID | None,
    company_id: UUID,
    entry_date: date,
    label: str,
    lines: list[dict],
    project_id: UUID | None = None,
    rf_type: str | None = None,
    od_justification_path: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Generate a journal entry from a source document.

    Args:
        source_type: one of SOURCE_TYPES
        source_id: UUID of the source document
        company_id: entity this entry belongs to
        entry_date: accounting date
        label: entry description
        lines: list of dicts with keys:
            account_code, debit, credit, label (optional),
            tiers_type (optional), tiers_id (optional), tiers_name (optional)
        project_id: optional project link
        rf_type: override RF type (default: derived from source_type)
        od_justification_path: required for OD_MANUAL
        created_by: user who triggered the generation

    Returns:
        JournalEntry with lines attached.

    Raises:
        ManualEntryForbidden: if source_type is invalid
        EntryBalanceError: if debits != credits
    """
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine

    # ── R-002: Reject manual entries ─────────────────────────────────────
    if source_type not in SOURCE_TYPES:
        raise ManualEntryForbidden(
            "Ecriture manuelle interdite. Toute ecriture doit provenir "
            "d'une piece justificative."
        )

    if source_type == "OD_MANUAL" and not od_justification_path:
        raise ManualEntryForbidden(
            "Ecriture OD manuelle : piece justificative obligatoire."
        )

    if source_type != "OD_MANUAL" and source_id is None:
        raise ManualEntryForbidden(
            "Ecriture manuelle interdite. Toute ecriture doit provenir "
            "d'une piece justificative."
        )

    # ── Determine journal and RF type ────────────────────────────────────
    journal_code = SOURCE_TO_JOURNAL[source_type]
    if rf_type is None:
        rf_type = SOURCE_TO_RF.get(source_type, "RF1")

    journal = _get_or_create_journal(session, company_id, journal_code)
    fiscal_year = entry_date.year

    # ── Generate entry number ────────────────────────────────────────────
    entry_number = get_next_entry_number(
        session, company_id, journal_code, fiscal_year
    )

    # ── Validate balance ─────────────────────────────────────────────────
    total_debit = sum(Decimal(str(l.get("debit", 0))) for l in lines)
    total_credit = sum(Decimal(str(l.get("credit", 0))) for l in lines)

    if _r2(total_debit) != _r2(total_credit):
        raise EntryBalanceError(
            f"Debit ({total_debit}) != Credit ({total_credit}) "
            f"in entry {entry_number}."
        )

    # ── Create entry ─────────────────────────────────────────────────────
    entry = JournalEntry(
        company_id=company_id,
        journal_id=journal.id,
        entry_number=entry_number,
        entry_date=entry_date,
        fiscal_year=str(fiscal_year),
        label=label,
        rf_type=rf_type,
        source_document_type=source_type,
        source_document_id=source_id,
        od_justification_path=od_justification_path,
        status="DRAFT",
        total_debit=_r2(total_debit),
        total_credit=_r2(total_credit),
        project_id=project_id,
        created_by=created_by,
    )
    session.add(entry)
    session.flush()

    # ── Create lines ─────────────────────────────────────────────────────
    for i, line_data in enumerate(lines, start=1):
        account = _resolve_account(session, line_data["account_code"])
        line = JournalEntryLine(
            company_id=company_id,
            entry_id=entry.id,
            account_id=account.id,
            account_code=line_data["account_code"],
            debit=Decimal(str(line_data.get("debit", 0))),
            credit=Decimal(str(line_data.get("credit", 0))),
            label=line_data.get("label"),
            tiers_type=line_data.get("tiers_type"),
            tiers_id=line_data.get("tiers_id"),
            tiers_name=line_data.get("tiers_name"),
            line_number=i,
            created_by=created_by,
        )
        session.add(line)

    session.flush()
    return entry


# ═════════════════════════════════════════════════════════════════════════════
# AUTO-GENERATION TEMPLATES
# ═════════════════════════════════════════════════════════════════════════════

def generate_purchase_invoice_entry(
    session: Session,
    *,
    company_id: UUID,
    invoice_id: UUID,
    entry_date: date,
    supplier_name: str,
    expense_account: str,
    amount_ht: Decimal,
    tva_amount: Decimal,
    total_ttc: Decimal,
    project_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """Purchase invoice (RF1): D 6xx + D 4456 / C 401"""
    return generate_entry(
        session,
        source_type="PURCHASE_INVOICE_RF1",
        source_id=invoice_id,
        company_id=company_id,
        entry_date=entry_date,
        label=f"Facture achat {supplier_name}",
        project_id=project_id,
        created_by=created_by,
        lines=[
            {"account_code": expense_account, "debit": amount_ht, "credit": 0,
             "label": f"Achat {supplier_name}"},
            {"account_code": "4456", "debit": tva_amount, "credit": 0,
             "label": "TVA deductible"},
            {"account_code": "401", "debit": 0, "credit": total_ttc,
             "label": supplier_name,
             "tiers_type": "FOURNISSEUR", "tiers_name": supplier_name},
        ],
    )


def generate_sales_invoice_entry(
    session: Session,
    *,
    company_id: UUID,
    invoice_id: UUID,
    entry_date: date,
    client_name: str,
    revenue_account: str,
    amount_ht: Decimal,
    tva_amount: Decimal,
    total_ttc: Decimal,
    project_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """Sales invoice (RF1): D 411 / C 70x + C 4457"""
    return generate_entry(
        session,
        source_type="SALES_INVOICE_RF1",
        source_id=invoice_id,
        company_id=company_id,
        entry_date=entry_date,
        label=f"Facture vente {client_name}",
        project_id=project_id,
        created_by=created_by,
        lines=[
            {"account_code": "411", "debit": total_ttc, "credit": 0,
             "label": client_name,
             "tiers_type": "CLIENT", "tiers_name": client_name},
            {"account_code": revenue_account, "debit": 0, "credit": amount_ht,
             "label": f"Vente {client_name}"},
            {"account_code": "4457", "debit": 0, "credit": tva_amount,
             "label": "TVA collectee"},
        ],
    )


def generate_rf3_invoice_entry(
    session: Session,
    *,
    company_id: UUID,
    invoice_id: UUID,
    entry_date: date,
    counterparty_name: str,
    amount_ht: Decimal,
    tva_amount: Decimal,
    total_ttc: Decimal,
    project_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """RF3 fictitious invoice: D 411 interco / C 70x + C 4457. Auto-triggers CFF."""
    return generate_entry(
        session,
        source_type="RF3_FICTITIOUS_INVOICE",
        source_id=invoice_id,
        company_id=company_id,
        entry_date=entry_date,
        label=f"Facture RF3 {counterparty_name}",
        rf_type="RF3",
        project_id=project_id,
        created_by=created_by,
        lines=[
            {"account_code": "411", "debit": total_ttc, "credit": 0,
             "label": f"Interco {counterparty_name}",
             "tiers_type": "CLIENT", "tiers_name": counterparty_name},
            {"account_code": "701", "debit": 0, "credit": amount_ht,
             "label": f"Revenue RF3 {counterparty_name}"},
            {"account_code": "4457", "debit": 0, "credit": tva_amount,
             "label": "TVA collectee RF3"},
        ],
    )


def generate_supplier_payment_entry(
    session: Session,
    *,
    company_id: UUID,
    payment_id: UUID,
    entry_date: date,
    supplier_name: str,
    amount: Decimal,
    created_by: UUID | None = None,
) -> object:
    """Supplier payment: D 401 / C 512"""
    return generate_entry(
        session,
        source_type="SUPPLIER_PAYMENT",
        source_id=payment_id,
        company_id=company_id,
        entry_date=entry_date,
        label=f"Reglement {supplier_name}",
        created_by=created_by,
        lines=[
            {"account_code": "401", "debit": amount, "credit": 0,
             "label": supplier_name,
             "tiers_type": "FOURNISSEUR", "tiers_name": supplier_name},
            {"account_code": "512", "debit": 0, "credit": amount,
             "label": f"Paiement {supplier_name}"},
        ],
    )


def generate_client_collection_entry(
    session: Session,
    *,
    company_id: UUID,
    collection_id: UUID,
    entry_date: date,
    client_name: str,
    amount: Decimal,
    created_by: UUID | None = None,
) -> object:
    """Client collection: D 512 / C 411"""
    return generate_entry(
        session,
        source_type="CLIENT_COLLECTION",
        source_id=collection_id,
        company_id=company_id,
        entry_date=entry_date,
        label=f"Encaissement {client_name}",
        created_by=created_by,
        lines=[
            {"account_code": "512", "debit": amount, "credit": 0,
             "label": f"Encaissement {client_name}"},
            {"account_code": "411", "debit": 0, "credit": amount,
             "label": client_name,
             "tiers_type": "CLIENT", "tiers_name": client_name},
        ],
    )


def generate_payroll_entry(
    session: Session,
    *,
    company_id: UUID,
    payroll_id: UUID,
    entry_date: date,
    period_label: str,
    gross_salary: Decimal,
    employer_contributions: Decimal,
    net_salary: Decimal,
    social_security: Decimal,
    irg: Decimal,
    created_by: UUID | None = None,
) -> object:
    """Payroll: D 631 + D 635 / C 421 + C 431 + C 442"""
    return generate_entry(
        session,
        source_type="PAYROLL",
        source_id=payroll_id,
        company_id=company_id,
        entry_date=entry_date,
        label=f"Paie {period_label}",
        created_by=created_by,
        lines=[
            {"account_code": "631", "debit": gross_salary, "credit": 0,
             "label": f"Remunerations {period_label}"},
            {"account_code": "635", "debit": employer_contributions, "credit": 0,
             "label": f"Cotisations patronales {period_label}"},
            {"account_code": "421", "debit": 0, "credit": net_salary,
             "label": f"Salaires a payer {period_label}"},
            {"account_code": "431", "debit": 0, "credit": social_security,
             "label": f"Securite sociale {period_label}"},
            {"account_code": "442", "debit": 0, "credit": irg,
             "label": f"IRG a payer {period_label}"},
        ],
    )


def generate_cca_movement_entry(
    session: Session,
    *,
    company_id: UUID,
    movement_id: UUID,
    entry_date: date,
    associate_name: str,
    amount: Decimal,
    direction: str,
    created_by: UUID | None = None,
) -> object:
    """CCA movement: D/C 455 / C/D 512"""
    if direction == "CREDIT":
        # Associate lends to company
        lines = [
            {"account_code": "512", "debit": amount, "credit": 0},
            {"account_code": "455", "debit": 0, "credit": amount,
             "label": f"CCA {associate_name}",
             "tiers_type": "ASSOCIE", "tiers_name": associate_name},
        ]
    else:
        # Company reimburses associate
        lines = [
            {"account_code": "455", "debit": amount, "credit": 0,
             "label": f"Remboursement CCA {associate_name}",
             "tiers_type": "ASSOCIE", "tiers_name": associate_name},
            {"account_code": "512", "debit": 0, "credit": amount},
        ]
    return generate_entry(
        session,
        source_type="CCA_MOVEMENT",
        source_id=movement_id,
        company_id=company_id,
        entry_date=entry_date,
        label=f"CCA {associate_name} — {direction}",
        created_by=created_by,
        lines=lines,
    )


# ═════════════════════════════════════════════════════════════════════════════
# G50 PREPARATION
# ═════════════════════════════════════════════════════════════════════════════

def prepare_g50(
    session: Session,
    *,
    company_id: UUID,
    period_start: date,
    period_end: date,
    created_by: UUID | None = None,
) -> object:
    """
    Auto-prepare the G50 monthly declaration from validated entries.
    Calculates TVA a decaisser, TAP, and IBS installment.

    If IBS or TAP rate is missing -> generates FC-005 and raises.
    """
    from app.models.company import Company
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.fiscal_declaration import FiscalDeclaration
    from app.formulaire_engine import generate_if_not_exists
    from app.cff_engine import CffCalculationError

    company = session.get(Company, company_id)
    if company is None:
        raise ValueError(f"Company {company_id} not found.")

    if company.ibs_rate is None or company.tap_rate is None:
        generate_if_not_exists(
            session,
            code="FC-005",
            company_id=company_id,
            context={"entite": company.legal_name},
            blocked_resource_type="fiscal_declaration",
        )
        raise CffCalculationError(
            f"Tax rates missing for {company.code}. FC-005 generated."
        )

    # Sum TVA collected (credit on 4457) for the period
    tva_collected = (
        session.query(__import__("sqlalchemy").func.coalesce(
            __import__("sqlalchemy").func.sum(JournalEntryLine.credit), 0
        ))
        .join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id)
        .filter(
            JournalEntry.company_id == company_id,
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date <= period_end,
            JournalEntry.status.in_(["VALIDATED", "POSTED"]),
            JournalEntry.is_deleted.is_(False),
            JournalEntryLine.account_code == "4457",
            JournalEntryLine.is_deleted.is_(False),
        )
        .scalar()
    ) or Decimal("0")

    # Sum TVA deductible (debit on 4456)
    tva_deductible = (
        session.query(__import__("sqlalchemy").func.coalesce(
            __import__("sqlalchemy").func.sum(JournalEntryLine.debit), 0
        ))
        .join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id)
        .filter(
            JournalEntry.company_id == company_id,
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date <= period_end,
            JournalEntry.status.in_(["VALIDATED", "POSTED"]),
            JournalEntry.is_deleted.is_(False),
            JournalEntryLine.account_code == "4456",
            JournalEntryLine.is_deleted.is_(False),
        )
        .scalar()
    ) or Decimal("0")

    tva_a_decaisser = Decimal(str(tva_collected)) - Decimal(str(tva_deductible))

    # Sum revenue (credit on 70x accounts) for TAP
    from sqlalchemy import func as sqfunc
    revenue = (
        session.query(sqfunc.coalesce(
            sqfunc.sum(JournalEntryLine.credit), 0
        ))
        .join(JournalEntry, JournalEntryLine.entry_id == JournalEntry.id)
        .filter(
            JournalEntry.company_id == company_id,
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date <= period_end,
            JournalEntry.status.in_(["VALIDATED", "POSTED"]),
            JournalEntry.is_deleted.is_(False),
            JournalEntryLine.account_code.like("70%"),
            JournalEntryLine.is_deleted.is_(False),
        )
        .scalar()
    ) or Decimal("0")

    tap_amount = _r2(
        Decimal(str(revenue)) * Decimal(str(company.tap_rate)) / Decimal("100")
    )

    # IBS installment = revenue * IBS rate / 100 / 4 (quarterly approximation)
    ibs_installment = _r2(
        Decimal(str(revenue)) * Decimal(str(company.ibs_rate)) / Decimal("100")
    )

    declaration = FiscalDeclaration(
        company_id=company_id,
        declaration_type="G50",
        period_start=period_start,
        period_end=period_end,
        fiscal_year=str(period_start.year),
        status="PREPARED",
        tva_collected=tva_collected,
        tva_deductible=tva_deductible,
        tva_a_decaisser=tva_a_decaisser,
        tap_amount=tap_amount,
        ibs_installment=ibs_installment,
        computed_data={
            "revenue": str(revenue),
            "tva_collected": str(tva_collected),
            "tva_deductible": str(tva_deductible),
            "tva_a_decaisser": str(tva_a_decaisser),
            "tap_amount": str(tap_amount),
            "ibs_installment": str(ibs_installment),
        },
        created_by=created_by,
    )
    session.add(declaration)
    session.flush()
    return declaration
