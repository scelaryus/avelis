"""GFI Platform — Registry & Real Estate API endpoints.

Provides:
- Notaires CRUD
- Banques partenaires CRUD
- Projet ↔ Notaire / Banque assignments
- Parts projets (ownership shares)
- Mutations foncières (land mutation chains)
- Lots immobiliers (real estate EDD stock)
- Projet entreprise historique (OPERA transitions)
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User
from app.models.registry import (
    Notaire, BanquePartenaire, ProjetNotaire, ProjetBanque,
    PartProjet, MutationFonciere, LotImmobilier,
    ProjetEntrepriseHistorique, DossierFictifReference,
    TypeMutation, TypeCedant, StatutLotImmo, TypeBien,
    TypeTransition,
)

router = APIRouter(tags=["Registry & Real Estate"])


# ────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ────────────────────────────────────────────────────────────────────────────

class NotaireCreate(BaseModel):
    nom: str
    prenom: Optional[str] = None
    titre: str = "Maître"
    adresse: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None

class BanqueCreate(BaseModel):
    code: str
    nom_banque: str
    agence: Optional[str] = None
    adresse: Optional[str] = None
    telephone: Optional[str] = None

class ProjetNotaireCreate(BaseModel):
    projet_id: str
    notaire_id: str
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None

class ProjetBanqueCreate(BaseModel):
    projet_id: str
    banque_id: str
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None

class PartProjetCreate(BaseModel):
    projet_id: str
    associe_id: str
    pourcentage: float = Field(gt=0, le=100)
    montant_apport: float = 0

class MutationCreate(BaseModel):
    projet_id: str
    type_mutation: str
    cedant_id: Optional[str] = None
    cedant_type: Optional[str] = None
    cessionnaire_id: Optional[str] = None
    cessionnaire_type: Optional[str] = None
    date_mutation: Optional[date] = None
    montant: Optional[float] = None
    reference_acte: Optional[str] = None
    description: Optional[str] = None
    ordre: int = 0

class LotImmoCreate(BaseModel):
    projet_id: str
    bloc: str
    etage: str
    numero_lot: str
    type_bien: str
    surface: float = Field(gt=0)
    prix: float = Field(ge=0)
    notes: Optional[str] = None

class ProjetEntrepriseHistCreate(BaseModel):
    projet_id: str
    entreprise_id: str
    date_debut: date
    date_fin: Optional[date] = None
    type_transition: Optional[str] = None
    reference_acte: Optional[str] = None
    notes: Optional[str] = None


# ────────────────────────────────────────────────────────────────────────────
# Notaires
# ────────────────────────────────────────────────────────────────────────────

@router.post("/notaires", status_code=201)
async def create_notaire(
    body: NotaireCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = Notaire(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        nom=body.nom,
        prenom=body.prenom,
        titre=body.titre,
        adresse=body.adresse,
        telephone=body.telephone,
        email=body.email,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return {"id": n.id, "nom": n.nom}


@router.get("/notaires")
async def list_notaires(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notaire).where(
            Notaire.tenant_id == user.tenant_id,
            Notaire.actif == True,
        )
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "nom": r.nom, "prenom": r.prenom,
            "titre": r.titre, "telephone": r.telephone, "email": r.email,
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Banques Partenaires
# ────────────────────────────────────────────────────────────────────────────

@router.post("/banques", status_code=201)
async def create_banque(
    body: BanqueCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    b = BanquePartenaire(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        code=body.code,
        nom_banque=body.nom_banque,
        agence=body.agence,
        adresse=body.adresse,
        telephone=body.telephone,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return {"id": b.id, "code": b.code}


@router.get("/banques")
async def list_banques(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BanquePartenaire).where(
            BanquePartenaire.tenant_id == user.tenant_id,
            BanquePartenaire.actif == True,
        )
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "code": r.code, "nom_banque": r.nom_banque,
            "agence": r.agence, "telephone": r.telephone,
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Projet ↔ Notaire Assignments
# ────────────────────────────────────────────────────────────────────────────

@router.post("/projet-notaires", status_code=201)
async def assign_notaire_to_projet(
    body: ProjetNotaireCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pn = ProjetNotaire(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        notaire_id=body.notaire_id,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
    )
    db.add(pn)
    await db.commit()
    return {"id": pn.id}


@router.get("/projet-notaires")
async def list_projet_notaires(
    projet_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(ProjetNotaire).where(ProjetNotaire.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(ProjetNotaire.projet_id == projet_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "projet_id": r.projet_id, "notaire_id": r.notaire_id,
            "date_debut": str(r.date_debut) if r.date_debut else None,
            "date_fin": str(r.date_fin) if r.date_fin else None,
            "actif": r.actif,
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Projet ↔ Banque Assignments
# ────────────────────────────────────────────────────────────────────────────

@router.post("/projet-banques", status_code=201)
async def assign_banque_to_projet(
    body: ProjetBanqueCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pb = ProjetBanque(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        banque_id=body.banque_id,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
    )
    db.add(pb)
    await db.commit()
    return {"id": pb.id}


@router.get("/projet-banques")
async def list_projet_banques(
    projet_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(ProjetBanque).where(ProjetBanque.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(ProjetBanque.projet_id == projet_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "projet_id": r.projet_id, "banque_id": r.banque_id,
            "date_debut": str(r.date_debut) if r.date_debut else None,
            "date_fin": str(r.date_fin) if r.date_fin else None,
            "actif": r.actif,
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Parts Projets (ownership shares)
# ────────────────────────────────────────────────────────────────────────────

@router.post("/parts-projets", status_code=201)
async def create_part(
    body: PartProjetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from decimal import Decimal
    from app.services.blocking_rules import validate_project_shares_sum
    await validate_project_shares_sum(
        body.projet_id, db,
        new_pourcentage=Decimal(str(body.pourcentage)),
    )

    pp = PartProjet(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        associe_id=body.associe_id,
        pourcentage=body.pourcentage,
        montant_apport=body.montant_apport,
    )
    db.add(pp)
    await db.commit()
    return {"id": pp.id}


@router.get("/parts-projets")
async def list_parts(
    projet_id: Optional[str] = None,
    associe_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(PartProjet).where(PartProjet.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(PartProjet.projet_id == projet_id)
    if associe_id:
        q = q.where(PartProjet.associe_id == associe_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "projet_id": r.projet_id, "associe_id": r.associe_id,
            "pourcentage": float(r.pourcentage), "montant_apport": float(r.montant_apport or 0),
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Mutations Foncières
# ────────────────────────────────────────────────────────────────────────────

@router.post("/mutations", status_code=201)
async def create_mutation(
    body: MutationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = MutationFonciere(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        type_mutation=TypeMutation(body.type_mutation),
        cedant_id=body.cedant_id,
        cedant_type=TypeCedant(body.cedant_type) if body.cedant_type else None,
        cessionnaire_id=body.cessionnaire_id,
        cessionnaire_type=TypeCedant(body.cessionnaire_type) if body.cessionnaire_type else None,
        date_mutation=body.date_mutation,
        montant=body.montant,
        reference_acte=body.reference_acte,
        description=body.description,
        ordre=body.ordre,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return {"id": m.id}


@router.get("/mutations")
async def list_mutations(
    projet_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(MutationFonciere).where(MutationFonciere.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(MutationFonciere.projet_id == projet_id)
    q = q.order_by(MutationFonciere.ordre)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "projet_id": r.projet_id,
            "type_mutation": r.type_mutation.value if r.type_mutation else None,
            "cedant_id": r.cedant_id, "cedant_type": r.cedant_type.value if r.cedant_type else None,
            "cessionnaire_id": r.cessionnaire_id,
            "cessionnaire_type": r.cessionnaire_type.value if r.cessionnaire_type else None,
            "date_mutation": str(r.date_mutation) if r.date_mutation else None,
            "montant": float(r.montant) if r.montant else None,
            "reference_acte": r.reference_acte,
            "description": r.description,
            "ordre": r.ordre,
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# Lots Immobiliers (EDD)
# ────────────────────────────────────────────────────────────────────────────

@router.post("/lots-immobiliers", status_code=201)
async def create_lot_immobilier(
    body: LotImmoCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lot = LotImmobilier(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        bloc=body.bloc,
        etage=body.etage,
        numero_lot=body.numero_lot,
        type_bien=TypeBien(body.type_bien),
        surface=body.surface,
        prix=body.prix,
        notes=body.notes,
    )
    db.add(lot)
    await db.commit()
    await db.refresh(lot)
    return {"id": lot.id}


@router.get("/lots-immobiliers")
async def list_lots_immobiliers(
    projet_id: Optional[str] = None,
    statut: Optional[str] = None,
    type_bien: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(LotImmobilier).where(LotImmobilier.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(LotImmobilier.projet_id == projet_id)
    if statut:
        q = q.where(LotImmobilier.statut == StatutLotImmo(statut))
    if type_bien:
        q = q.where(LotImmobilier.type_bien == TypeBien(type_bien))
    q = q.order_by(LotImmobilier.bloc, LotImmobilier.etage, LotImmobilier.numero_lot)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "projet_id": r.projet_id,
            "bloc": r.bloc, "etage": r.etage, "numero_lot": r.numero_lot,
            "type_bien": r.type_bien.value if r.type_bien else None,
            "surface": float(r.surface), "prix": float(r.prix),
            "statut": r.statut.value if r.statut else "DISPONIBLE",
            "client_id": r.client_id,
            "date_reservation": str(r.date_reservation) if r.date_reservation else None,
            "date_vente": str(r.date_vente) if r.date_vente else None,
            "date_livraison": str(r.date_livraison) if r.date_livraison else None,
        }
        for r in rows
    ]


@router.get("/lots-immobiliers/dashboard")
async def lots_dashboard(
    projet_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get EDD real estate stock dashboard for a project."""
    q = select(LotImmobilier).where(
        LotImmobilier.tenant_id == user.tenant_id,
        LotImmobilier.projet_id == projet_id,
    )
    result = await db.execute(q)
    lots = result.scalars().all()

    summary = {"total": 0, "disponible": 0, "reserve": 0, "vendu": 0, "livre": 0, "litige": 0}
    total_value = 0
    sold_value = 0
    by_type = {}

    for lot in lots:
        summary["total"] += 1
        s = (lot.statut.value if lot.statut else "DISPONIBLE").lower()
        summary[s] = summary.get(s, 0) + 1
        total_value += float(lot.prix or 0)
        if s in ("vendu", "livre"):
            sold_value += float(lot.prix or 0)
        tb = lot.type_bien.value if lot.type_bien else "AUTRE"
        by_type[tb] = by_type.get(tb, 0) + 1

    return {
        "summary": summary,
        "total_value": total_value,
        "sold_value": sold_value,
        "available_value": total_value - sold_value,
        "by_type": by_type,
    }


