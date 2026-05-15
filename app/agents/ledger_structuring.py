"""GFI Platform - LedgerStructuringAgent.

Builds balanced journal proposals linked to evidence anchors.
"""
import uuid
import structlog
from datetime import datetime
from app.schemas.artifacts import (
    WorkflowState, NodeResult, ProposedLedgerPackage,
    ProposedJournalEntry, ProposedJournalLine, EvidenceAnchorSchema,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Generate balanced journal entry proposals from normalized data + matching."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    artifacts_created = []
    errors = []

    # Get normalized entity sets
    norm_ids = state.artifacts.get("normalization", [])
    match_ids = state.artifacts.get("matching", [])

    # Build maps
    norm_data_map: dict[str, dict] = {}
    match_data_map: dict[str, dict] = {}

    for nid in norm_ids:
        result = await ctx.db_session.execute(select(Artifact).where(Artifact.id == nid))
        a = result.scalar_one_or_none()
        if a:
            norm_data_map[a.data.get("doc_id", "")] = a.data

    for mid in match_ids:
        result = await ctx.db_session.execute(select(Artifact).where(Artifact.id == mid))
        a = result.scalar_one_or_none()
        if a:
            match_data_map[a.data.get("doc_id", "")] = a.data

    for doc_id, norm_data in norm_data_map.items():
        try:
            doc_type = norm_data.get("doc_type", "OTHER")
            fields = norm_data.get("fields", [])
            match_data = match_data_map.get(doc_id, {})

            # Build field map
            field_map = {}
            evidence_map = {}
            for f in fields:
                fname = f.get("field_name", "")
                field_map[fname] = f.get("normalized_value") or f.get("original_value")

            # Get evidence anchors from extraction artifacts
            ext_ids = state.artifacts.get("extraction", [])
            for eid in ext_ids:
                result = await ctx.db_session.execute(select(Artifact).where(Artifact.id == eid))
                ea = result.scalar_one_or_none()
                if ea and ea.data.get("doc_id") == doc_id:
                    for ef in ea.data.get("fields", []):
                        if ef.get("evidence_anchor"):
                            evidence_map[ef["field_name"]] = EvidenceAnchorSchema(**ef["evidence_anchor"])

            # Build journal entries based on doc type
            if doc_type == "INVOICE":
                entries = _build_invoice_entries(doc_id, field_map, match_data, evidence_map)
            elif doc_type == "RECEIPT":
                entries = _build_receipt_entries(doc_id, field_map, match_data, evidence_map)
            elif doc_type == "PAYROLL":
                entries = _build_payroll_entries(doc_id, field_map, match_data, evidence_map)
            elif doc_type == "BANK_STATEMENT":
                entries = _build_bank_entries(doc_id, field_map, match_data, evidence_map)
            else:
                entries = _build_generic_entries(doc_id, field_map, match_data, evidence_map)

            # Compute totals and balance check
            total_debit = sum(l.debit for e in entries for l in e.lines)
            total_credit = sum(l.credit for e in entries for l in e.lines)
            is_balanced = abs(total_debit - total_credit) < 0.01

            package = ProposedLedgerPackage(
                doc_id=doc_id,
                entries=entries,
                total_debit=round(total_debit, 2),
                total_credit=round(total_credit, 2),
                is_balanced=is_balanced,
            )

            artifact = Artifact(
                id=uuid.uuid4(),
                tenant_id=state.tenant_id,
                workflow_id=state.workflow_id,
                doc_id=doc_id,
                artifact_type=ArtifactType.PROPOSED_LEDGER_PACKAGE,
                data=package.model_dump(),
                algo_version="v3.0-ledger",
            )
            ctx.db_session.add(artifact)
            artifacts_created.append(str(artifact.id))

            logger.info("ledger_structured", doc_id=doc_id, entries=len(entries),
                        balanced=is_balanced, debit=total_debit, credit=total_credit)

        except Exception as e:
            errors.append({"code": "LEDGER_ERROR", "message": f"Ledger failed for {doc_id}: {str(e)}"})

    await ctx.db_session.flush()

    if errors and not artifacts_created:
        return NodeResult(status="ERROR", artifacts_created=[], warnings=[], errors=errors)

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=errors)


def _safe_decimal(value) -> float:
    """Safely convert to float."""
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0


