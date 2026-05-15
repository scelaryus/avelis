"""GFI Platform — Centre de Coût & Financial API endpoints.

Provides:
- CRUD for Entreprises, Projets, Clients, Fournisseurs
- Encaissements & Décaissements (with D/ND/F)
- Centre de coût computation & display
- Ratio charges communes
- Mouvements caisse
- Paramètres système
- Consolidation views
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User, AuditLog
from app.models.financial import (
    Entreprise, Projet, Exercice, Encaissement, Decaissement,
    Parametre, RatioChargesCommunes, CentreCoutMensuel,
    ImputationPaieProjet, MouvementCaisse, MouvementStock,
    CompteTransitoireNotaire, ClientCC, Fournisseur, Lot,
    ArticleStock, Associe, BulletinPaieComplement,
    StatutFiscal, TypeCharge, CategorieDepense, SensOperation,
    StatutProjet, StatutLot, SensCaisse, TypeMouvementStock,
    MethodeRatio,
)
from app.services.cost_center_engine import (
    calculer_centre_cout_mensuel,
    calculer_ratio_charges_communes,
    recalculer_tous_centres_cout,
    format_centre_cout,
    calculer_irg,
)

router = APIRouter(tags=["Centre de Coût"])

# Shorthand → full enum mapping for fiscal status
_FISCAL_SHORTHAND = {
    "RD": StatutFiscal.REEL_DECLARE,
    "RND": StatutFiscal.REEL_NON_DECLARE,
    "D": StatutFiscal.REEL_DECLARE,
    "ND": StatutFiscal.REEL_NON_DECLARE,
    "F": StatutFiscal.FICTIF,
    "FD": StatutFiscal.FICTIF,
    "FND": StatutFiscal.FICTIF,
}

def _parse_statut_fiscal(val: str) -> StatutFiscal:
    normalized = (val or "").strip().upper()
    if normalized in _FISCAL_SHORTHAND:
        return _FISCAL_SHORTHAND[normalized]
    return StatutFiscal(normalized)


async def _get_entreprise_or_404(db: AsyncSession, tenant_id: str, entreprise_id: str) -> Entreprise:
    result = await db.execute(
        select(Entreprise).where(
            Entreprise.id == entreprise_id,
            Entreprise.tenant_id == tenant_id,
            Entreprise.is_active == True,
        )
    )
    entreprise = result.scalar_one_or_none()
    if not entreprise:
        raise HTTPException(status_code=404, detail="Entreprise not found")
    return entreprise


async def _get_projet_or_404(
    db: AsyncSession,
    tenant_id: str,
    projet_id: str,
    entreprise_id: Optional[str] = None,
) -> Projet:
    q = select(Projet).where(
        Projet.id == projet_id,
        Projet.tenant_id == tenant_id,
        Projet.is_active == True,
    )
    if entreprise_id:
        q = q.where(Projet.entreprise_id == entreprise_id)
    result = await db.execute(q)
    projet = result.scalar_one_or_none()
    if not projet:
        raise HTTPException(status_code=404, detail="Projet not found for this entreprise")
    return projet


async def _recalculate_cost_impact(
    db: AsyncSession,
    tenant_id: str,
    entreprise_id: str,
    projet_id: Optional[str],
    operation_date: Optional[date],
    type_charge: Optional[str] = None,
) -> None:
    if not operation_date:
        return
    if type_charge == "COMMUNE":
        await recalculer_tous_centres_cout(db, tenant_id, entreprise_id, operation_date.month, operation_date.year)
        return
    if projet_id:
        await calculer_centre_cout_mensuel(
            db, tenant_id, projet_id, entreprise_id, operation_date.month, operation_date.year
        )


# ────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ────────────────────────────────────────────────────────────────────────────

class EntrepriseCreate(BaseModel):
    raison_sociale: str
    nif: Optional[str] = None
    rc: Optional[str] = None
    nis: Optional[str] = None
    ai: Optional[str] = None
    adresse: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None

class ProjetCreate(BaseModel):
    entreprise_id: str
    code: str
    nom: str
    adresse: Optional[str] = None
    date_debut: Optional[date] = None
    budget_previsionnel: float = 0

class EncaissementCreate(BaseModel):
    entreprise_id: str
    projet_id: Optional[str] = None
    client_id: Optional[str] = None
    date_encaissement: date
    montant: float
    statut_fiscal: str  # D, ND or F
    moyen_paiement: Optional[str] = None
    reference: Optional[str] = None
    banque: Optional[str] = None
    description: Optional[str] = None

class DecaissementCreate(BaseModel):
    entreprise_id: str
    projet_id: Optional[str] = None
    fournisseur_id: Optional[str] = None
    date_decaissement: date
    montant: float
    montant_ht: Optional[float] = None
    montant_tva: Optional[float] = None
    taux_tva: Optional[float] = None
    statut_fiscal: str  # D, ND or F
    type_charge: str  # PROJET or COMMUNE
    categorie_depense: str = "AUTRE"
    sens: Optional[str] = None  # GAIN or PERTE (for CONTENTIEUX)
    reference_facture: Optional[str] = None
    description: Optional[str] = None
    moyen_paiement: Optional[str] = None

class ClientCreate(BaseModel):
    nom: str
    prenom: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    adresse: Optional[str] = None

class FournisseurCreate(BaseModel):
    code: str
    raison_sociale: str
    nif: Optional[str] = None
    rc: Optional[str] = None
    adresse: Optional[str] = None
    telephone: Optional[str] = None
    est_fictif: bool = False

class MouvementCaisseCreate(BaseModel):
    entreprise_id: str
    projet_id: Optional[str] = None
    date_mouvement: date
    sens: str  # ENTREE or SORTIE
    montant: float
    motif: str
    beneficiaire: Optional[str] = None
    reference_fiche: str
    statut_fiscal: str  # ND or F

class ParametreUpdate(BaseModel):
    cle: str
    valeur: str
    description: Optional[str] = None


# ────────────────────────────────────────────────────────────────────────────
# Entreprises
# ────────────────────────────────────────────────────────────────────────────

@router.get("/entreprises")
async def list_entreprises(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Entreprise).where(Entreprise.tenant_id == user.tenant_id).order_by(Entreprise.raison_sociale)
    )
    return [
        {"id": e.id, "raison_sociale": e.raison_sociale, "nif": e.nif, "rc": e.rc,
         "adresse": e.adresse, "telephone": e.telephone, "email": e.email, "is_active": e.is_active}
        for e in result.scalars().all()
    ]


@router.post("/entreprises", status_code=201)
async def create_entreprise(
    body: EntrepriseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = Entreprise(tenant_id=user.tenant_id, **body.model_dump())
    db.add(ent)
    await db.flush()
    return {"id": ent.id, "raison_sociale": ent.raison_sociale}


# ────────────────────────────────────────────────────────────────────────────
# Projets
# ────────────────────────────────────────────────────────────────────────────

@router.get("/projets")
async def list_projets(
    entreprise_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Projet).where(Projet.tenant_id == user.tenant_id)
    if entreprise_id:
        q = q.where(Projet.entreprise_id == entreprise_id)
    result = await db.execute(q.order_by(Projet.code))
    return [
        {"id": p.id, "entreprise_id": p.entreprise_id, "code": p.code, "nom": p.nom,
         "statut": p.statut.value if p.statut else None, "adresse": p.adresse,
         "budget_previsionnel": float(p.budget_previsionnel or 0), "is_active": p.is_active}
        for p in result.scalars().all()
    ]


@router.post("/projets", status_code=201)
async def create_projet(
    body: ProjetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_entreprise_or_404(db, user.tenant_id, body.entreprise_id)
    p = Projet(tenant_id=user.tenant_id, **body.model_dump())
    db.add(p)
    await db.flush()
    return {"id": p.id, "code": p.code, "nom": p.nom}


# ────────────────────────────────────────────────────────────────────────────
# Encaissements
# ────────────────────────────────────────────────────────────────────────────

@router.get("/encaissements")
async def list_encaissements(
    entreprise_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    statut_fiscal: Optional[str] = None,
    mois: Optional[int] = None,
    annee: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Encaissement).where(
        Encaissement.tenant_id == user.tenant_id,
        Encaissement.is_deleted == False,
    )
    if entreprise_id:
        q = q.where(Encaissement.entreprise_id == entreprise_id)
    if projet_id:
        q = q.where(Encaissement.projet_id == projet_id)
    if statut_fiscal:
        q = q.where(Encaissement.statut_fiscal == _parse_statut_fiscal(statut_fiscal))
    if mois and annee:
        date_debut = date(annee, mois, 1)
        date_fin = date(annee, mois + 1, 1) if mois < 12 else date(annee, 12, 31)
        q = q.where(Encaissement.date_encaissement >= date_debut, Encaissement.date_encaissement < date_fin)

    result = await db.execute(q.order_by(Encaissement.date_encaissement.desc()))
    return [
        {"id": e.id, "entreprise_id": e.entreprise_id, "projet_id": e.projet_id,
         "client_id": e.client_id, "date": e.date_encaissement.isoformat(),
         "montant": float(e.montant), "statut_fiscal": e.statut_fiscal.value,
         "moyen_paiement": e.moyen_paiement, "reference": e.reference, "banque": e.banque,
         "description": e.description}
        for e in result.scalars().all()
    ]


@router.post("/encaissements", status_code=201)
async def create_encaissement(
    body: EncaissementCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_entreprise_or_404(db, user.tenant_id, body.entreprise_id)
    if body.projet_id:
        await _get_projet_or_404(db, user.tenant_id, body.projet_id, body.entreprise_id)

    enc = Encaissement(
        tenant_id=user.tenant_id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        client_id=body.client_id,
        date_encaissement=body.date_encaissement,
        montant=body.montant,
        statut_fiscal=_parse_statut_fiscal(body.statut_fiscal),
        moyen_paiement=body.moyen_paiement,
        reference=body.reference,
        banque=body.banque,
        description=body.description,
        created_by=user.id,
    )
    db.add(enc)

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="encaissement_create", entity_type="encaissement", entity_id=enc.id,
    ))
    await db.flush()

    await _recalculate_cost_impact(
        db, user.tenant_id, body.entreprise_id, body.projet_id, body.date_encaissement
    )

    return {"id": enc.id, "montant": float(enc.montant), "statut_fiscal": enc.statut_fiscal.value}


@router.put("/encaissements/{encaissement_id}")
async def update_encaissement(
    encaissement_id: str,
    body: EncaissementCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_entreprise_or_404(db, user.tenant_id, body.entreprise_id)
    if body.projet_id:
        await _get_projet_or_404(db, user.tenant_id, body.projet_id, body.entreprise_id)

    result = await db.execute(
        select(Encaissement).where(
            Encaissement.id == encaissement_id,
            Encaissement.tenant_id == user.tenant_id,
            Encaissement.is_deleted == False,
        )
    )
    enc = result.scalar_one_or_none()
    if not enc:
        raise HTTPException(status_code=404, detail="Encaissement not found")

    old_entreprise_id = enc.entreprise_id
    old_projet_id = enc.projet_id
    old_date = enc.date_encaissement

    enc.entreprise_id = body.entreprise_id
    enc.projet_id = body.projet_id
    enc.client_id = body.client_id
    enc.date_encaissement = body.date_encaissement
    enc.montant = body.montant
    enc.statut_fiscal = _parse_statut_fiscal(body.statut_fiscal)
    enc.moyen_paiement = body.moyen_paiement
    enc.reference = body.reference
    enc.banque = body.banque
    enc.description = body.description

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="encaissement_update", entity_type="encaissement", entity_id=enc.id,
    ))
    await db.flush()

    await _recalculate_cost_impact(db, user.tenant_id, old_entreprise_id, old_projet_id, old_date)
    await _recalculate_cost_impact(db, user.tenant_id, body.entreprise_id, body.projet_id, body.date_encaissement)

    return {"id": enc.id, "montant": float(enc.montant), "statut_fiscal": enc.statut_fiscal.value}


# ────────────────────────────────────────────────────────────────────────────
# Décaissements
# ────────────────────────────────────────────────────────────────────────────

@router.get("/decaissements")
async def list_decaissements(
    entreprise_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    type_charge: Optional[str] = None,
    statut_fiscal: Optional[str] = None,
    mois: Optional[int] = None,
    annee: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Decaissement).where(
        Decaissement.tenant_id == user.tenant_id,
        Decaissement.is_deleted == False,
    )
    if entreprise_id:
        q = q.where(Decaissement.entreprise_id == entreprise_id)
    if projet_id:
        q = q.where(Decaissement.projet_id == projet_id)
    if type_charge:
        q = q.where(Decaissement.type_charge == TypeCharge(type_charge))
    if statut_fiscal:
        q = q.where(Decaissement.statut_fiscal == _parse_statut_fiscal(statut_fiscal))
    if mois and annee:
        date_debut = date(annee, mois, 1)
        date_fin = date(annee, mois + 1, 1) if mois < 12 else date(annee, 12, 31)
        q = q.where(Decaissement.date_decaissement >= date_debut, Decaissement.date_decaissement < date_fin)

    result = await db.execute(q.order_by(Decaissement.date_decaissement.desc()))
    return [
        {"id": d.id, "entreprise_id": d.entreprise_id, "projet_id": d.projet_id,
         "fournisseur_id": d.fournisseur_id, "date": d.date_decaissement.isoformat(),
         "montant": float(d.montant), "statut_fiscal": d.statut_fiscal.value,
         "type_charge": d.type_charge.value, "categorie_depense": d.categorie_depense.value if d.categorie_depense else None,
         "sens": d.sens.value if d.sens else None, "description": d.description,
         "reference_facture": d.reference_facture, "moyen_paiement": d.moyen_paiement,
         "montant_ht": float(d.montant_ht) if d.montant_ht is not None else None,
         "montant_tva": float(d.montant_tva) if d.montant_tva is not None else None,
         "taux_tva": float(d.taux_tva) if d.taux_tva is not None else None}
        for d in result.scalars().all()
    ]


@router.post("/decaissements", status_code=201)
async def create_decaissement(
    body: DecaissementCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_entreprise_or_404(db, user.tenant_id, body.entreprise_id)

    # Validation: if type_charge is PROJET, projet_id must be set
    if body.type_charge == "PROJET" and not body.projet_id:
        raise HTTPException(
            status_code=400,
            detail="BLOCAGE: type_charge PROJET requires a projet_id. Choose a project or set type_charge to COMMUNE.",
        )

    # Validation: if type_charge is COMMUNE, projet_id must be NULL
    if body.type_charge == "COMMUNE" and body.projet_id:
        raise HTTPException(
            status_code=400,
            detail="BLOCAGE: charge COMMUNE cannot have a projet_id.",
        )

    if body.projet_id:
        await _get_projet_or_404(db, user.tenant_id, body.projet_id, body.entreprise_id)

    # TVA verification (Chapter 8.3: tolerance = 0.00 DA)
    if body.montant_ht and body.montant_tva and body.taux_tva:
        expected_tva = round(body.montant_ht * body.taux_tva / 100, 2)
        if abs(body.montant_tva - expected_tva) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"BLOCAGE: TVA incohérente. Attendu {expected_tva}, reçu {body.montant_tva}.",
            )
        expected_ttc = round(body.montant_ht + body.montant_tva, 2)
        if abs(body.montant - expected_ttc) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"BLOCAGE: TTC incohérent. HT({body.montant_ht}) + TVA({body.montant_tva}) ≠ TTC({body.montant}).",
            )

    dec = Decaissement(
        tenant_id=user.tenant_id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        fournisseur_id=body.fournisseur_id,
        date_decaissement=body.date_decaissement,
        montant=body.montant,
        montant_ht=body.montant_ht,
        montant_tva=body.montant_tva,
        taux_tva=body.taux_tva,
        statut_fiscal=_parse_statut_fiscal(body.statut_fiscal),
        type_charge=TypeCharge(body.type_charge),
        categorie_depense=CategorieDepense(body.categorie_depense),
        sens=SensOperation(body.sens) if body.sens else None,
        reference_facture=body.reference_facture,
        description=body.description,
        moyen_paiement=body.moyen_paiement,
        created_by=user.id,
    )
    db.add(dec)

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="decaissement_create", entity_type="decaissement", entity_id=dec.id,
    ))
    await db.flush()

    await _recalculate_cost_impact(
        db, user.tenant_id, body.entreprise_id, body.projet_id, body.date_decaissement, body.type_charge
    )

    return {"id": dec.id, "montant": float(dec.montant), "statut_fiscal": dec.statut_fiscal.value,
            "type_charge": dec.type_charge.value}


@router.put("/decaissements/{decaissement_id}")
async def update_decaissement(
    decaissement_id: str,
    body: DecaissementCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_entreprise_or_404(db, user.tenant_id, body.entreprise_id)

    if body.type_charge == "PROJET" and not body.projet_id:
        raise HTTPException(status_code=400, detail="BLOCAGE: type_charge PROJET requires a projet_id.")
    if body.type_charge == "COMMUNE" and body.projet_id:
        raise HTTPException(status_code=400, detail="BLOCAGE: charge COMMUNE cannot have a projet_id.")
    if body.projet_id:
        await _get_projet_or_404(db, user.tenant_id, body.projet_id, body.entreprise_id)
    if body.montant_ht and body.montant_tva and body.taux_tva:
        expected_tva = round(body.montant_ht * body.taux_tva / 100, 2)
        if abs(body.montant_tva - expected_tva) > 0.01:
            raise HTTPException(status_code=400, detail=f"BLOCAGE: TVA incohérente. Attendu {expected_tva}, reçu {body.montant_tva}.")
        expected_ttc = round(body.montant_ht + body.montant_tva, 2)
        if abs(body.montant - expected_ttc) > 0.01:
            raise HTTPException(status_code=400, detail=f"BLOCAGE: TTC incohérent. HT({body.montant_ht}) + TVA({body.montant_tva}) ≠ TTC({body.montant}).")

    result = await db.execute(
        select(Decaissement).where(
            Decaissement.id == decaissement_id,
            Decaissement.tenant_id == user.tenant_id,
            Decaissement.is_deleted == False,
        )
    )
    dec = result.scalar_one_or_none()
    if not dec:
        raise HTTPException(status_code=404, detail="Décaissement not found")

    old_entreprise_id = dec.entreprise_id
    old_projet_id = dec.projet_id
    old_date = dec.date_decaissement
    old_type_charge = dec.type_charge.value if dec.type_charge else None

    dec.entreprise_id = body.entreprise_id
    dec.projet_id = body.projet_id
    dec.fournisseur_id = body.fournisseur_id
    dec.date_decaissement = body.date_decaissement
    dec.montant = body.montant
    dec.montant_ht = body.montant_ht
    dec.montant_tva = body.montant_tva
    dec.taux_tva = body.taux_tva
    dec.statut_fiscal = _parse_statut_fiscal(body.statut_fiscal)
    dec.type_charge = TypeCharge(body.type_charge)
    dec.categorie_depense = CategorieDepense(body.categorie_depense)
    dec.sens = SensOperation(body.sens) if body.sens else None
    dec.reference_facture = body.reference_facture
    dec.description = body.description
    dec.moyen_paiement = body.moyen_paiement

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="decaissement_update", entity_type="decaissement", entity_id=dec.id,
    ))
    await db.flush()

    await _recalculate_cost_impact(db, user.tenant_id, old_entreprise_id, old_projet_id, old_date, old_type_charge)
    await _recalculate_cost_impact(db, user.tenant_id, body.entreprise_id, body.projet_id, body.date_decaissement, body.type_charge)

    return {"id": dec.id, "montant": float(dec.montant), "statut_fiscal": dec.statut_fiscal.value,
            "type_charge": dec.type_charge.value}


# ────────────────────────────────────────────────────────────────────────────
# Clients
# ────────────────────────────────────────────────────────────────────────────

@router.get("/clients")
async def list_clients(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClientCC).where(ClientCC.tenant_id == user.tenant_id).order_by(ClientCC.nom)
    )
    return [
        {"id": c.id, "nom": c.nom, "prenom": c.prenom, "telephone": c.telephone, "email": c.email}
        for c in result.scalars().all()
    ]


@router.post("/clients", status_code=201)
async def create_client(
    body: ClientCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = ClientCC(tenant_id=user.tenant_id, **body.model_dump())
    db.add(c)
    await db.flush()
    return {"id": c.id, "nom": c.nom}


# ────────────────────────────────────────────────────────────────────────────
# Fournisseurs
# ────────────────────────────────────────────────────────────────────────────

@router.get("/fournisseurs")
async def list_fournisseurs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Fournisseur).where(Fournisseur.tenant_id == user.tenant_id).order_by(Fournisseur.raison_sociale)
    )
    return [
        {"id": f.id, "code": f.code, "raison_sociale": f.raison_sociale, "nif": f.nif,
         "est_fictif": f.est_fictif, "is_active": f.is_active}
        for f in result.scalars().all()
    ]


@router.post("/fournisseurs", status_code=201)
async def create_fournisseur(
    body: FournisseurCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    f = Fournisseur(tenant_id=user.tenant_id, **body.model_dump())
    db.add(f)
    await db.flush()
    return {"id": f.id, "code": f.code, "raison_sociale": f.raison_sociale}


# ────────────────────────────────────────────────────────────────────────────
# Mouvements Caisse
# ────────────────────────────────────────────────────────────────────────────

@router.get("/caisse")
async def list_mouvements_caisse(
    entreprise_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    mois: Optional[int] = None,
    annee: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(MouvementCaisse).where(MouvementCaisse.tenant_id == user.tenant_id)
    if entreprise_id:
        q = q.where(MouvementCaisse.entreprise_id == entreprise_id)
    if projet_id:
        q = q.where(MouvementCaisse.projet_id == projet_id)
    if mois and annee:
        date_debut = date(annee, mois, 1)
        date_fin = date(annee, mois + 1, 1) if mois < 12 else date(annee, 12, 31)
        q = q.where(MouvementCaisse.date_mouvement >= date_debut, MouvementCaisse.date_mouvement < date_fin)

    result = await db.execute(q.order_by(MouvementCaisse.date_mouvement))
    items = result.scalars().all()

    total_entrees = sum(float(m.montant) for m in items if m.sens == SensCaisse.ENTREE)
    total_sorties = sum(float(m.montant) for m in items if m.sens == SensCaisse.SORTIE)

    return {
        "mouvements": [
            {"id": m.id, "date": m.date_mouvement.isoformat(), "sens": m.sens.value,
             "montant": float(m.montant), "motif": m.motif, "beneficiaire": m.beneficiaire,
             "reference_fiche": m.reference_fiche, "solde_avant": float(m.solde_avant or 0),
             "solde_apres": float(m.solde_apres or 0)}
            for m in items
        ],
        "total_entrees": total_entrees,
        "total_sorties": total_sorties,
        "variation": total_entrees - total_sorties,
    }


@router.post("/caisse", status_code=201)
async def create_mouvement_caisse(
    body: MouvementCaisseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Calculate running balance
    r = await db.execute(
        select(MouvementCaisse.solde_apres).where(
            MouvementCaisse.entreprise_id == body.entreprise_id,
        ).order_by(MouvementCaisse.date_mouvement.desc(), MouvementCaisse.created_at.desc()).limit(1)
    )
    last_solde = r.scalar_one_or_none()
    solde_avant = float(last_solde) if last_solde else 0.0

    if body.sens == "SORTIE" and solde_avant < body.montant:
        raise HTTPException(status_code=400, detail="BLOCAGE: Solde caisse insuffisant.")

    solde_apres = solde_avant + body.montant if body.sens == "ENTREE" else solde_avant - body.montant

    mv = MouvementCaisse(
        tenant_id=user.tenant_id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        date_mouvement=body.date_mouvement,
        sens=SensCaisse(body.sens),
        montant=body.montant,
        motif=body.motif,
        beneficiaire=body.beneficiaire,
        reference_fiche=body.reference_fiche,
        solde_avant=solde_avant,
        solde_apres=solde_apres,
        statut_fiscal=_parse_statut_fiscal(body.statut_fiscal),
        created_by=user.id,
    )
    db.add(mv)
    await db.flush()
    return {"id": mv.id, "solde_apres": solde_apres}


# ────────────────────────────────────────────────────────────────────────────
# Paramètres système
# ────────────────────────────────────────────────────────────────────────────

@router.get("/parametres")
async def list_parametres(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Parametre).where(Parametre.tenant_id == user.tenant_id).order_by(Parametre.cle)
    )
    return [{"id": p.id, "cle": p.cle, "valeur": p.valeur, "description": p.description}
            for p in result.scalars().all()]


@router.put("/parametres")
async def upsert_parametre(
    body: ParametreUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Parametre).where(Parametre.tenant_id == user.tenant_id, Parametre.cle == body.cle)
    )
    p = result.scalar_one_or_none()
    if p:
        p.valeur = body.valeur
        if body.description:
            p.description = body.description
    else:
        p = Parametre(tenant_id=user.tenant_id, cle=body.cle, valeur=body.valeur, description=body.description)
        db.add(p)
    await db.flush()
    return {"cle": p.cle, "valeur": p.valeur}


# ────────────────────────────────────────────────────────────────────────────
# Centre de Coût — Core endpoints
# ────────────────────────────────────────────────────────────────────────────

@router.post("/centre-cout/recalculer")
async def recalculer_centre_cout(
    entreprise_id: str = Query(...),
    mois: int = Query(..., ge=1, le=12),
    annee: int = Query(..., ge=2020),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force recalculation of all cost centers for an entreprise/month (double computation)."""
    await _get_entreprise_or_404(db, user.tenant_id, entreprise_id)
    results = await recalculer_tous_centres_cout(db, user.tenant_id, entreprise_id, mois, annee)
    return {
        "count": len(results),
        "projets": [format_centre_cout(cc) for cc in results],
    }


