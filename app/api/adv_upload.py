"""ADV Smart Document Upload — AI classification + auto-routing.

Accepts an image or PDF, uses the LLM vision/text agent to:
  1. Identify document type (invoice, receipt, payroll, contract, tax declaration, etc.)
  2. Extract the document date (date mentioned in the doc, not upload date)
  3. Extract key fields (amount, reference, client, etc.)
  4. Return classification so frontend can auto-route to the right ADV section
"""
import base64
import uuid
from datetime import date, datetime
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User

router = APIRouter(tags=["ADV Upload"])

ADV_SYSTEM_PROMPT = """You are a document classification expert for a real estate and construction company in Algeria.
Analyze the document image and return a JSON object with:
{
  "document_type": "ONE OF: FACTURE, RECU_PAIEMENT, CONTRAT, BULLETIN_PAIE, DECLARATION_FISCALE, BON_COMMANDE, RELEVE_BANCAIRE, ECHEANCIER, DEVIS, AVOIR, AUTRE",
  "adv_section": "ONE OF: clients, contracts, receivables, payments, capital, retraits, bulletins, declarations, comptes, journaux, echeancier",
  "document_date": "YYYY-MM-DD format - the date mentioned IN the document (not today). Look for dates like 'date de facture', 'date', 'le', 'fait a ... le', 'periode', etc. If multiple dates, use the primary document date.",
  "amount": null or number (main amount in the document),
  "reference": null or string (invoice number, receipt number, contract number, etc.),
  "client_name": null or string (client/company name if visible),
  "description": "Brief description of the document in French",
  "confidence": 0.0 to 1.0,
  "extracted_fields": {
    "any_additional_field": "value"
  }
}

Classification rules:
- FACTURE (invoice) → adv_section: "receivables"
- RECU_PAIEMENT (payment receipt) → adv_section: "payments"
- CONTRAT → adv_section: "contracts"
- BULLETIN_PAIE (payroll) → adv_section: "bulletins"
- DECLARATION_FISCALE (tax: G50, IBS, TAP) → adv_section: "declarations"
- BON_COMMANDE (purchase order) → adv_section: "receivables"
- RELEVE_BANCAIRE (bank statement) → adv_section: "comptes"
- ECHEANCIER (payment schedule) → adv_section: "echeancier"
- DEVIS (quote) → adv_section: "contracts"
- AVOIR (credit note) → adv_section: "receivables"

For document_date: This is CRITICAL. Always extract the date from the document content, never use today's date. If no date is visible, set to null."""


