"""GFI Platform — Treasury & Finance Associés API endpoints.

Provides:
- Capital contributions CRUD (capital_associes)
- Partner withdrawals CRUD (retraits_associes)
- Consolidation views (by partner, by company)
- Bulletins de paie CRUD
- Déclarations fiscales CRUD
- Échéancier clients (payment schedule)
- Bank accounts CRUD
- Accounting journals CRUD
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User, AuditLog
from app.models.financial import Associe, Projet
from app.models.treasury import (
    CapitalAssocie, RetraitAssocie,
    ConsolidationAssocie, ConsolidationEntreprise,
    BulletinPaie, DeclarationFiscale,
    EcheancierClient, CompteBancaire, Journal,
    StatutBulletinPaie, StatutDeclaration, TypeDeclaration,
    TypeJournal, StatutEcheance,
)

router = APIRouter(tags=["Treasury & Finance Associés"])


# ────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ────────────────────────────────────────────────────────────────────────────

class CapitalCreate(BaseModel):
    associe_id: str
    projet_id: str
    montant: float = Field(gt=0)
    date_apport: Optional[date] = None
    date_versement: Optional[date] = None  # alias — frontend sends this
    description: Optional[str] = None
    reference: Optional[str] = None
    mode_paiement: Optional[str] = None

class RetraitCreate(BaseModel):
    associe_id: str
    projet_id: str
    montant: float = Field(gt=0)
    date_retrait: date
    description: str
    reference: Optional[str] = None


class RetraitCreateResult(BaseModel):
    id: str
    statut: str
    motif_rejet: Optional[str] = None
    solde_individuel: Optional[float] = None
    max_autorise: Optional[float] = None
    solde_global_cca: Optional[float] = None
    ai_montant_extrait: Optional[float] = None
    ai_verification: Optional[str] = None
    message: str

class BulletinCreate(BaseModel):
    employe_id: str
    entreprise_id: str
    projet_id: Optional[str] = None
    mois: int = Field(ge=1, le=12)
    annee: int
    salaire_base: float = 0
    heures_sup: float = 0
    prime_rendement: float = 0
    indemnites: float = 0
    complement_nd: float = 0

class DeclarationCreate(BaseModel):
    entreprise_id: str
    exercice_id: str
    type_declaration: str  # G50, IBS, DADS, TAP
    mois: Optional[int] = None
    annee: int
    montant_tva_collectee: float = 0
    montant_tva_deductible: float = 0
    montant_tap: float = 0
    montant_irg_salaires: float = 0
    montant_total: float = 0

class CompteBancaireCreate(BaseModel):
    entreprise_id: str
    banque: str
    agence: Optional[str] = None
    numero_compte: Optional[str] = None
    iban: Optional[str] = None
    rib: Optional[str] = None

class JournalCreate(BaseModel):
    entreprise_id: str
    code: str
    libelle: str
    type_journal: str = "OD"

class EcheancierCreate(BaseModel):
    client_id: str
    projet_id: str
    lot_id: Optional[str] = None
    numero_echeance: int
    montant: float
    date_prevue: date


# ────────────────────────────────────────────────────────────────────────────
# Capital Associés
# ────────────────────────────────────────────────────────────────────────────

@router.post("/capital", status_code=201)
async def create_capital_apport(
    body: CapitalCreate,
    file: Optional[UploadFile] = File(None, description="Justificatif (reçu virement, chèque, PV)"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record a capital contribution from a partner to a project. Proof verified by AI."""
    # AI proof verification if document provided
    doc_id = None
    if file and file.filename:
        from app.services.proof_verifier import verify_proof
        proof = await verify_proof(
            file, "enregistrer_paiement",
            {"montant": body.montant, "action_detail": "Versement capital associé"},
            user.tenant_id, user.id, db,
        )
        if not proof["verified"]:
            raise HTTPException(400, f"BLOCAGE : Document non conforme — {proof['rejection_reason']}")
        doc_id = proof.get("document_id")

    effective_date = body.date_apport or body.date_versement or date.today()
    record = CapitalAssocie(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        associe_id=body.associe_id,
        projet_id=body.projet_id,
        montant=body.montant,
        date_apport=effective_date,
        description=body.description,
        reference=body.reference,
        created_by=user.id,
    )
    db.add(record)
    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="capital_apport", entity_type="capital_associe", entity_id=record.id,
    ))
    await db.commit()
    await db.refresh(record)
    return {"id": record.id, "message": "Versement de capital enregistré"}