@router.get("/centre-cout/consolide")
async def get_consolidation(
    entreprise_id: str = Query(...),
    mois: int = Query(..., ge=1, le=12),
    annee: int = Query(..., ge=2020),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get consolidated cost center view across all projects of an entreprise (Ch. 6.3)."""
    await _get_entreprise_or_404(db, user.tenant_id, entreprise_id)
    result = await db.execute(
        select(CentreCoutMensuel).where(
            CentreCoutMensuel.tenant_id == user.tenant_id,
            CentreCoutMensuel.entreprise_id == entreprise_id,
            CentreCoutMensuel.annee == annee,
            CentreCoutMensuel.mois == mois,
        ).order_by(CentreCoutMensuel.resultat_ultra_reel.desc())
    )
    centres = result.scalars().all()

    # Fetch project codes for display
    proj_ids = [cc.projet_id for cc in centres]
    proj_result = await db.execute(
        select(Projet).where(Projet.tenant_id == user.tenant_id, Projet.id.in_(proj_ids))
    )
    proj_map = {p.id: p for p in proj_result.scalars().all()}

    projets = []
    totals = {
        "recettes": 0.0, "depenses_directes": 0.0, "charges_communes": 0.0,
        "total_depenses": 0.0, "resultat": 0.0,
    }

    for cc in centres:
        p = proj_map.get(cc.projet_id)
        row = {
            "projet_id": cc.projet_id,
            "projet_code": p.code if p else "?",
            "projet_nom": p.nom if p else "?",
            "recettes": float(cc.total_recettes or 0),
            "depenses_directes": float(cc.total_depenses_directes or 0),
            "charges_communes": float(cc.charges_communes_montant or 0),
            "total_depenses": float(cc.total_depenses or 0),
            "resultat": float(cc.resultat_ultra_reel or 0),
            "marge_pct": float(cc.marge_brute_pct or 0),
        }
        projets.append(row)
        totals["recettes"] += row["recettes"]
        totals["depenses_directes"] += row["depenses_directes"]
        totals["charges_communes"] += row["charges_communes"]
        totals["total_depenses"] += row["total_depenses"]
        totals["resultat"] += row["resultat"]

    totals["marge_pct"] = round(
        totals["resultat"] / totals["recettes"] * 100, 2
    ) if totals["recettes"] > 0 else 0.0

    ent = await db.execute(select(Entreprise).where(Entreprise.id == entreprise_id))
    entreprise = ent.scalar_one_or_none()

    return {
        "entreprise": entreprise.raison_sociale if entreprise else entreprise_id,
        "periode": f"{annee}-{mois:02d}",
        "projets": projets,
        "totaux": totals,
    }


@router.get("/centre-cout/{projet_id}")
async def get_centre_cout(
    projet_id: str,
    mois: int = Query(..., ge=1, le=12),
    annee: int = Query(..., ge=2020),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get centre de coût for a specific project & month. Auto-calculates if missing."""
    projet = await _get_projet_or_404(db, user.tenant_id, projet_id)

    cc = await calculer_centre_cout_mensuel(
        db, user.tenant_id, projet_id, projet.entreprise_id, mois, annee
    )
    return format_centre_cout(cc)


# ────────────────────────────────────────────────────────────────────────────
# Ratio Charges Communes
# ────────────────────────────────────────────────────────────────────────────

@router.get("/ratio-charges-communes")
async def get_ratio(
    entreprise_id: str = Query(...),
    mois: int = Query(..., ge=1, le=12),
    annee: int = Query(..., ge=2020),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get or calculate the common charge ratio for a given month."""
    await _get_entreprise_or_404(db, user.tenant_id, entreprise_id)
    ratio = await calculer_ratio_charges_communes(
        db, user.tenant_id, entreprise_id, mois, annee
    )
    return {
        "id": ratio.id,
        "entreprise_id": ratio.entreprise_id,
        "mois": ratio.mois,
        "annee": ratio.annee,
        "methode": ratio.methode.value if ratio.methode else "CA",
        "detail_projets": ratio.detail_projets,
        "total_base": float(ratio.total_base or 0),
        "total_charges_communes": float(ratio.total_charges_communes or 0),
        "somme_ratios": float(ratio.somme_ratios or 0),
    }


# ────────────────────────────────────────────────────────────────────────────
# Dashboard summary (Ch. 6.1)
# ────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    entreprise_id: Optional[str] = None,
    mois: Optional[int] = None,
    annee: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard summary with key metrics from Ch. 6.1."""
    from datetime import datetime as dt
    now = dt.now()
    if not mois:
        mois = now.month
    if not annee:
        annee = now.year

    if entreprise_id:
        await _get_entreprise_or_404(db, user.tenant_id, entreprise_id)

    # Count active projects
    q = select(sa_func.count(Projet.id)).where(
        Projet.tenant_id == user.tenant_id,
        Projet.statut == StatutProjet.ACTIF,
    )
    if entreprise_id:
        q = q.where(Projet.entreprise_id == entreprise_id)
    r = await db.execute(q)
    nb_projets = r.scalar()

    # Count clients
    r = await db.execute(
        select(sa_func.count(ClientCC.id)).where(ClientCC.tenant_id == user.tenant_id)
    )
    nb_clients = r.scalar()

    # Total CA this month (encaissements RD + RND)
    date_debut = date(annee, mois, 1)
    date_fin = date(annee, mois + 1, 1) if mois < 12 else date(annee, 12, 31)
    q = select(sa_func.coalesce(sa_func.sum(Encaissement.montant), 0)).where(
        Encaissement.tenant_id == user.tenant_id,
        Encaissement.date_encaissement >= date_debut,
        Encaissement.date_encaissement < date_fin,
        Encaissement.is_deleted == False,
    )
    if entreprise_id:
        q = q.where(Encaissement.entreprise_id == entreprise_id)
    r = await db.execute(q)
    ca_mois = float(r.scalar())

    # Transit notaire en attente
    q = select(sa_func.coalesce(
        sa_func.sum(CompteTransitoireNotaire.montant_tranche1_20pct + CompteTransitoireNotaire.montant_tranche2_5pct), 0
    )).where(
        CompteTransitoireNotaire.tenant_id == user.tenant_id,
        CompteTransitoireNotaire.statut != "CLOTURE",
    )
    r = await db.execute(q)
    transit_total = float(r.scalar())

    # Total résultat from CentreCoutMensuel this month
    q = select(sa_func.coalesce(sa_func.sum(CentreCoutMensuel.resultat_ultra_reel), 0)).where(
        CentreCoutMensuel.tenant_id == user.tenant_id,
        CentreCoutMensuel.annee == annee,
        CentreCoutMensuel.mois == mois,
    )
    if entreprise_id:
        q = q.where(CentreCoutMensuel.entreprise_id == entreprise_id)
    r = await db.execute(q)
    resultat_mois = float(r.scalar())

    return {
        "periode": f"{annee}-{mois:02d}",
        "nb_projets_actifs": nb_projets,
        "nb_clients": nb_clients,
        "ca_mois": ca_mois,
        "transit_notaire": transit_total,
        "resultat_mois": resultat_mois,
    }


# ────────────────────────────────────────────────────────────────────────────
# Seed default parametres
# ────────────────────────────────────────────────────────────────────────────

@router.post("/parametres/seed")
async def seed_parametres(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seed all default system parameters from Chapter 9."""
    defaults = [
        ("taux_tva_normal", "19", "Taux TVA normal (%)"),
        ("taux_tva_reduit", "9", "Taux TVA réduit (%)"),
        ("taux_tap", "2", "Taux TAP (%)"),
        ("taux_ibs", "19", "Taux IBS sociétés (%)"),
        ("cnas_taux_salarie", "9", "CNAS part salariale (%)"),
        ("cnas_taux_patronal", "26", "CNAS part patronale (%)"),
        ("cacobatph_taux", "1.75", "CACOBATPH BTP (%)"),
        ("casnos_taux", "15", "CASNOS dirigeants (%)"),
        ("taux_cout_fictif", "3", "Coût réel des factures fictives (%)"),
        ("methode_ratio_charges_communes", "CA", "Méthode ratio : CA ou DEPENSES"),
        ("delta_tolerance_da", "0.00", "Delta toléré double computation (DA)"),
        ("alerte_retard_j1", "30", "Première alerte retard (jours)"),
        ("alerte_retard_j2", "60", "Deuxième alerte retard (jours)"),
        ("alerte_retard_j3", "90", "Troisième alerte retard (jours)"),
        ("transit_tranche1_pct", "20", "Tranche 1 notaire (%)"),
        ("transit_tranche2_pct", "5", "Tranche 2 notaire (%)"),
        ("transit_direct_pct", "75", "Part directe banque (%)"),
        ("methode_valorisation_stock", "CUMP", "Méthode valorisation stock"),
        ("seuil_alerte_stock", "10", "Seuil alerte stock minimum (%)"),
        ("devise_principale", "DZD", "Devise par défaut"),
        ("symbole_devise", "DA", "Symbole devise affiché"),
    ]
    count = 0
    for cle, val, desc in defaults:
        existing = await db.execute(
            select(Parametre).where(Parametre.tenant_id == user.tenant_id, Parametre.cle == cle)
        )
        if not existing.scalar_one_or_none():
            db.add(Parametre(tenant_id=user.tenant_id, cle=cle, valeur=val, description=desc))
            count += 1
    await db.flush()
    return {"seeded": count, "total": len(defaults)}
