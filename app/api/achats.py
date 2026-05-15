"""Achats, Stock & Logistique API — Section 11.

Full procurement cycle (EX-ACH-001):
  Demande d'achat → Bon de commande → Bon de réception → Facture fournisseur

Multi-warehouse inventory (EX-ACH-002):
  Entrepôts, mouvements de stock, valorisation CUMP
"""
import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User, AuditLog
from app.models.juridique import (
    DemandeAchat, LigneDemandeAchat, StatutDemande,
    CommandeAchat, StatutCommande,
    BonReception, FactureFournisseur,
    StockMateriel, Entrepot,
)

router = APIRouter(tags=["Achats & Stock"])


async def _proof_if_provided(file, action, context, user, db):
    if file and file.filename:
        from app.services.proof_verifier import verify_proof
        proof = await verify_proof(file, action, context, user.tenant_id, user.id, db)
        if not proof["verified"]:
            raise HTTPException(400, f"BLOCAGE : Document non conforme — {proof['rejection_reason']}")
        return proof
    return None


# ═══════════════════════════════════════════════════════════════════════════
# DEMANDES D'ACHAT (EX-ACH-001 step 1)
# ═══════════════════════════════════════════════════════════════════════════

class DemandeCreate(BaseModel):
    entreprise_id: str
    projet_id: Optional[str] = None
    reference: str
    objet: str
    description: Optional[str] = None
    montant_estime: float = 0
    urgence: str = "NORMALE"
    date_demande: date
    lignes: list[dict] = []  # [{designation, quantite, unite, prix_unitaire_estime}]