@router.get("/capital")
async def list_capital(
    associe_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List capital contributions, optionally filtered by partner or project."""
    q = select(CapitalAssocie).where(CapitalAssocie.tenant_id == user.tenant_id)
    if associe_id:
        q = q.where(CapitalAssocie.associe_id == associe_id)
    if projet_id:
        q = q.where(CapitalAssocie.projet_id == projet_id)
    q = q.order_by(CapitalAssocie.date_apport.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "associe_id": r.associe_id, "projet_id": r.projet_id,
            "montant": float(r.montant), "date_apport": str(r.date_apport),
            "description": r.description, "reference": r.reference,
        }
        for r in rows
    ]


@router.delete("/capital/{capital_id}")
async def delete_capital(
    capital_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CapitalAssocie).where(
            CapitalAssocie.id == capital_id,
            CapitalAssocie.tenant_id == user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Capital record not found")
    await db.delete(record)
    await db.commit()
    return {"message": "deleted"}


# ────────────────────────────────────────────────────────────────────────────
# Retraits Associés
# ────────────────────────────────────────────────────────────────────────────

@router.post("/retraits", status_code=201)
async def create_retrait(
    file: UploadFile = File(..., description="Document justificatif (demande écrite, PDF ou image)"),
    associe_id: str = Form(...),
    projet_id: str = Form(...),
    montant: float = Form(..., gt=0),
    date_retrait: str = Form(...),
    description: str = Form(...),
    reference: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Request a partner withdrawal with mandatory justification document.

    Flow:
      1. Upload & store the justification document (written demande)
      2. AI analyzes the document to extract the requested amount
      3. If AI-extracted amount != form amount → auto-REFUSE (montant mismatch)
      4. Validate R-003 rules (50% individual, global positive)
      5. If R-003 fails → auto-BLOQUE
      6. Otherwise → statut=DEMANDE, awaiting DAF approval
    """
    import hashlib
    from app.services.blocking_rules import validate_retrait_associe, BlockingError
    from app.models.core import Document
    from app.storage.service import get_storage_service

    # ── 1. Store the justification document ──
    allowed = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}
    if file.content_type not in allowed:
        raise HTTPException(400, f"Format non supporté: {file.content_type}. Acceptés: PDF, PNG, JPG, TIFF")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "Fichier trop volumineux (max 20 MB)")

    file_hash = hashlib.sha256(content).hexdigest()
    storage = get_storage_service()
    storage_key = f"documents/{user.tenant_id}/retraits/{file_hash}/{file.filename}"
    await storage.upload(storage_key, content, file.content_type)

    doc = Document(
        tenant_id=user.tenant_id,
        filename=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        sha256=file_hash,
        storage_key=storage_key,
        uploaded_by=user.id,
        module_routed_to="treasury",
    )
    db.add(doc)
    await db.flush()
    doc_id = doc.id

    # ── 2. AI analysis of the document ──
    ai_montant = None
    ai_verification = None
    try:
        ai_result = await _analyze_retrait_document(content, file.content_type, file.filename)
        ai_montant = ai_result.get("montant")
        ai_verification = ai_result.get("verification")
    except Exception as exc:
        ai_verification = f"Analyse IA échouée: {exc}"

    # ── 3. Check AI amount vs form amount ──
    statut = "DEMANDE"
    motif_rejet = None
    montant_decimal = Decimal(str(montant))

    if ai_montant is not None:
        ai_montant_decimal = Decimal(str(ai_montant))
        tolerance = montant_decimal * Decimal("0.02")  # 2% tolerance
        if abs(ai_montant_decimal - montant_decimal) > tolerance:
            statut = "REFUSE"
            motif_rejet = (
                f"Incohérence montant : le document mentionne {ai_montant_decimal:,.2f} DA "
                f"mais la demande indique {montant_decimal:,.2f} DA. "
                f"Écart de {abs(ai_montant_decimal - montant_decimal):,.2f} DA "
                f"(tolérance 2% = {tolerance:,.2f} DA)."
            )

    # ── 4. Validate R-003 rules (only if not already refused) ──
    snapshot = {"solde_individuel": 0, "max_autorise": 0, "solde_global_cca": 0}
    if statut == "DEMANDE":
        try:
            snapshot = await validate_retrait_associe(associe_id, montant_decimal, db)
        except BlockingError as e:
            statut = "BLOQUE"
            motif_rejet = str(e)
            if e.payload:
                snapshot = {
                    "solde_individuel": e.payload.get("solde_individuel", 0),
                    "max_autorise": e.payload.get("max_autorise", 0),
                    "solde_global_cca": e.payload.get("solde_global_cca", 0),
                }

    # ── 5. Create the retrait record ──
    record = RetraitAssocie(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        associe_id=associe_id,
        projet_id=projet_id,
        montant=montant,
        date_retrait=date_retrait,
        description=description,
        reference=reference,
        document_id=doc_id,
        statut=statut,
        motif_rejet=motif_rejet,
        solde_individuel=snapshot.get("solde_individuel"),
        max_autorise=snapshot.get("max_autorise"),
        solde_global_cca=snapshot.get("solde_global_cca"),
        created_by=user.id,
    )
    db.add(record)

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action=f"retrait_{statut.lower()}", entity_type="retrait",
        entity_id=record.id,
    ))
    await db.commit()
    await db.refresh(record)

    return {
        "id": record.id,
        "statut": statut,
        "motif_rejet": motif_rejet,
        "solde_individuel": snapshot.get("solde_individuel"),
        "max_autorise": snapshot.get("max_autorise"),
        "solde_global_cca": snapshot.get("solde_global_cca"),
        "ai_montant_extrait": ai_montant,
        "ai_verification": ai_verification,
        "document_id": doc_id,
        "message": (
            "Demande de retrait enregistrée — en attente d'approbation DAF" if statut == "DEMANDE"
            else f"Retrait {statut} : {motif_rejet}"
        ),
    }


