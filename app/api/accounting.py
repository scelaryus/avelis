"""GFI Platform - Accounting API router."""
import csv
import io
import uuid
from datetime import datetime, date as date_type
from typing import Optional
from decimal import Decimal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status, Header
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.core import (
    User, ChartOfAccount, AccountingPeriod, JournalEntry, JournalLine,
    JournalEntryStatus, AuditLog, Document,
)
from app.models.financial import Entreprise, Projet
from app.auth.dependencies import get_current_user, require_role
from app.schemas.api import (
    COACreate, COAResponse,
    PeriodCreate, PeriodResponse,
    JournalEntryResponse, JournalEntryListResponse,
    JournalEntryCreate,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Accounting"])


# ── Companies & Projects Registry ───────────────────────────────────

@router.get("/entreprises")
async def list_entreprises(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tenant companies for the registry screens."""
    result = await db.execute(
        select(Entreprise)
        .where(Entreprise.tenant_id == user.tenant_id)
        .order_by(Entreprise.raison_sociale)
    )
    return [
        {
            "id": entreprise.id,
            "raison_sociale": entreprise.raison_sociale,
            "devise": entreprise.devise,
            "nif": entreprise.nif,
            "rc": entreprise.rc,
            "adresse": entreprise.adresse,
            "telephone": entreprise.telephone,
            "email": entreprise.email,
            "is_active": entreprise.is_active,
        }
        for entreprise in result.scalars().all()
    ]


@router.get("/projets")
async def list_projets(
    entreprise_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tenant projects for the registry screens."""
    query = select(Projet).where(Projet.tenant_id == user.tenant_id)
    if entreprise_id:
        query = query.where(Projet.entreprise_id == entreprise_id)

    result = await db.execute(query.order_by(Projet.code))
    return [
        {
            "id": projet.id,
            "entreprise_id": projet.entreprise_id,
            "code": projet.code,
            "nom": projet.nom,
            "statut": projet.statut.value if projet.statut else None,
            "adresse": projet.adresse,
            "budget_previsionnel": float(projet.budget_previsionnel or 0),
            "is_active": projet.is_active,
        }
        for projet in result.scalars().all()
    ]


# ── Chart of Accounts ──────────────────────────────────────────────

@router.post("/coa", response_model=COAResponse, status_code=status.HTTP_201_CREATED)
async def create_coa_entry(
    body: COACreate,
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Create a Chart of Account entry."""
    coa = ChartOfAccount(
        tenant_id=user.tenant_id,
        code=body.code,
        label=body.label,
        account_type=body.account_type,
        parent_code=body.parent_code,
    )
    db.add(coa)
    await db.commit()
    await db.refresh(coa)
    return COAResponse(
        id=coa.id, code=coa.code, label=coa.label,
        account_type=coa.account_type, parent_code=coa.parent_code,
    )


@router.get("/coa", response_model=list[COAResponse])
async def list_coa(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List Chart of Accounts for tenant."""
    result = await db.execute(
        select(ChartOfAccount)
        .where(ChartOfAccount.tenant_id == user.tenant_id)
        .order_by(ChartOfAccount.code)
    )
    accounts = result.scalars().all()
    return [
        COAResponse(id=a.id, code=a.code, label=a.label, account_type=a.account_type, parent_code=a.parent_code)
        for a in accounts
    ]


@router.put("/coa/{coa_id}", response_model=COAResponse)
async def update_coa_entry(
    coa_id: str,
    body: COACreate,
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Update a COA entry."""
    result = await db.execute(
        select(ChartOfAccount).where(ChartOfAccount.id == coa_id, ChartOfAccount.tenant_id == user.tenant_id)
    )
    coa = result.scalar_one_or_none()
    if coa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    coa.code = body.code
    coa.label = body.label
    coa.account_type = body.account_type
    coa.parent_code = body.parent_code
    await db.commit()
    await db.refresh(coa)
    return COAResponse(id=coa.id, code=coa.code, label=coa.label, account_type=coa.account_type, parent_code=coa.parent_code)


@router.delete("/coa/{coa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coa_entry(
    coa_id: str,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Delete a COA entry."""
    result = await db.execute(
        select(ChartOfAccount).where(ChartOfAccount.id == coa_id, ChartOfAccount.tenant_id == user.tenant_id)
    )
    coa = result.scalar_one_or_none()
    if coa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    await db.delete(coa)
    await db.commit()


# ── Accounting Periods ──────────────────────────────────────────────

@router.post("/periods", response_model=PeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_period(
    body: PeriodCreate,
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Create an accounting period."""
    period = AccountingPeriod(
        tenant_id=user.tenant_id,
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        is_closed=False,
    )
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return PeriodResponse(
        id=period.id, name=period.name,
        start_date=period.start_date, end_date=period.end_date,
        is_closed=period.is_closed,
    )


@router.get("/periods", response_model=list[PeriodResponse])
async def list_periods(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List accounting periods."""
    result = await db.execute(
        select(AccountingPeriod)
        .where(AccountingPeriod.tenant_id == user.tenant_id)
        .order_by(AccountingPeriod.start_date.desc())
    )
    periods = result.scalars().all()
    return [
        PeriodResponse(id=p.id, name=p.name, start_date=p.start_date, end_date=p.end_date, is_closed=p.is_closed)
        for p in periods
    ]


@router.post("/periods/{period_id}/close")
async def close_period(
    period_id: str,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Close an accounting period."""
    result = await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == user.tenant_id)
    )
    period = result.scalar_one_or_none()
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    period.is_closed = True
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="period_close",
        entity_type="accounting_period",
        entity_id=str(period_id),
    ))
    await db.commit()
    return {"status": "closed", "period_id": str(period_id)}


# ── Journal Entries ─────────────────────────────────────────────────

@router.get("/journal-entries", response_model=JournalEntryListResponse)
async def list_journal_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    period_id: Optional[uuid.UUID] = Query(None),
    x_entreprise_id: Optional[str] = Header(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List journal entries — scoped to active entreprise."""
    from fastapi import Header as _H
    base = select(JournalEntry).where(JournalEntry.tenant_id == user.tenant_id)
    count_base = select(func.count()).select_from(JournalEntry).where(JournalEntry.tenant_id == user.tenant_id)

    ent_id = x_entreprise_id or getattr(user, "_active_entreprise_id", None)
    if ent_id:
        base = base.where(JournalEntry.entreprise_id == ent_id)
        count_base = count_base.where(JournalEntry.entreprise_id == ent_id)

    if status_filter:
        try:
            s = JournalEntryStatus(status_filter)
            base = base.where(JournalEntry.status == s)
            count_base = count_base.where(JournalEntry.status == s)
        except ValueError:
            pass

    if period_id:
        base = base.where(JournalEntry.period_id == period_id)
        count_base = count_base.where(JournalEntry.period_id == period_id)

    total = (await db.execute(count_base)).scalar()
    result = await db.execute(
        base.order_by(JournalEntry.entry_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    entries = result.scalars().all()

    items = []
    for e in entries:
        # load lines
        lines_result = await db.execute(
            select(JournalLine).where(JournalLine.entry_id == e.id).order_by(JournalLine.line_no)
        )
        lines = lines_result.scalars().all()
        items.append(
            JournalEntryResponse(
                id=e.id,
                workflow_id=e.workflow_id,
                entry_date=e.entry_date,
                reference=e.reference,
                description=e.description,
                status=e.status.value,
                source_doc_ids=e.source_doc_ids or [],
                lines=[
                    {
                        "id": str(l.id),
                        "line_no": l.line_no,
                        "account_code": l.account_code,
                        "label": l.label,
                        "debit": float(l.debit),
                        "credit": float(l.credit),
                    }
                    for l in lines
                ],
            )
        )

    return JournalEntryListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/journal-entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    body: JournalEntryCreate,
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Create a manual journal entry (comptable uploads journal).

    Lines must balance (total debit == total credit).
    Optionally cross-reference to uploaded documents via source_doc_ids.
    """
    # Validate debit/credit balance
    total_debit = sum(l.debit for l in body.lines)
    total_credit = sum(l.credit for l in body.lines)
    if abs(total_debit - total_credit) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"L'écriture n'est pas équilibrée: débit={total_debit:.2f}, crédit={total_credit:.2f}",
        )

    # Validate source_doc_ids exist and belong to the tenant
    if body.source_doc_ids:
        for did in body.source_doc_ids:
            result = await db.execute(
                select(Document).where(Document.id == did, Document.tenant_id == user.tenant_id)
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Document justificatif introuvable: {did}",
                )

    # Validate period is not closed (KT-04)
    if body.period_id:
        period_result = await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.id == body.period_id,
                AccountingPeriod.tenant_id == user.tenant_id,
            )
        )
        period = period_result.scalar_one_or_none()
        if period and period.is_closed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Impossible de créer une écriture dans une période clôturée (KT-04)",
            )

    # Create journal entry
    entry = JournalEntry(
        tenant_id=user.tenant_id,
        entreprise_id=getattr(body, "entreprise_id", None),
        journal_id=getattr(body, "journal_id", None),
        entry_date=datetime.combine(body.entry_date, datetime.min.time()),
        reference=body.reference,
        description=body.description,
        status=JournalEntryStatus.PROPOSED,
        period_id=getattr(body, "period_id", None),
        realite_financiere=getattr(body, "realite_financiere", None),
        source_doc_ids=body.source_doc_ids,
    )
    db.add(entry)
    await db.flush()

    # Create lines
    lines_out = []
    for i, line in enumerate(body.lines, 1):
        jl = JournalLine(
            entry_id=entry.id,
            line_no=i,
            account_code=line.account_code,
            label=line.label,
            debit=Decimal(str(line.debit)),
            credit=Decimal(str(line.credit)),
            currency="DZD",
            cost_center_code=line.cost_center_code,
            project_code=line.project_code,
        )
        db.add(jl)
        lines_out.append(jl)

    await db.flush()

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="journal_entry_create",
        entity_type="journal_entry",
        entity_id=str(entry.id),
        new_value={
            "reference": body.reference,
            "description": body.description,
            "source_doc_ids": body.source_doc_ids,
            "total_debit": total_debit,
            "lines_count": len(body.lines),
        },
    ))
    await db.commit()

    return JournalEntryResponse(
        id=entry.id,
        entry_date=entry.entry_date,
        reference=entry.reference,
        description=entry.description,
        status=entry.status.value,
        source_doc_ids=entry.source_doc_ids or [],
        lines=[
            {
                "id": str(l.id),
                "line_no": l.line_no,
                "account_code": l.account_code,
                "label": l.label,
                "debit": float(l.debit),
                "credit": float(l.credit),
            }
            for l in lines_out
        ],
    )


@router.get("/journal-entries/unmatched")
async def list_unmatched_entries(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List journal entries that have no linked justification documents."""
    result = await db.execute(
        select(JournalEntry).where(
            JournalEntry.tenant_id == user.tenant_id,
        ).order_by(JournalEntry.entry_date.desc())
    )
    entries = result.scalars().all()

    unmatched = []
    matched = []
    for e in entries:
        has_docs = e.source_doc_ids and len(e.source_doc_ids) > 0

        # Load lines to get total
        lines_result = await db.execute(
            select(JournalLine).where(JournalLine.entry_id == e.id)
        )
        lines = lines_result.scalars().all()
        total_debit = sum(float(l.debit or 0) for l in lines)

        entry_info = {
            "id": str(e.id),
            "entry_date": e.entry_date.strftime("%Y-%m-%d") if e.entry_date else None,
            "reference": e.reference,
            "description": e.description,
            "status": e.status.value,
            "total_debit": round(total_debit, 2),
            "source_doc_count": len(e.source_doc_ids) if e.source_doc_ids else 0,
        }

        if has_docs:
            matched.append(entry_info)
        else:
            unmatched.append(entry_info)

    return {
        "total_entries": len(entries),
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "unmatched_entries": unmatched,
        "matched_entries": matched,
    }


@router.post("/journal-entries/rematch")
async def rematch_entries(
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Re-run AI matching for all unmatched journal entries."""
    result = await db.execute(
        select(JournalEntry).where(
            JournalEntry.tenant_id == user.tenant_id,
        )
    )
    entries = result.scalars().all()

    # Find entries with no source docs
    unmatched_ids = [
        str(e.id) for e in entries
        if not e.source_doc_ids or len(e.source_doc_ids) == 0
    ]

    if not unmatched_ids:
        return {"status": "ok", "message": "Toutes les écritures ont déjà des justificatifs.", "matching": None}

    try:
        from app.services.journal_matcher import match_entries_to_documents
        match_result = await match_entries_to_documents(db, user.tenant_id, unmatched_ids)
        await db.commit()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur lors du rapprochement: {exc}")

    return {
        "status": "ok",
        "matching": match_result,
    }


@router.get("/journal-entries/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entry_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get journal entry with lines and evidence anchors."""
    result = await db.execute(
        select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.tenant_id == user.tenant_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    lines_result = await db.execute(
        select(JournalLine).where(JournalLine.entry_id == entry.id).order_by(JournalLine.line_no)
    )
    lines = lines_result.scalars().all()

    # Build line data with evidence anchors from JSON field
    line_data = []
    for l in lines:
        line_data.append({
            "id": str(l.id),
            "line_no": l.line_no,
            "account_code": l.account_code,
            "label": l.label,
            "debit": float(l.debit),
            "credit": float(l.credit),
            "evidence_anchors": l.evidence_anchors or [],
        })

    # Load linked documents info
    linked_docs = []
    if entry.source_doc_ids:
        for did in entry.source_doc_ids:
            doc_result = await db.execute(
                select(Document).where(Document.id == did, Document.tenant_id == user.tenant_id)
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                linked_docs.append({
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "doc_type": doc.doc_type.value if doc.doc_type else None,
                    "extracted_montant": float(doc.extracted_montant) if doc.extracted_montant else None,
                })

    return JournalEntryResponse(
        id=entry.id,
        workflow_id=entry.workflow_id,
        entry_date=entry.entry_date,
        reference=entry.reference,
        description=entry.description,
        status=entry.status.value,
        source_doc_ids=entry.source_doc_ids or [],
        lines=line_data,
    )


@router.post("/journal-entries/{entry_id}/approve")
async def approve_journal_entry(
    entry_id: str,
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Approve a proposed journal entry."""
    result = await db.execute(
        select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.tenant_id == user.tenant_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    if entry.status != JournalEntryStatus.PROPOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot approve entry in state: {entry.status.value}")

    entry.status = JournalEntryStatus.APPROVED
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="journal_entry_approve",
        entity_type="journal_entry",
        entity_id=str(entry_id),
    ))
    await db.commit()
    return {"status": "approved", "entry_id": str(entry_id)}


@router.post("/journal-entries/{entry_id}/reject")
async def reject_journal_entry(
    entry_id: str,
    reason: str = "",
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Reject a proposed journal entry."""
    result = await db.execute(
        select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.tenant_id == user.tenant_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    entry.status = JournalEntryStatus.REJECTED
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="journal_entry_reject",
        entity_type="journal_entry",
        entity_id=str(entry_id),
    ))
    await db.commit()
    return {"status": "rejected", "entry_id": str(entry_id)}


# ── Journal Upload from CSV / Excel ─────────────────────────────────

def _parse_date(val: str) -> date_type:
    """Try multiple date formats common in Algeria / France."""
    val = val.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Format de date non reconnu: {val}")


def _parse_decimal(val: str) -> Decimal:
    """Parse a decimal, handling comma as separator."""
    val = val.strip().replace(" ", "").replace("\xa0", "")
    # French‐style: 1.234,56 → 1234.56
    if "," in val and "." in val:
        val = val.replace(".", "").replace(",", ".")
    elif "," in val:
        val = val.replace(",", ".")
    if not val or val == "-":
        return Decimal("0")
    return Decimal(val)


def _parse_csv_rows(text: str) -> list[dict]:
    """Parse CSV text into list of row dicts. Auto-detects delimiter."""
    # Detect delimiter
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(text[:2000], delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ';'  # Default for French accounting software

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = []
    for row in reader:
        # Normalize keys (strip whitespace, lowercase)
        clean = {k.strip().lower(): v.strip() if v else "" for k, v in row.items() if k}
        rows.append(clean)
    return rows


def _normalize_column(headers: list[str], candidates: list[str]) -> str | None:
    """Find a column name matching any of the candidates (case-insensitive)."""
    for h in headers:
        hl = h.lower().strip()
        for c in candidates:
            if c == hl or c in hl:
                return h
    return None


def _rows_to_entries(
    rows: list[dict],
) -> list[dict]:
    """Convert parsed rows into structured journal entries.

    Expected CSV columns (flexible naming):
      date, reference/ref, description/libellé, account/compte, label/libellé_ligne,
      debit/débit, credit/crédit

    Rows with the same (date + reference) are grouped into one journal entry.
    """
    if not rows:
        return []

    headers = list(rows[0].keys())

    col_date = _normalize_column(headers, ["date", "date_ecriture", "date_operation"])
    col_ref = _normalize_column(headers, ["reference", "ref", "réf", "n°", "numero", "piece"])
    col_desc = _normalize_column(headers, ["description", "libellé", "libelle", "intitulé", "intitule", "objet"])
    col_account = _normalize_column(headers, ["compte", "account", "code_compte", "n° compte", "account_code"])
    col_label = _normalize_column(headers, ["libellé_ligne", "libelle_ligne", "label", "détail", "detail", "libellé", "libelle"])
    col_debit = _normalize_column(headers, ["debit", "débit", "montant_debit"])
    col_credit = _normalize_column(headers, ["credit", "crédit", "montant_credit"])
    # Some CSVs have a single "montant" column with sign
    col_montant = _normalize_column(headers, ["montant", "amount"])
    col_sens = _normalize_column(headers, ["sens", "type", "d/c"])

    if not col_account:
        raise ValueError(
            f"Colonne 'compte' introuvable. Colonnes détectées: {', '.join(headers)}. "
            f"Le fichier doit contenir au moins: compte, débit, crédit (ou montant + sens)."
        )

    if not col_debit and not col_montant:
        raise ValueError(
            f"Colonne 'débit'/'crédit' ou 'montant' introuvable. Colonnes: {', '.join(headers)}"
        )

    # Group by (date, reference) to form journal entries
    entry_groups: dict[str, dict] = {}

    for i, row in enumerate(rows):
        # Parse fields
        try:
            raw_date = row.get(col_date, "") if col_date else ""
            entry_date = _parse_date(raw_date) if raw_date else date_type.today()
        except ValueError:
            entry_date = date_type.today()

        reference = row.get(col_ref, "") if col_ref else ""
        description = row.get(col_desc, "") if col_desc else ""
        account_code = row.get(col_account, "") if col_account else ""

        # Pick label: first try dedicated label column, fall back to description
        if col_label and col_label != col_desc:
            label = row.get(col_label, "") or description
        else:
            label = description

        # Parse debit / credit
        if col_debit and col_credit:
            debit = _parse_decimal(row.get(col_debit, "0"))
            credit = _parse_decimal(row.get(col_credit, "0"))
        elif col_montant:
            montant = _parse_decimal(row.get(col_montant, "0"))
            sens = (row.get(col_sens, "") if col_sens else "").strip().upper()
            if sens in ("D", "DEBIT", "DÉBIT"):
                debit, credit = montant, Decimal("0")
            elif sens in ("C", "CREDIT", "CRÉDIT"):
                debit, credit = Decimal("0"), montant
            else:
                # Positive = debit, negative = credit
                if montant >= 0:
                    debit, credit = montant, Decimal("0")
                else:
                    debit, credit = Decimal("0"), abs(montant)
        else:
            debit, credit = Decimal("0"), Decimal("0")

        if not account_code:
            continue  # skip empty lines

        group_key = f"{entry_date}|{reference or f'LINE-{i}'}"
        if group_key not in entry_groups:
            entry_groups[group_key] = {
                "entry_date": entry_date,
                "reference": reference or None,
                "description": description or None,
                "lines": [],
            }
        elif description and not entry_groups[group_key]["description"]:
            entry_groups[group_key]["description"] = description

        entry_groups[group_key]["lines"].append({
            "account_code": account_code.strip(),
            "label": label.strip() if label else None,
            "debit": debit,
            "credit": credit,
        })

    return list(entry_groups.values())


@router.post("/journal-entries/upload")
async def upload_journal_file(
    file: UploadFile = File(...),
    auto_match: bool = Query(True, description="Auto-match entries to scanned documents via AI"),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Upload a journal from CSV or Excel file.

    The file is parsed, validated, and journal entries are created.
    If auto_match=true, an AI agent automatically matches entries to uploaded documents.
    Returns a report of created entries, matches, and unjustified entries.
    """
    filename = file.filename or "unknown"
    content = await file.read()

    # ── Parse file ──
    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            # Excel parsing
            try:
                import openpyxl
            except ImportError:
                raise HTTPException(
                    status_code=400,
                    detail="Le support Excel nécessite openpyxl. Installez-le ou utilisez un fichier CSV.",
                )
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            headers = [str(h or "").strip() for h in next(rows_iter)]
            csv_text_lines = [";".join(headers)]
            for row in rows_iter:
                csv_text_lines.append(";".join(str(c or "") for c in row))
            csv_text = "\n".join(csv_text_lines)
            wb.close()
        elif filename.lower().endswith(".csv") or filename.lower().endswith(".txt"):
            # Try multiple encodings
            for encoding in ("utf-8", "utf-8-sig", "cp1252", "iso-8859-1", "latin-1"):
                try:
                    csv_text = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise HTTPException(status_code=400, detail="Impossible de décoder le fichier. Encodage non reconnu.")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Format non supporté: {filename}. Formats acceptés: .csv, .xlsx, .xls",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erreur de lecture du fichier: {exc}")

    # ── Parse rows into entries ──
    try:
        rows = _parse_csv_rows(csv_text)
        if not rows:
            raise HTTPException(status_code=400, detail="Le fichier est vide ou ne contient pas de données.")
        entry_defs = _rows_to_entries(rows)
        if not entry_defs:
            raise HTTPException(status_code=400, detail="Aucune écriture valide trouvée dans le fichier.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erreur d'analyse: {exc}")

    # ── Create journal entries ──
    created_entries = []
    errors = []
    for i, edef in enumerate(entry_defs, 1):
        total_debit = sum(l["debit"] for l in edef["lines"])
        total_credit = sum(l["credit"] for l in edef["lines"])

        # Warn if unbalanced but still create (user can fix later)
        is_balanced = abs(total_debit - total_credit) < Decimal("0.01")
        if not is_balanced:
            errors.append({
                "row": i,
                "reference": edef.get("reference"),
                "message": f"Écriture non équilibrée: débit={total_debit}, crédit={total_credit}",
            })
            continue  # skip unbalanced entries

        entry = JournalEntry(
            tenant_id=user.tenant_id,
            entry_date=datetime.combine(edef["entry_date"], datetime.min.time()),
            reference=edef.get("reference"),
            description=edef.get("description"),
            status=JournalEntryStatus.PROPOSED,
            source_doc_ids=[],
        )
        db.add(entry)
        await db.flush()

        for j, line in enumerate(edef["lines"], 1):
            jl = JournalLine(
                entry_id=entry.id,
                line_no=j,
                account_code=line["account_code"],
                label=line.get("label"),
                debit=line["debit"],
                credit=line["credit"],
                currency="DZD",
            )
            db.add(jl)

        created_entries.append({
            "id": str(entry.id),
            "entry_date": edef["entry_date"].isoformat(),
            "reference": edef.get("reference"),
            "description": edef.get("description"),
            "total_debit": float(total_debit),
            "lines_count": len(edef["lines"]),
        })

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="journal_upload",
        entity_type="journal_file",
        entity_id=filename,
        new_value={
            "filename": filename,
            "entries_created": len(created_entries),
            "errors": len(errors),
            "total_rows": len(rows),
        },
    ))
    await db.commit()

    # ── AI Auto-matching ──
    match_result = None
    if auto_match and created_entries:
        try:
            from app.services.journal_matcher import match_entries_to_documents
            entry_ids = [e["id"] for e in created_entries]
            match_result = await match_entries_to_documents(db, user.tenant_id, entry_ids)
            await db.commit()
        except Exception as exc:
            logger.error("journal_upload_match_error", error=str(exc))
            match_result = {"error": str(exc), "matches": [], "unmatched_entries": [], "stats": {}}

    # ── Cost center recalculation ──
    cc_recalc_count = 0
    try:
        from app.services.cost_center_engine import (
            calculer_centre_cout_mensuel,
            recalculer_tous_centres_cout,
        )
        from app.models.financial import Projet

        # Gather unique months from entries
        months_seen: set[tuple[int, int]] = set()
        for edef in entry_defs:
            d = edef["entry_date"]
            months_seen.add((d.month, d.year))

        # Find which cost center codes were referenced in journal lines
        line_cost_centers: set[str] = set()
        for edef in entry_defs:
            for line in edef["lines"]:
                code = line["account_code"]
                # Accounts starting with 6 (charges) or 7 (produits) affect cost centers
                if code and code[0] in ("6", "7"):
                    line_cost_centers.add(code)

        if line_cost_centers and months_seen:
            # Get all active projects for the tenant
            from app.models.financial import Entreprise
            ent_result = await db.execute(
                select(Entreprise.id).where(
                    Entreprise.tenant_id == user.tenant_id,
                    Entreprise.is_active == True,
                )
            )
            entreprise_ids = [row[0] for row in ent_result.fetchall()]

            for ent_id in entreprise_ids:
                for mois, annee in months_seen:
                    try:
                        results = await recalculer_tous_centres_cout(
                            db, user.tenant_id, ent_id, mois, annee
                        )
                        cc_recalc_count += len(results)
                    except Exception:
                        pass  # Don't fail the upload for CC errors

            if cc_recalc_count > 0:
                await db.commit()
    except ImportError:
        pass  # cost_center_engine not available
    except Exception as exc:
        logger.warning("journal_upload_cc_recalc_error", error=str(exc))

    return {
        "status": "ok",
        "filename": filename,
        "total_rows": len(rows),
        "entries_created": len(created_entries),
        "entries": created_entries,
        "parse_errors": errors,
        "matching": match_result,
        "cost_center_recalculated": cc_recalc_count,
    }


# ── SCF Plan Comptable Initialization ────────────────────────────────────

@router.post("/scf/init")
async def init_scf_plan(
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Initialize the SCF plan comptable algérien and default journals per entity.

    EX-SCF-001 + EX-SCF-002.
    """
    from app.services.scf_plan_comptable import seed_scf_plan_comptable, ensure_default_journals

    accounts_created = await seed_scf_plan_comptable(db, user.tenant_id)
    journals_created = await ensure_default_journals(db, user.tenant_id)

    return {
        "status": "ok",
        "accounts_created": accounts_created,
        "journals_created": journals_created,
    }


# ── G50 Declaration Computation ──────────────────────────────────────────

@router.get("/declarations/g50")
async def compute_g50_declaration(
    entreprise_id: str = Query(...),
    mois: int = Query(..., ge=1, le=12),
    annee: int = Query(..., ge=2020),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Compute G50 monthly tax declaration from committed entries.

    EX-SCF-005: Auto-generated from validated journal entries.
    Returns: TVA nette, TAP, IBS acompte, IRG, timbre, total.
    """
    from app.services.declaration_engine import compute_g50
    return await compute_g50(db, user.tenant_id, entreprise_id, mois, annee)


@router.get("/declarations/cnas")
async def compute_cnas_declaration(
    entreprise_id: str = Query(...),
    trimestre: int = Query(..., ge=1, le=4),
    annee: int = Query(..., ge=2020),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Compute CNAS quarterly declaration from payroll entries.

    EX-SCF-005.
    """
    from app.services.declaration_engine import compute_cnas_trimestrielle
    return await compute_cnas_trimestrielle(db, user.tenant_id, entreprise_id, trimestre, annee)


# ── Period Validation (EX-CCA-004) ───────────────────────────────────────

@router.post("/periods/{period_id}/close")
async def close_period(
    period_id: str,
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Close an accounting period. No further entries can be created in it.

    Kill Test KT-04.
    """
    result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == user.tenant_id,
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Période introuvable")
    if period.is_closed:
        raise HTTPException(status_code=400, detail="Période déjà clôturée")

    period.is_closed = True
    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="close_period", entity_type="accounting_period", entity_id=period_id,
    ))
    await db.commit()
    return {"status": "ok", "period": period.name, "is_closed": True}


# ── PDF Downloads ────────────────────────────────────────────────────────

@router.get("/pdf/g50")
async def download_g50_pdf(
    entreprise_id: str = Query(...),
    mois: int = Query(..., ge=1, le=12),
    annee: int = Query(..., ge=2020),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Download G50 declaration as printable PDF."""
    from fastapi.responses import Response
    from app.services.declaration_engine import compute_g50
    from app.services.pdf_generator import generate_g50_pdf

    data = await compute_g50(db, user.tenant_id, entreprise_id, mois, annee)

    # Get entity name
    ent_result = await db.execute(
        select(Entreprise).where(Entreprise.id == entreprise_id)
    )
    ent = ent_result.scalar_one_or_none()
    entity_name = ent.raison_sociale if ent else entreprise_id

    pdf_bytes = generate_g50_pdf(data, entity_name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="G50_{data["periode"]}_{ent.code if ent else ""}.pdf"',
        },
    )


@router.get("/pdf/cnas")
async def download_cnas_pdf(
    entreprise_id: str = Query(...),
    trimestre: int = Query(..., ge=1, le=4),
    annee: int = Query(..., ge=2020),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Download CNAS quarterly declaration as printable PDF."""
    from fastapi.responses import Response
    from app.services.declaration_engine import compute_cnas_trimestrielle
    from app.services.pdf_generator import generate_cnas_pdf

    data = await compute_cnas_trimestrielle(db, user.tenant_id, entreprise_id, trimestre, annee)

    ent_result = await db.execute(select(Entreprise).where(Entreprise.id == entreprise_id))
    ent = ent_result.scalar_one_or_none()
    entity_name = ent.raison_sociale if ent else entreprise_id

    pdf_bytes = generate_cnas_pdf(data, entity_name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="CNAS_{data["periode"]}_{ent.code if ent else ""}.pdf"',
        },
    )


@router.get("/pdf/journal")
async def download_journal_pdf(
    entreprise_id: str = Query(...),
    date_from: str = Query(..., description="YYYY-MM-DD"),
    date_to: str = Query(..., description="YYYY-MM-DD"),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Download journal entries listing as printable PDF."""
    from fastapi.responses import Response
    from app.services.pdf_generator import generate_journal_pdf
    from sqlalchemy import text as sa_text

    ent_result = await db.execute(select(Entreprise).where(Entreprise.id == entreprise_id))
    ent = ent_result.scalar_one_or_none()
    entity_name = ent.raison_sociale if ent else entreprise_id

    # Fetch entries with lines
    entries_result = await db.execute(sa_text("""
        SELECT je.id, je.entry_date, je.reference, je.description, je.realite_financiere
        FROM journal_entries je
        WHERE je.tenant_id = :tid AND je.entreprise_id = :eid
          AND je.entry_date >= :d1 AND je.entry_date <= :d2
        ORDER BY je.entry_date
    """), {"tid": user.tenant_id, "eid": entreprise_id, "d1": date_from, "d2": date_to})
    entry_rows = entries_result.fetchall()

    entries = []
    for row in entry_rows:
        lines_result = await db.execute(sa_text("""
            SELECT account_code, label, debit, credit
            FROM journal_lines WHERE entry_id = :eid ORDER BY line_no
        """), {"eid": row[0]})
        lines = [
            {"account_code": l[0], "label": l[1], "debit": l[2], "credit": l[3]}
            for l in lines_result.fetchall()
        ]
        entries.append({
            "entry_date": str(row[1]),
            "reference": row[2],
            "description": row[3],
            "lines": lines,
        })

    period = f"{date_from} au {date_to}"
    pdf_bytes = generate_journal_pdf(entries, entity_name, period)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="Journal_{ent.code if ent else ""}_{date_from}_{date_to}.pdf"',
        },
    )


@router.get("/pdf/balance")
async def download_balance_pdf(
    entreprise_id: str = Query(...),
    date_from: str = Query(..., description="YYYY-MM-DD"),
    date_to: str = Query(..., description="YYYY-MM-DD"),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Download Balance des Comptes (trial balance) as printable PDF."""
    from fastapi.responses import Response
    from app.services.pdf_generator import generate_balance_pdf
    from sqlalchemy import text as sa_text

    ent_result = await db.execute(select(Entreprise).where(Entreprise.id == entreprise_id))
    ent = ent_result.scalar_one_or_none()
    entity_name = ent.raison_sociale if ent else entreprise_id

    # Aggregate debit/credit by account
    result = await db.execute(sa_text("""
        SELECT jl.account_code,
               COALESCE(coa.label, jl.account_code) as label,
               SUM(jl.debit) as total_debit,
               SUM(jl.credit) as total_credit
        FROM journal_lines jl
        JOIN journal_entries je ON jl.entry_id = je.id
        LEFT JOIN chart_of_accounts coa ON coa.code = jl.account_code AND coa.tenant_id = je.tenant_id
        WHERE je.tenant_id = :tid AND je.entreprise_id = :eid
          AND je.entry_date >= :d1 AND je.entry_date <= :d2
          AND je.status IN ('COMMITTED', 'VALIDATED', 'PROPOSED')
        GROUP BY jl.account_code, coa.label
        ORDER BY jl.account_code
    """), {"tid": user.tenant_id, "eid": entreprise_id, "d1": date_from, "d2": date_to})

    accounts = [
        {"code": r[0], "label": r[1], "total_debit": r[2], "total_credit": r[3]}
        for r in result.fetchall()
    ]

    period = f"{date_from} au {date_to}"
    pdf_bytes = generate_balance_pdf(accounts, entity_name, period)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="Balance_{ent.code if ent else ""}_{date_from}_{date_to}.pdf"',
        },
    )


@router.get("/pdf/grand-livre")
async def download_grand_livre_pdf(
    entreprise_id: str = Query(...),
    date_from: str = Query(..., description="YYYY-MM-DD"),
    date_to: str = Query(..., description="YYYY-MM-DD"),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Download Grand Livre (general ledger detail) as printable PDF."""
    from fastapi.responses import Response
    from app.services.pdf_generator import generate_grand_livre_pdf
    from sqlalchemy import text as sa_text

    ent_result = await db.execute(select(Entreprise).where(Entreprise.id == entreprise_id))
    ent = ent_result.scalar_one_or_none()
    entity_name = ent.raison_sociale if ent else entreprise_id

    # Get all accounts that have movements
    accts_result = await db.execute(sa_text("""
        SELECT DISTINCT jl.account_code, COALESCE(coa.label, jl.account_code) as label
        FROM journal_lines jl
        JOIN journal_entries je ON jl.entry_id = je.id
        LEFT JOIN chart_of_accounts coa ON coa.code = jl.account_code AND coa.tenant_id = je.tenant_id
        WHERE je.tenant_id = :tid AND je.entreprise_id = :eid
          AND je.entry_date >= :d1 AND je.entry_date <= :d2
        ORDER BY jl.account_code
    """), {"tid": user.tenant_id, "eid": entreprise_id, "d1": date_from, "d2": date_to})

    accounts = []
    for acc_code, acc_label in accts_result.fetchall():
        mvts_result = await db.execute(sa_text("""
            SELECT je.entry_date, je.reference, jl.label, jl.debit, jl.credit
            FROM journal_lines jl
            JOIN journal_entries je ON jl.entry_id = je.id
            WHERE je.tenant_id = :tid AND je.entreprise_id = :eid
              AND jl.account_code = :ac
              AND je.entry_date >= :d1 AND je.entry_date <= :d2
            ORDER BY je.entry_date
        """), {"tid": user.tenant_id, "eid": entreprise_id, "ac": acc_code, "d1": date_from, "d2": date_to})

        movements = [
            {"date": str(m[0]), "reference": m[1], "label": m[2], "debit": m[3], "credit": m[4]}
            for m in mvts_result.fetchall()
        ]
        accounts.append({"code": acc_code, "label": acc_label, "movements": movements})

    period = f"{date_from} au {date_to}"
    pdf_bytes = generate_grand_livre_pdf(accounts, entity_name, period)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="GrandLivre_{ent.code if ent else ""}_{date_from}_{date_to}.pdf"',
        },
    )