@router.get("/demandes")
async def list_demandes(
    statut: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(DemandeAchat).where(DemandeAchat.tenant_id == user.tenant_id)
    if statut:
        q = q.where(DemandeAchat.statut == statut)
    q = q.order_by(DemandeAchat.created_at.desc())
    result = await db.execute(q)
    items = []
    for d in result.scalars().all():
        lines_r = await db.execute(select(LigneDemandeAchat).where(LigneDemandeAchat.demande_id == d.id))
        lines = [{"designation": l.designation, "quantite": float(l.quantite), "unite": l.unite, "prix_unitaire": float(l.prix_unitaire_estime or 0)} for l in lines_r.scalars().all()]
        items.append({
            "id": d.id, "reference": d.reference, "objet": d.objet,
            "montant_estime": float(d.montant_estime or 0),
            "urgence": d.urgence, "statut": d.statut.value if d.statut else None,
            "date_demande": str(d.date_demande) if d.date_demande else None,
            "lignes": lines,
        })
    return items


@router.post("/demandes", status_code=201)
async def create_demande(
    body: DemandeCreate,
    file: Optional[UploadFile] = File(None, description="Justificatif (devis, spec technique)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proof = await _proof_if_provided(file, "demande_achat", {"montant": body.montant_estime, "action_detail": body.objet}, user, db)

    da = DemandeAchat(
        tenant_id=user.tenant_id, entreprise_id=body.entreprise_id,
        projet_id=body.projet_id, reference=body.reference,
        objet=body.objet, description=body.description,
        montant_estime=body.montant_estime, urgence=body.urgence,
        date_demande=body.date_demande, demandeur_id=user.id,
        document_id=proof["document_id"] if proof else None,
    )
    db.add(da)
    await db.flush()

    for l in body.lignes:
        db.add(LigneDemandeAchat(
            demande_id=da.id, designation=l.get("designation", ""),
            quantite=l.get("quantite", 1), unite=l.get("unite", "unité"),
            prix_unitaire_estime=l.get("prix_unitaire_estime", 0),
            montant_estime=l.get("quantite", 1) * l.get("prix_unitaire_estime", 0),
        ))

    await db.commit()
    return {"id": da.id, "reference": da.reference, "statut": "BROUILLON"}


@router.post("/demandes/{demande_id}/approuver")
async def approuver_demande(
    demande_id: str,
    file: Optional[UploadFile] = File(None, description="Approbation signée"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a purchase requisition (maker/checker — Socle S-08)."""
    result = await db.execute(select(DemandeAchat).where(DemandeAchat.id == demande_id, DemandeAchat.tenant_id == user.tenant_id))
    da = result.scalar_one_or_none()
    if not da:
        raise HTTPException(404, "Demande introuvable")
    if da.demandeur_id == user.id:
        raise HTTPException(400, "BLOCAGE Socle S-08 : le demandeur ne peut pas approuver sa propre demande (maker/checker)")
    if da.statut not in (StatutDemande.BROUILLON, StatutDemande.SOUMISE):
        raise HTTPException(400, f"Statut actuel: {da.statut.value}")

    await _proof_if_provided(file, "approuver_demande", {"action_detail": f"Approbation DA {da.reference}"}, user, db)

    da.statut = StatutDemande.APPROUVEE
    da.approbateur_id = user.id
    da.date_approbation = date.today()
    db.add(AuditLog(tenant_id=user.tenant_id, user_id=user.id, action="demande_approuvee", entity_type="demande_achat", entity_id=demande_id))
    await db.commit()
    return {"statut": "APPROUVEE"}


@router.post("/demandes/{demande_id}/rejeter")
async def rejeter_demande(
    demande_id: str, motif: str = Query(...),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DemandeAchat).where(DemandeAchat.id == demande_id, DemandeAchat.tenant_id == user.tenant_id))
    da = result.scalar_one_or_none()
    if not da:
        raise HTTPException(404, "Demande introuvable")
    da.statut = StatutDemande.REJETEE
    da.motif_rejet = motif
    await db.commit()
    return {"statut": "REJETEE", "motif": motif}


# ═══════════════════════════════════════════════════════════════════════════
# BONS DE RÉCEPTION (EX-ACH-001 step 3)
# ═══════════════════════════════════════════════════════════════════════════

class ReceptionCreate(BaseModel):
    entreprise_id: str
    projet_id: Optional[str] = None
    commande_id: Optional[str] = None
    reference: str
    date_reception: date
    fournisseur_id: Optional[str] = None
    quantite_commandee: float = 0
    quantite_recue: float = 0
    quantite_conforme: float = 0
    quantite_rejetee: float = 0
    entrepot_id: Optional[str] = None
    observations: Optional[str] = None


@router.get("/receptions")
async def list_receptions(
    commande_id: Optional[str] = None,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    q = select(BonReception).where(BonReception.tenant_id == user.tenant_id)
    if commande_id:
        q = q.where(BonReception.commande_id == commande_id)
    q = q.order_by(BonReception.created_at.desc())
    result = await db.execute(q)
    return [
        {
            "id": r.id, "reference": r.reference, "date_reception": str(r.date_reception),
            "quantite_commandee": float(r.quantite_commandee or 0),
            "quantite_recue": float(r.quantite_recue or 0),
            "quantite_conforme": float(r.quantite_conforme or 0),
            "quantite_rejetee": float(r.quantite_rejetee or 0),
            "statut": r.statut, "commande_id": r.commande_id,
        }
        for r in result.scalars().all()
    ]


@router.post("/receptions", status_code=201)
async def create_reception(
    body: ReceptionCreate,
    file: UploadFile = File(..., description="Bon de réception signé, PV de réception"),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    proof = await _proof_if_provided(file, "bon_reception", {"action_detail": f"Réception {body.reference}"}, user, db)

    statut = "CONFORME" if body.quantite_recue == body.quantite_commandee else ("PARTIEL" if body.quantite_recue > 0 else "REJETE")

    br = BonReception(
        tenant_id=user.tenant_id, entreprise_id=body.entreprise_id,
        projet_id=body.projet_id, commande_id=body.commande_id,
        reference=body.reference, date_reception=body.date_reception,
        fournisseur_id=body.fournisseur_id,
        quantite_commandee=body.quantite_commandee,
        quantite_recue=body.quantite_recue,
        quantite_conforme=body.quantite_conforme,
        quantite_rejetee=body.quantite_rejetee,
        statut=statut, observations=body.observations,
        receptionnaire_id=user.id, entrepot_id=body.entrepot_id,
        document_id=proof["document_id"] if proof else None,
    )
    db.add(br)

    # Update commande status if linked
    if body.commande_id:
        cmd_r = await db.execute(select(CommandeAchat).where(CommandeAchat.id == body.commande_id))
        cmd = cmd_r.scalar_one_or_none()
        if cmd and statut == "CONFORME":
            cmd.statut = StatutCommande.LIVREE
            cmd.date_livraison_effective = body.date_reception

    await db.commit()
    return {"id": br.id, "statut": statut}


# ═══════════════════════════════════════════════════════════════════════════
# FACTURES FOURNISSEUR (EX-ACH-001 step 4)
# ═══════════════════════════════════════════════════════════════════════════

class FactureCreate(BaseModel):
    entreprise_id: str
    fournisseur_id: str
    commande_id: Optional[str] = None
    reception_id: Optional[str] = None
    reference_facture: str
    date_facture: date
    date_echeance: Optional[date] = None
    montant_ht: float
    realite_financiere: str = "RF1"


@router.get("/factures-fournisseur")
async def list_factures(
    statut: Optional[str] = None,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    q = select(FactureFournisseur).where(FactureFournisseur.tenant_id == user.tenant_id)
    if statut:
        q = q.where(FactureFournisseur.statut == statut)
    q = q.order_by(FactureFournisseur.created_at.desc())
    result = await db.execute(q)
    return [
        {
            "id": f.id, "reference_facture": f.reference_facture,
            "date_facture": str(f.date_facture), "date_echeance": str(f.date_echeance) if f.date_echeance else None,
            "montant_ht": float(f.montant_ht or 0), "montant_ttc": float(f.montant_ttc or 0),
            "statut": f.statut, "realite_financiere": f.realite_financiere,
            "commande_id": f.commande_id, "reception_id": f.reception_id,
        }
        for f in result.scalars().all()
    ]


@router.post("/factures-fournisseur", status_code=201)
async def create_facture(
    body: FactureCreate,
    file: UploadFile = File(..., description="Facture fournisseur (PDF/image)"),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Create supplier invoice with AI verification and 3-way matching."""
    proof = await _proof_if_provided(file, "facture_fournisseur", {"montant": body.montant_ht, "action_detail": f"Facture {body.reference_facture}"}, user, db)

    ht = Decimal(str(body.montant_ht))
    tva = ht * Decimal("0.19")
    ttc = ht + tva

    # 3-way matching: check ecart with PO
    ecart_montant = Decimal(0)
    if body.commande_id:
        cmd_r = await db.execute(select(CommandeAchat).where(CommandeAchat.id == body.commande_id))
        cmd = cmd_r.scalar_one_or_none()
        if cmd:
            ecart_montant = ht - Decimal(str(cmd.montant_ht or 0))

    ff = FactureFournisseur(
        tenant_id=user.tenant_id, entreprise_id=body.entreprise_id,
        fournisseur_id=body.fournisseur_id, commande_id=body.commande_id,
        reception_id=body.reception_id, reference_facture=body.reference_facture,
        date_facture=body.date_facture, date_echeance=body.date_echeance,
        montant_ht=ht, montant_tva=tva, montant_ttc=ttc,
        realite_financiere=body.realite_financiere,
        ecart_montant=ecart_montant,
        document_id=proof["document_id"] if proof else None,
        created_by=user.id,
    )
    db.add(ff)
    await db.commit()
    await db.refresh(ff)

    return {
        "id": ff.id, "reference": ff.reference_facture,
        "montant_ttc": float(ttc), "ecart_montant": float(ecart_montant),
        "statut": ff.statut,
    }


@router.post("/factures-fournisseur/{facture_id}/valider")
async def valider_facture(
    facture_id: str,
    file: UploadFile = File(..., description="Bon pour accord signé"),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Validate supplier invoice — auto-generates journal entry D601/C401."""
    result = await db.execute(select(FactureFournisseur).where(FactureFournisseur.id == facture_id, FactureFournisseur.tenant_id == user.tenant_id))
    ff = result.scalar_one_or_none()
    if not ff:
        raise HTTPException(404, "Facture introuvable")

    await _proof_if_provided(file, "valider_facture_fournisseur", {"montant": float(ff.montant_ht or 0), "action_detail": f"Validation facture {ff.reference_facture}"}, user, db)

    ff.statut = "VALIDEE"
    ff.validee_par = user.id
    ff.date_validation = datetime.utcnow()

    # Auto journal entry
    from app.models.core import JournalEntry, JournalLine, JournalEntryStatus
    je = JournalEntry(
        id=str(_uuid.uuid4()), tenant_id=user.tenant_id,
        entreprise_id=ff.entreprise_id, entry_date=datetime.utcnow(),
        reference=f"FAF-{ff.reference_facture}",
        description=f"Facture fournisseur {ff.reference_facture}",
        status=JournalEntryStatus.COMMITTED,
        realite_financiere=ff.realite_financiere, auto_generated=True,
    )
    db.add(je)
    await db.flush()
    ff.journal_entry_id = je.id

    for i, (acc, label, d, c) in enumerate([
        ("601", f"Achats — {ff.reference_facture}", ff.montant_ht, Decimal(0)),
        ("4456", f"TVA déductible — {ff.reference_facture}", ff.montant_tva, Decimal(0)),
        ("401", f"Fournisseur — {ff.reference_facture}", Decimal(0), ff.montant_ttc),
    ], 1):
        db.add(JournalLine(id=str(_uuid.uuid4()), entry_id=je.id, line_no=i, account_code=acc, label=label, debit=d, credit=c))

    db.add(AuditLog(tenant_id=user.tenant_id, user_id=user.id, action="facture_fournisseur_validee", entity_type="facture_fournisseur", entity_id=facture_id))
    await db.commit()
    return {"statut": "VALIDEE", "journal_entry_id": je.id}


# ═══════════════════════════════════════════════════════════════════════════
# ENTREPÔTS (EX-ACH-002)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/entrepots")
async def list_entrepots(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Entrepot).where(Entrepot.tenant_id == user.tenant_id).order_by(Entrepot.code))
    return [{"id": e.id, "code": e.code, "designation": e.designation, "adresse": e.adresse, "projet_id": e.projet_id} for e in result.scalars().all()]


@router.post("/entrepots", status_code=201)
async def create_entrepot(
    code: str = Query(...), designation: str = Query(...),
    adresse: Optional[str] = Query(None), projet_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    e = Entrepot(tenant_id=user.tenant_id, code=code, designation=designation, adresse=adresse, projet_id=projet_id, responsable_id=user.id)
    db.add(e)
    await db.commit()
    return {"id": e.id, "code": e.code}


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def achats_dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    da_r = await db.execute(select(sa_func.count(DemandeAchat.id)).where(DemandeAchat.tenant_id == user.tenant_id))
    cmd_r = await db.execute(select(sa_func.count(CommandeAchat.id)).where(CommandeAchat.tenant_id == user.tenant_id))
    br_r = await db.execute(select(sa_func.count(BonReception.id)).where(BonReception.tenant_id == user.tenant_id))
    ff_r = await db.execute(select(sa_func.count(FactureFournisseur.id)).where(FactureFournisseur.tenant_id == user.tenant_id))
    stock_r = await db.execute(select(sa_func.coalesce(sa_func.sum(StockMateriel.valeur_totale), 0)).where(StockMateriel.tenant_id == user.tenant_id))
    alerte_r = await db.execute(select(sa_func.count(StockMateriel.id)).where(StockMateriel.tenant_id == user.tenant_id, StockMateriel.quantite <= StockMateriel.seuil_alerte))

    return {
        "demandes_achat": da_r.scalar() or 0,
        "bons_commande": cmd_r.scalar() or 0,
        "bons_reception": br_r.scalar() or 0,
        "factures_fournisseur": ff_r.scalar() or 0,
        "valeur_stock": float(stock_r.scalar() or 0),
        "alertes_stock": alerte_r.scalar() or 0,
    }