def _build_invoice_entries(
    doc_id: str, fields: dict, match_data: dict, evidence: dict
) -> list[ProposedJournalEntry]:
    """Build journal entries for a purchase invoice."""
    total_ht = _safe_decimal(fields.get("total_ht", 0))
    total_tva = _safe_decimal(fields.get("total_tva", 0))
    total_ttc = _safe_decimal(fields.get("total_ttc", 0))

    # Use TTC if available, else compute
    if total_ttc == 0 and total_ht > 0:
        total_ttc = total_ht + total_tva

    # Get account codes from matching
    accounts = _get_matched_accounts(match_data)
    expense_acc = accounts.get("expense_account", "6111")
    vat_acc = accounts.get("vat_account", "3455")
    supplier_acc = accounts.get("supplier_account", "4411")

    invoice_ref = fields.get("invoice_number", "")
    invoice_date = fields.get("invoice_date", datetime.utcnow().strftime("%Y-%m-%d"))

    lines = []
    assumptions = []

    # Debit: Expense
    if total_ht > 0:
        lines.append(ProposedJournalLine(
            account_code=expense_acc,
            label=f"Achat - Facture {invoice_ref}",
            debit=round(total_ht, 2),
            credit=0.0,
            evidence_anchors=[evidence["total_ht"]] if "total_ht" in evidence else [],
        ))

    # Debit: VAT recoverable
    if total_tva > 0:
        lines.append(ProposedJournalLine(
            account_code=vat_acc,
            label=f"TVA récupérable - Facture {invoice_ref}",
            debit=round(total_tva, 2),
            credit=0.0,
            evidence_anchors=[evidence["total_tva"]] if "total_tva" in evidence else [],
        ))

    # Credit: Supplier
    if total_ttc > 0:
        lines.append(ProposedJournalLine(
            account_code=supplier_acc,
            label=f"Fournisseur - Facture {invoice_ref}",
            debit=0.0,
            credit=round(total_ttc, 2),
            evidence_anchors=[evidence["total_ttc"]] if "total_ttc" in evidence else [],
        ))
    else:
        assumptions.append("TTC computed from HT+TVA, no direct source")

    supplier_name = fields.get("supplier_name", "Fournisseur")

    return [ProposedJournalEntry(
        entry_date=invoice_date,
        reference=invoice_ref,
        description=f"Facture {invoice_ref} - {supplier_name}",
        lines=lines,
        assumptions=assumptions,
    )]


def _build_receipt_entries(
    doc_id: str, fields: dict, match_data: dict, evidence: dict
) -> list[ProposedJournalEntry]:
    """Build journal entries for a receipt."""
    total = _safe_decimal(fields.get("total_amount", 0))
    accounts = _get_matched_accounts(match_data)
    expense_acc = accounts.get("expense_account", "6125")
    cash_acc = accounts.get("cash_account", "5161")

    date = fields.get("receipt_date", datetime.utcnow().strftime("%Y-%m-%d"))

    return [ProposedJournalEntry(
        entry_date=date,
        description=f"Reçu - {fields.get('vendor_name', 'Vendeur')}",
        lines=[
            ProposedJournalLine(
                account_code=expense_acc, label="Achat divers",
                debit=round(total, 2), credit=0.0,
                evidence_anchors=[evidence["total_amount"]] if "total_amount" in evidence else [],
            ),
            ProposedJournalLine(
                account_code=cash_acc, label="Caisse",
                debit=0.0, credit=round(total, 2),
                evidence_anchors=[evidence["total_amount"]] if "total_amount" in evidence else [],
            ),
        ],
    )]


def _build_payroll_entries(
    doc_id: str, fields: dict, match_data: dict, evidence: dict
) -> list[ProposedJournalEntry]:
    """Build journal entries for payroll."""
    gross = _safe_decimal(fields.get("gross_salary", 0))
    net = _safe_decimal(fields.get("net_salary", 0))
    deductions = gross - net if gross > net else 0

    accounts = _get_matched_accounts(match_data)
    salary_acc = accounts.get("salary_account", "6171")
    social_acc = accounts.get("social_charges", "6174")
    payable_acc = accounts.get("net_payable", "4432")

    date = fields.get("period", datetime.utcnow().strftime("%Y-%m-%d"))

    return [ProposedJournalEntry(
        entry_date=date,
        description=f"Paie - {fields.get('employee_name', 'Employé')}",
        lines=[
            ProposedJournalLine(
                account_code=salary_acc, label="Salaire brut",
                debit=round(gross, 2), credit=0.0,
                evidence_anchors=[evidence["gross_salary"]] if "gross_salary" in evidence else [],
            ),
            ProposedJournalLine(
                account_code=social_acc, label="Retenues",
                debit=0.0, credit=round(deductions, 2),
            ),
            ProposedJournalLine(
                account_code=payable_acc, label="Net à payer",
                debit=0.0, credit=round(net, 2),
                evidence_anchors=[evidence["net_salary"]] if "net_salary" in evidence else [],
            ),
        ],
    )]


def _build_bank_entries(
    doc_id: str, fields: dict, match_data: dict, evidence: dict
) -> list[ProposedJournalEntry]:
    """Build entries for bank statement (placeholder)."""
    return [ProposedJournalEntry(
        entry_date=fields.get("statement_date", datetime.utcnow().strftime("%Y-%m-%d")),
        description="Relevé bancaire",
        lines=[],
        assumptions=["Bank statement entries require transaction-level detail"],
    )]


def _build_generic_entries(
    doc_id: str, fields: dict, match_data: dict, evidence: dict
) -> list[ProposedJournalEntry]:
    """Build generic entries for unclassified documents."""
    return [ProposedJournalEntry(
        entry_date=datetime.utcnow().strftime("%Y-%m-%d"),
        description="Document non classifié - écriture en attente",
        lines=[],
        assumptions=["Document type not recognized; manual classification required"],
    )]


def _get_matched_accounts(match_data: dict) -> dict[str, str]:
    """Extract matched account codes from matching package."""
    accounts = {}
    for match in match_data.get("matches", []):
        if match.get("entity_type") == "account":
            accounts[match["field_name"]] = match["extracted_value"]
    return accounts