async def _classify_single_file(
    content: bytes,
    mime: str,
    filename: str,
    tenant_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Classify one file via AI vision and persist as a Document. Returns result dict."""
    from app.services.llm_graph import invoke_json_agent
    from app.models.core import Document
    from app.database import AsyncSessionLocal

    image_b64 = base64.b64encode(content).decode("utf-8")

    result = await invoke_json_agent(
        system_prompt=ADV_SYSTEM_PROMPT,
        user_prompt="Classify this document and extract all relevant information.",
        image_b64=image_b64,
        image_mime=mime,
    )
    parsed = result["parsed_json"]

    doc_date_str = parsed.get("document_date")
    doc_date = None
    if doc_date_str:
        try:
            doc_date = datetime.strptime(doc_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            doc_date = None

    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename=filename or "document",
        mime_type=mime,
        file_size=len(content),
        file_data=content,
        doc_type=parsed.get("document_type", "AUTRE"),
        extracted_montant=parsed.get("amount"),
        uploaded_by=user_id,
    )
    if doc_date:
        doc.created_at = datetime.combine(doc_date, datetime.min.time())

    async with AsyncSessionLocal() as db:
        db.add(doc)
        await db.commit()

    return {
        "document_id": doc_id,
        "document_type": parsed.get("document_type", "AUTRE"),
        "adv_section": parsed.get("adv_section", "clients"),
        "document_date": doc_date_str,
        "amount": parsed.get("amount"),
        "reference": parsed.get("reference"),
        "client_name": parsed.get("client_name"),
        "description": parsed.get("description", ""),
        "confidence": parsed.get("confidence", 0.5),
        "extracted_fields": parsed.get("extracted_fields", {}),
        "ai_model": result.get("ai_model", ""),
        "filename": filename,
    }


@router.post("/upload-classify")
async def classify_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Classify an uploaded document using AI vision and extract key fields."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.LLM_API_KEY:
        raise HTTPException(503, "AI service not configured (LLM_API_KEY missing)")

    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop volumineux (max 15 MB)")

    try:
        return await _classify_single_file(
            content=content,
            mime=file.content_type or "image/jpeg",
            filename=file.filename or "document",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"AI classification failed: {str(exc)}")


@router.post("/bulk-classify")
async def bulk_classify_documents(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """Bulk upload + AI classify multiple documents for ADV injection.

    Each file is classified independently. Results include the ADV section
    each document was routed to, so the frontend can display a summary.
    """
    from app.config import get_settings

    settings = get_settings()
    if not settings.LLM_API_KEY:
        raise HTTPException(503, "AI service not configured (LLM_API_KEY missing)")

    if not files:
        raise HTTPException(400, "Aucun fichier fourni")

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    section_counts: dict[str, int] = {}

    for file in files:
        try:
            content = await file.read()
            if len(content) > 15 * 1024 * 1024:
                failures.append({"filename": file.filename, "error": "Fichier trop volumineux (max 15 MB)"})
                continue

            item = await _classify_single_file(
                content=content,
                mime=file.content_type or "image/jpeg",
                filename=file.filename or "document",
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
            )
            results.append(item)
            section = item.get("adv_section", "clients")
            section_counts[section] = section_counts.get(section, 0) + 1
        except Exception as exc:
            failures.append({"filename": file.filename, "error": str(exc)})

    return {
        "status": "ok",
        "total_files": len(files),
        "classified_count": len(results),
        "failed_count": len(failures),
        "section_counts": section_counts,
        "items": results,
        "failures": failures,
    }


@router.get("/combined-stats")
async def combined_adv_treasury_stats(
    entreprise_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Combined ADV + Treasury stats for the merged dashboard."""
    from sqlalchemy import select, func as sa_func
    from app.models.adv import Client, Contract, Receivable, Payment, ContractStatus
    from app.models.treasury import (
        CapitalAssocie, RetraitAssocie, BulletinPaie, DeclarationFiscale,
        EcheancierClient, CompteBancaire,
    )

    tid = current_user.tenant_id

    # ADV stats
    clients_q = select(sa_func.count(Client.id)).where(Client.tenant_id == tid)
    contracts_q = select(sa_func.count(Contract.id)).where(
        Contract.tenant_id == tid, Contract.status == ContractStatus.ACTIVE
    )
    receivable_q = select(
        sa_func.coalesce(sa_func.sum(Receivable.amount - Receivable.amount_paid), 0)
    ).where(Receivable.tenant_id == tid)
    paid_q = select(sa_func.coalesce(sa_func.sum(Payment.amount), 0)).where(
        Payment.tenant_id == tid
    )
    overdue_q = select(
        sa_func.coalesce(sa_func.sum(Receivable.amount - Receivable.amount_paid), 0)
    ).where(
        Receivable.tenant_id == tid,
        Receivable.due_date < date.today(),
        Receivable.amount > Receivable.amount_paid,
    )

    if entreprise_id:
        clients_q = clients_q.where(Client.entreprise_id == entreprise_id)
        contracts_q = contracts_q.where(Contract.entreprise_id == entreprise_id)
        receivable_q = receivable_q.where(Receivable.entreprise_id == entreprise_id)
        paid_q = paid_q.where(Payment.entreprise_id == entreprise_id)
        overdue_q = overdue_q.where(Receivable.entreprise_id == entreprise_id)
    if projet_id:
        clients_q = clients_q.where(Client.projet_id == projet_id)
        contracts_q = contracts_q.where(Contract.projet_id == projet_id)
        receivable_q = receivable_q.where(Receivable.projet_id == projet_id)
        paid_q = paid_q.where(Payment.projet_id == projet_id)
        overdue_q = overdue_q.where(Receivable.projet_id == projet_id)

    # Treasury stats
    capital_q = select(sa_func.coalesce(sa_func.sum(CapitalAssocie.montant), 0)).where(
        CapitalAssocie.tenant_id == tid
    )
    retraits_q = select(sa_func.coalesce(sa_func.sum(RetraitAssocie.montant), 0)).where(
        RetraitAssocie.tenant_id == tid
    )
    bulletins_q = select(sa_func.count(BulletinPaie.id)).where(
        BulletinPaie.tenant_id == tid
    )
    declarations_q = select(sa_func.count(DeclarationFiscale.id)).where(
        DeclarationFiscale.tenant_id == tid
    )
    echeances_q = select(sa_func.count(EcheancierClient.id)).where(
        EcheancierClient.tenant_id == tid,
        EcheancierClient.statut == "EN_ATTENTE",
    )
    solde_bancaire_q = select(
        sa_func.coalesce(sa_func.sum(CompteBancaire.solde_actuel), 0)
    ).where(CompteBancaire.tenant_id == tid, CompteBancaire.actif == True)

    # Execute all
    results = await db.execute(clients_q)
    clients_count = results.scalar() or 0
    results = await db.execute(contracts_q)
    active_contracts = results.scalar() or 0
    results = await db.execute(receivable_q)
    total_receivable = float(results.scalar() or 0)
    results = await db.execute(paid_q)
    total_paid = float(results.scalar() or 0)
    results = await db.execute(overdue_q)
    overdue_amount = float(results.scalar() or 0)
    results = await db.execute(capital_q)
    total_capital = float(results.scalar() or 0)
    results = await db.execute(retraits_q)
    total_retraits = float(results.scalar() or 0)
    results = await db.execute(bulletins_q)
    bulletins_count = results.scalar() or 0
    results = await db.execute(declarations_q)
    declarations_count = results.scalar() or 0
    results = await db.execute(echeances_q)
    echeances_pending = results.scalar() or 0
    results = await db.execute(solde_bancaire_q)
    solde_bancaire = float(results.scalar() or 0)

    # Document count (docs uploaded this month)
    from app.models.core import Document
    docs_q = select(sa_func.count(Document.id)).where(Document.tenant_id == tid)
    results = await db.execute(docs_q)
    total_documents = results.scalar() or 0

    return {
        # ADV
        "clients_count": clients_count,
        "active_contracts": active_contracts,
        "total_receivable": total_receivable,
        "overdue_amount": overdue_amount,
        "total_paid": total_paid,
        # Treasury
        "total_capital": total_capital,
        "total_retraits": total_retraits,
        "position_nette": total_capital - total_retraits,
        "solde_bancaire": solde_bancaire,
        "bulletins_count": bulletins_count,
        "declarations_count": declarations_count,
        "echeances_pending": echeances_pending,
        # Documents
        "total_documents": total_documents,
    }