@router.patch("/lots-immobiliers/{lot_id}/reserve")
async def reserve_lot(
    lot_id: str,
    client_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LotImmobilier).where(
            LotImmobilier.id == lot_id,
            LotImmobilier.tenant_id == user.tenant_id,
        )
    )
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(404, "Lot not found")
    if lot.statut != StatutLotImmo.DISPONIBLE:
        raise HTTPException(400, f"Lot is not available (status: {lot.statut.value})")
    lot.statut = StatutLotImmo.RESERVE
    lot.client_id = client_id
    lot.date_reservation = date.today()
    await db.commit()
    return {"message": "Lot reserved"}


@router.patch("/lots-immobiliers/{lot_id}/sell")
async def sell_lot(
    lot_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LotImmobilier).where(
            LotImmobilier.id == lot_id,
            LotImmobilier.tenant_id == user.tenant_id,
        )
    )
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(404, "Lot not found")
    if lot.statut not in (StatutLotImmo.DISPONIBLE, StatutLotImmo.RESERVE):
        raise HTTPException(400, f"Cannot sell lot (status: {lot.statut.value})")
    lot.statut = StatutLotImmo.VENDU
    lot.date_vente = date.today()
    await db.commit()
    return {"message": "Lot sold"}


# ────────────────────────────────────────────────────────────────────────────
# Projet Entreprise Historique (OPERA)
# ────────────────────────────────────────────────────────────────────────────