async def _analyze_retrait_document(content: bytes, mime_type: str, filename: str) -> dict:
    """Use AI to analyze a withdrawal request document and extract the amount.

    Returns: {"montant": float|None, "verification": str, "signataire": str|None}
    """
    import base64

    extracted_text = ""
    image_b64 = None
    image_mime = None

    if mime_type == "application/pdf":
        try:
            import fitz
            pdf = fitz.open(stream=content, filetype="pdf")
            pages = []
            for i in range(min(pdf.page_count, 3)):
                pages.append(pdf.load_page(i).get_text())
            pdf.close()
            extracted_text = "\n".join(pages)[:6000]
        except Exception:
            pass
        if not extracted_text.strip():
            try:
                import fitz
                pdf = fitz.open(stream=content, filetype="pdf")
                pix = pdf.load_page(0).get_pixmap(dpi=200)
                image_b64 = base64.b64encode(pix.tobytes("png")).decode()
                image_mime = "image/png"
                pdf.close()
            except Exception:
                pass
    else:
        image_b64 = base64.b64encode(content).decode()
        image_mime = mime_type

    system_prompt = """\
You are a financial document verifier for Groupe Dendani (Algeria).
You receive a withdrawal request document (demande de retrait d'un associé).

Your task: Extract key information from this document:
1. montant: The withdrawal amount requested (number, in DA/DZD)
2. signataire: The name of the person requesting the withdrawal
3. date_document: The date written on the document (YYYY-MM-DD)
4. verification: A one-sentence summary of what the document says

IMPORTANT:
- Extract the EXACT amount mentioned in the document
- If multiple amounts are mentioned, extract the total/final requested amount
- Return amounts as plain numbers (no currency symbols)
- If you cannot find an amount, return montant as null

Reply with JSON only:
{"montant": ..., "signataire": "...", "date_document": "...", "verification": "..."}
No markdown fences."""

    user_prompt = f"Document: {filename}\n"
    if extracted_text:
        user_prompt += f"\nText:\n\"\"\"\n{extracted_text}\n\"\"\""
    if image_b64:
        user_prompt += "\nAnalyze the attached document image."

    from app.services.llm_graph import invoke_json_agent
    result = await invoke_json_agent(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.0,
        max_tokens=512,
        image_b64=image_b64,
        image_mime=image_mime,
    )
    data = result["parsed_json"]

    montant = None
    if data.get("montant") is not None:
        try:
            montant = float(data["montant"])
            if montant <= 0:
                montant = None
        except (ValueError, TypeError):
            pass

    return {
        "montant": montant,
        "signataire": data.get("signataire"),
        "date_document": data.get("date_document"),
        "verification": data.get("verification", "Document analysé"),
    }