@router.post("/projet-historique", status_code=201)
async def create_projet_historique(
    body: ProjetEntrepriseHistCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ph = ProjetEntrepriseHistorique(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        entreprise_id=body.entreprise_id,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
        type_transition=TypeTransition(body.type_transition) if body.type_transition else None,
        reference_acte=body.reference_acte,
        notes=body.notes,
    )
    db.add(ph)
    await db.commit()
    return {"id": ph.id}


@router.get("/projet-historique")
async def list_projet_historique(
    projet_id: Optional[str] = None,
    entreprise_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(ProjetEntrepriseHistorique).where(
        ProjetEntrepriseHistorique.tenant_id == user.tenant_id
    )
    if projet_id:
        q = q.where(ProjetEntrepriseHistorique.projet_id == projet_id)
    if entreprise_id:
        q = q.where(ProjetEntrepriseHistorique.entreprise_id == entreprise_id)
    q = q.order_by(ProjetEntrepriseHistorique.date_debut)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "projet_id": r.projet_id, "entreprise_id": r.entreprise_id,
            "date_debut": str(r.date_debut),
            "date_fin": str(r.date_fin) if r.date_fin else None,
            "type_transition": r.type_transition.value if r.type_transition else None,
            "reference_acte": r.reference_acte, "notes": r.notes,
        }
        for r in rows
    ]