@router.post("/retraits/{retrait_id}/approuver")
async def approuver_retrait(
    retrait_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve a pending withdrawal request (DAF only)."""
    from datetime import datetime

    result = await db.execute(
        select(RetraitAssocie).where(
            RetraitAssocie.id == retrait_id,
            RetraitAssocie.tenant_id == user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Demande introuvable")
    if record.statut != "DEMANDE":
        raise HTTPException(400, f"Impossible d'approuver : statut actuel = {record.statut}")

    # Re-validate rules at approval time
    from app.services.blocking_rules import validate_retrait_associe, BlockingError
    try:
        await validate_retrait_associe(record.associe_id, Decimal(str(record.montant)), db)
    except BlockingError as e:
        record.statut = "BLOQUE"
        record.motif_rejet = f"Bloqué à l'approbation : {e}"
        record.date_decision = datetime.utcnow()
        db.add(AuditLog(
            tenant_id=user.tenant_id, user_id=user.id,
            action="retrait_bloque_approbation", entity_type="retrait", entity_id=retrait_id,
        ))
        await db.commit()
        raise HTTPException(400, f"Retrait bloqué par les règles R-003 : {e}")

    record.statut = "APPROUVE"
    record.approuve_par = user.id
    record.date_decision = datetime.utcnow()

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="retrait_approuve", entity_type="retrait", entity_id=retrait_id,
    ))
    await db.commit()
    return {"id": retrait_id, "statut": "APPROUVE", "message": "Retrait approuvé"}


@router.post("/retraits/{retrait_id}/refuser")
async def refuser_retrait(
    retrait_id: str,
    motif: str = Query(..., description="Motif du refus"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Refuse a pending withdrawal request."""
    from datetime import datetime

    result = await db.execute(
        select(RetraitAssocie).where(
            RetraitAssocie.id == retrait_id,
            RetraitAssocie.tenant_id == user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Demande introuvable")
    if record.statut not in ("DEMANDE", "BLOQUE"):
        raise HTTPException(400, f"Impossible de refuser : statut actuel = {record.statut}")

    record.statut = "REFUSE"
    record.motif_rejet = motif
    record.approuve_par = user.id
    record.date_decision = datetime.utcnow()

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="retrait_refuse", entity_type="retrait", entity_id=retrait_id,
    ))
    await db.commit()
    return {"id": retrait_id, "statut": "REFUSE", "message": f"Retrait refusé : {motif}"}


@router.get("/retraits")
async def list_retraits(
    associe_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    statut: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List withdrawal requests with optional filters."""
    q = select(RetraitAssocie).where(RetraitAssocie.tenant_id == user.tenant_id)
    if associe_id:
        q = q.where(RetraitAssocie.associe_id == associe_id)
    if projet_id:
        q = q.where(RetraitAssocie.projet_id == projet_id)
    if statut:
        q = q.where(RetraitAssocie.statut == statut)
    q = q.order_by(RetraitAssocie.created_at.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "associe_id": r.associe_id, "projet_id": r.projet_id,
            "montant": float(r.montant), "date_retrait": str(r.date_retrait),
            "description": r.description, "reference": r.reference,
            "statut": r.statut, "motif_rejet": r.motif_rejet,
            "solde_individuel": float(r.solde_individuel or 0),
            "max_autorise": float(r.max_autorise or 0),
            "solde_global_cca": float(r.solde_global_cca or 0),
            "approuve_par": r.approuve_par,
            "date_decision": str(r.date_decision) if r.date_decision else None,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in rows
    ]


@router.delete("/retraits/{retrait_id}")
async def delete_retrait(
    retrait_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel a DEMANDE retrait (cannot delete approved/executed)."""
    result = await db.execute(
        select(RetraitAssocie).where(
            RetraitAssocie.id == retrait_id,
            RetraitAssocie.tenant_id == user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Demande introuvable")
    if record.statut == "APPROUVE":
        raise HTTPException(400, "Impossible de supprimer un retrait déjà approuvé")
    await db.delete(record)
    await db.commit()
    return {"message": "Demande annulée"}


# ────────────────────────────────────────────────────────────────────────────
# Consolidation Associé
# ────────────────────────────────────────────────────────────────────────────

@router.get("/consolidation/associes")
async def consolidation_by_partner(
    associe_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    annee: Optional[int] = None,
    mois: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get monthly consolidation per partner."""
    q = select(ConsolidationAssocie).where(ConsolidationAssocie.tenant_id == user.tenant_id)
    if associe_id:
        q = q.where(ConsolidationAssocie.associe_id == associe_id)
    if projet_id:
        q = q.where(ConsolidationAssocie.projet_id == projet_id)
    if annee:
        q = q.where(ConsolidationAssocie.annee == annee)
    if mois:
        q = q.where(ConsolidationAssocie.mois == mois)
    q = q.order_by(ConsolidationAssocie.annee.desc(), ConsolidationAssocie.mois.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "associe_id": r.associe_id, "projet_id": r.projet_id,
            "mois": r.mois, "annee": r.annee,
            "pourcentage": float(r.pourcentage or 0),
            "capital_verse": float(r.capital_verse or 0),
            "retraits": float(r.retraits or 0),
            "quote_part_recettes": float(r.quote_part_recettes or 0),
            "quote_part_depenses": float(r.quote_part_depenses or 0),
            "quote_part_resultat": float(r.quote_part_resultat or 0),
            "position_nette": float(r.position_nette or 0),
            "alerte_negative": r.alerte_negative,
        }
        for r in rows
    ]


@router.post("/consolidation/compute")
async def compute_consolidation(
    entreprise_id: str,
    annee: int,
    mois: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compute/refresh monthly consolidation for all partners in a company."""
    # Get all projects for this company
    proj_result = await db.execute(
        select(Projet).where(
            Projet.entreprise_id == entreprise_id,
            Projet.tenant_id == user.tenant_id,
            Projet.is_active == True,
        )
    )
    projets = proj_result.scalars().all()

    # Get all associés for this company
    assoc_result = await db.execute(
        select(Associe).where(
            Associe.entreprise_id == entreprise_id,
            Associe.tenant_id == user.tenant_id,
            Associe.is_active == True,
        )
    )
    associes = assoc_result.scalars().all()

    computed = 0
    for projet in projets:
        for associe in associes:
            # Sum capital contributions
            cap_result = await db.execute(
                select(sa_func.coalesce(sa_func.sum(CapitalAssocie.montant), 0)).where(
                    CapitalAssocie.associe_id == associe.id,
                    CapitalAssocie.projet_id == projet.id,
                    CapitalAssocie.tenant_id == user.tenant_id,
                )
            )
            capital = float(cap_result.scalar())

            # Sum withdrawals
            ret_result = await db.execute(
                select(sa_func.coalesce(sa_func.sum(RetraitAssocie.montant), 0)).where(
                    RetraitAssocie.associe_id == associe.id,
                    RetraitAssocie.projet_id == projet.id,
                    RetraitAssocie.tenant_id == user.tenant_id,
                )
            )
            retraits = float(ret_result.scalar())

            position_nette = capital - retraits
            pct = float(associe.part_pct or 0)

            # Upsert consolidation record
            existing = await db.execute(
                select(ConsolidationAssocie).where(
                    ConsolidationAssocie.associe_id == associe.id,
                    ConsolidationAssocie.projet_id == projet.id,
                    ConsolidationAssocie.annee == annee,
                    ConsolidationAssocie.mois == mois,
                )
            )
            record = existing.scalar_one_or_none()
            if record:
                record.capital_verse = capital
                record.retraits = retraits
                record.pourcentage = pct
                record.position_nette = position_nette
                record.alerte_negative = position_nette < 0
            else:
                record = ConsolidationAssocie(
                    id=str(uuid.uuid4()),
                    tenant_id=user.tenant_id,
                    associe_id=associe.id,
                    projet_id=projet.id,
                    mois=mois,
                    annee=annee,
                    pourcentage=pct,
                    capital_verse=capital,
                    retraits=retraits,
                    position_nette=position_nette,
                    alerte_negative=position_nette < 0,
                )
                db.add(record)
            computed += 1

    await db.commit()
    return {"message": f"Computed {computed} consolidation records"}


@router.get("/consolidation/entreprises")
async def consolidation_by_company(
    entreprise_id: Optional[str] = None,
    annee: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(ConsolidationEntreprise).where(ConsolidationEntreprise.tenant_id == user.tenant_id)
    if entreprise_id:
        q = q.where(ConsolidationEntreprise.entreprise_id == entreprise_id)
    if annee:
        q = q.where(ConsolidationEntreprise.annee == annee)
    q = q.order_by(ConsolidationEntreprise.annee.desc(), ConsolidationEntreprise.mois.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "entreprise_id": r.entreprise_id,
            "mois": r.mois, "annee": r.annee,
            "total_recettes": float(r.total_recettes or 0),
            "total_depenses": float(r.total_depenses or 0),
            "total_resultat": float(r.total_resultat or 0),
            "nombre_projets_actifs": r.nombre_projets_actifs or 0,
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Bulletins de Paie
# ────────────────────────────────────────────────────────────────────────────

@router.post("/bulletins", status_code=201)
async def create_bulletin(
    body: BulletinCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a payroll bulletin with auto-computed deductions."""
    from app.services.cost_center_engine import calculer_irg

    brut = body.salaire_base + body.heures_sup + body.prime_rendement + body.indemnites
    cnas_sal = round(brut * 0.09, 2)
    imposable = brut - cnas_sal
    irg = calculer_irg(imposable)
    total_ret = cnas_sal + irg
    net = brut - total_ret
    cnas_pat = round(brut * 0.26, 2)
    cacobatph = round(brut * 0.0175, 2)
    cout_emp = brut + cnas_pat + cacobatph
    reel_total = net + body.complement_nd

    bulletin = BulletinPaie(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        employe_id=body.employe_id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        mois=body.mois,
        annee=body.annee,
        salaire_base=body.salaire_base,
        heures_sup=body.heures_sup,
        prime_rendement=body.prime_rendement,
        indemnites=body.indemnites,
        salaire_brut=brut,
        cnas_salarie=cnas_sal,
        irg=irg,
        total_retenues=total_ret,
        salaire_net=net,
        cnas_patronal=cnas_pat,
        cacobatph=cacobatph,
        cout_employeur_rd=cout_emp,
        complement_nd=body.complement_nd,
        salaire_reel_total=reel_total,
        created_by=user.id,
    )
    db.add(bulletin)
    await db.commit()
    await db.refresh(bulletin)
    return {
        "id": bulletin.id,
        "salaire_brut": float(brut),
        "cnas_salarie": float(cnas_sal),
        "irg": float(irg),
        "salaire_net": float(net),
        "cnas_patronal": float(cnas_pat),
        "cout_employeur_rd": float(cout_emp),
        "complement_nd": float(body.complement_nd),
        "salaire_reel_total": float(reel_total),
    }


@router.get("/bulletins")
async def list_bulletins(
    entreprise_id: Optional[str] = None,
    employe_id: Optional[str] = None,
    annee: Optional[int] = None,
    mois: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(BulletinPaie).where(BulletinPaie.tenant_id == user.tenant_id)
    if entreprise_id:
        q = q.where(BulletinPaie.entreprise_id == entreprise_id)
    if employe_id:
        q = q.where(BulletinPaie.employe_id == employe_id)
    if annee:
        q = q.where(BulletinPaie.annee == annee)
    if mois:
        q = q.where(BulletinPaie.mois == mois)
    q = q.order_by(BulletinPaie.annee.desc(), BulletinPaie.mois.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "employe_id": r.employe_id, "entreprise_id": r.entreprise_id,
            "mois": r.mois, "annee": r.annee,
            "salaire_base": float(r.salaire_base or 0),
            "salaire_brut": float(r.salaire_brut or 0),
            "salaire_net": float(r.salaire_net or 0),
            "complement_nd": float(r.complement_nd or 0),
            "salaire_reel_total": float(r.salaire_reel_total or 0),
            "cout_employeur_rd": float(r.cout_employeur_rd or 0),
            "statut": r.statut.value if r.statut else "BROUILLON",
        }
        for r in rows
    ]


@router.patch("/bulletins/{bulletin_id}/validate")
async def validate_bulletin(
    bulletin_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BulletinPaie).where(
            BulletinPaie.id == bulletin_id,
            BulletinPaie.tenant_id == user.tenant_id,
        )
    )
    bulletin = result.scalar_one_or_none()
    if not bulletin:
        raise HTTPException(404, "Bulletin not found")
    bulletin.statut = StatutBulletinPaie.VALIDE
    await db.commit()
    return {"message": "Bulletin validated"}


# ────────────────────────────────────────────────────────────────────────────
# Déclarations Fiscales
# ────────────────────────────────────────────────────────────────────────────

@router.post("/declarations", status_code=201)
async def create_declaration(
    body: DeclarationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tva_a_payer = body.montant_tva_collectee - body.montant_tva_deductible
    total = tva_a_payer + body.montant_tap + body.montant_irg_salaires
    decl = DeclarationFiscale(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        entreprise_id=body.entreprise_id,
        exercice_id=body.exercice_id,
        type_declaration=TypeDeclaration(body.type_declaration),
        mois=body.mois,
        annee=body.annee,
        montant_tva_collectee=body.montant_tva_collectee,
        montant_tva_deductible=body.montant_tva_deductible,
        montant_tva_a_payer=tva_a_payer,
        montant_tap=body.montant_tap,
        montant_irg_salaires=body.montant_irg_salaires,
        montant_total=total if body.montant_total == 0 else body.montant_total,
        created_by=user.id,
    )
    db.add(decl)
    await db.commit()
    await db.refresh(decl)
    return {"id": decl.id, "montant_total": float(decl.montant_total)}


@router.get("/declarations")
async def list_declarations(
    entreprise_id: Optional[str] = None,
    annee: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(DeclarationFiscale).where(DeclarationFiscale.tenant_id == user.tenant_id)
    if entreprise_id:
        q = q.where(DeclarationFiscale.entreprise_id == entreprise_id)
    if annee:
        q = q.where(DeclarationFiscale.annee == annee)
    q = q.order_by(DeclarationFiscale.annee.desc(), DeclarationFiscale.mois.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "entreprise_id": r.entreprise_id,
            "type_declaration": r.type_declaration.value if r.type_declaration else None,
            "mois": r.mois, "annee": r.annee,
            "montant_total": float(r.montant_total or 0),
            "statut": r.statut.value if r.statut else "BROUILLON",
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Comptes Bancaires
# ────────────────────────────────────────────────────────────────────────────

@router.post("/comptes-bancaires", status_code=201)
async def create_compte_bancaire(
    body: CompteBancaireCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cb = CompteBancaire(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        entreprise_id=body.entreprise_id,
        banque=body.banque,
        agence=body.agence,
        numero_compte=body.numero_compte,
        iban=body.iban,
        rib=body.rib,
    )
    db.add(cb)
    await db.commit()
    await db.refresh(cb)
    return {"id": cb.id}


@router.get("/comptes-bancaires")
async def list_comptes_bancaires(
    entreprise_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(CompteBancaire).where(
        CompteBancaire.tenant_id == user.tenant_id,
        CompteBancaire.actif == True,
    )
    if entreprise_id:
        q = q.where(CompteBancaire.entreprise_id == entreprise_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "entreprise_id": r.entreprise_id,
            "banque": r.banque, "agence": r.agence,
            "numero_compte": r.numero_compte, "iban": r.iban,
            "rib": r.rib, "devise": r.devise,
            "solde_actuel": float(r.solde_actuel or 0),
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Journaux Comptables
# ────────────────────────────────────────────────────────────────────────────

@router.post("/journaux", status_code=201)
async def create_journal(
    body: JournalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    j = Journal(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        entreprise_id=body.entreprise_id,
        code=body.code,
        libelle=body.libelle,
        type_journal=TypeJournal(body.type_journal),
    )
    db.add(j)
    await db.commit()
    await db.refresh(j)
    return {"id": j.id}


@router.get("/journaux")
async def list_journaux(
    entreprise_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Journal).where(
        Journal.tenant_id == user.tenant_id,
        Journal.actif == True,
    )
    if entreprise_id:
        q = q.where(Journal.entreprise_id == entreprise_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "entreprise_id": r.entreprise_id,
            "code": r.code, "libelle": r.libelle,
            "type_journal": r.type_journal.value if r.type_journal else None,
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Échéancier Clients
# ────────────────────────────────────────────────────────────────────────────

@router.post("/echeancier", status_code=201)
async def create_echeance(
    body: EcheancierCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ech = EcheancierClient(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        client_id=body.client_id,
        projet_id=body.projet_id,
        lot_id=body.lot_id,
        numero_echeance=body.numero_echeance,
        montant=body.montant,
        date_prevue=body.date_prevue,
    )
    db.add(ech)
    await db.commit()
    await db.refresh(ech)
    return {"id": ech.id}


@router.get("/echeancier")
async def list_echeancier(
    client_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    statut: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(EcheancierClient).where(EcheancierClient.tenant_id == user.tenant_id)
    if client_id:
        q = q.where(EcheancierClient.client_id == client_id)
    if projet_id:
        q = q.where(EcheancierClient.projet_id == projet_id)
    if statut:
        q = q.where(EcheancierClient.statut == StatutEcheance(statut))
    q = q.order_by(EcheancierClient.date_prevue)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "client_id": r.client_id, "projet_id": r.projet_id,
            "numero_echeance": r.numero_echeance,
            "montant": float(r.montant or 0),
            "date_prevue": str(r.date_prevue),
            "date_paiement": str(r.date_paiement) if r.date_paiement else None,
            "statut": r.statut.value if r.statut else "EN_ATTENTE",
            "jours_retard": r.jours_retard or 0,
            "alerte_envoyee": r.alerte_envoyee,
        }
        for r in rows
    ]


@router.patch("/echeancier/{echeance_id}/pay")
async def mark_echeance_paid(
    echeance_id: str,
    date_paiement: date = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a payment schedule entry as paid."""
    result = await db.execute(
        select(EcheancierClient).where(
            EcheancierClient.id == echeance_id,
            EcheancierClient.tenant_id == user.tenant_id,
        )
    )
    ech = result.scalar_one_or_none()
    if not ech:
        raise HTTPException(404, "Échéance not found")
    ech.statut = StatutEcheance.PAYE
    ech.date_paiement = date_paiement
    ech.jours_retard = max(0, (date_paiement - ech.date_prevue).days)
    await db.commit()
    return {"message": "Payment recorded"}
