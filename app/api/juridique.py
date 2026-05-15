"""GFI v7.0 — Juridique & Moyens Generaux API.

CRUD for:
  - Dossiers juridiques (with est_succession for FC-002)
  - Permis & autorisations
  - Commandes d'achat (with RF + est_avance_materiel for KT-05)
  - Stock materiel
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User
from app.models.juridique import (
    DossierJuridique, StatutDossierJuridique,
    PermisAutorisation,
    CommandeAchat, StatutCommande,
    StockMateriel,
)

router = APIRouter(tags=["Juridique & Moyens Generaux"])


# ── Schemas ────────────────────────────────────────────────────────────────

class DossierCreate(BaseModel):
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    reference: Optional[str] = None
    titre: str
    description: Optional[str] = None
    type_dossier: Optional[str] = None
    est_succession: bool = False
    partie_adverse: Optional[str] = None
    tribunal: Optional[str] = None
    montant_litige: Optional[float] = None
    statut: str = "OUVERT"
    date_ouverture: Optional[str] = None
    avocat_responsable: Optional[str] = None


class PermisCreate(BaseModel):
    entreprise_id: Optional[str] = None
    projet_id: Optional[str] = None
    type_permis: str
    numero: Optional[str] = None
    date_delivrance: Optional[str] = None
    date_expiration: Optional[str] = None
    autorite_delivrance: Optional[str] = None


class CommandeCreate(BaseModel):
    entreprise_id: str
    projet_id: Optional[str] = None
    fournisseur_id: Optional[str] = None
    reference: Optional[str] = None
    realite_financiere: Optional[str] = None
    montant_ht: float = Field(gt=0)
    montant_tva: float = 0
    est_avance_materiel: bool = False
    statut: str = "BROUILLON"
    date_commande: str
    date_livraison_prevue: Optional[str] = None
    description: Optional[str] = None


class StockCreate(BaseModel):
    entreprise_id: str
    code_article: str
    designation: str
    unite: str = "unite"
    quantite: float = 0
    valeur_unitaire: float = 0
    emplacement: Optional[str] = None
    seuil_alerte: float = 0


# ── Dossiers Juridiques ───────────────────────────────────────────────────

@router.get("/dossiers")
async def list_dossiers(
    statut: Optional[str] = None,
    type_dossier: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(DossierJuridique).order_by(DossierJuridique.created_at.desc())
    if statut:
        q = q.where(DossierJuridique.statut == statut)
    if type_dossier:
        q = q.where(DossierJuridique.type_dossier == type_dossier)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [_serialize_dossier(r) for r in rows]


@router.post("/dossiers", status_code=201)
async def create_dossier(
    body: DossierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dossier = DossierJuridique(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        reference=body.reference,
        titre=body.titre,
        description=body.description,
        type_dossier=body.type_dossier,
        est_succession=body.est_succession,
        partie_adverse=body.partie_adverse,
        tribunal=body.tribunal,
        montant_litige=body.montant_litige,
        statut=StatutDossierJuridique(body.statut),
        date_ouverture=date.fromisoformat(body.date_ouverture) if body.date_ouverture else None,
        avocat_responsable=body.avocat_responsable,
        created_by=current_user.id,
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return _serialize_dossier(dossier)


@router.get("/dossiers/{dossier_id}")
async def get_dossier(
    dossier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(DossierJuridique).where(DossierJuridique.id == dossier_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    return _serialize_dossier(d)


def _serialize_dossier(d: DossierJuridique) -> dict:
    return {
        "id": d.id,
        "reference": d.reference,
        "titre": d.titre,
        "description": d.description,
        "type_dossier": d.type_dossier,
        "est_succession": d.est_succession,
        "partie_adverse": d.partie_adverse,
        "tribunal": d.tribunal,
        "montant_litige": float(d.montant_litige) if d.montant_litige else None,
        "statut": d.statut.value if d.statut else None,
        "date_ouverture": str(d.date_ouverture) if d.date_ouverture else None,
        "date_cloture": str(d.date_cloture) if d.date_cloture else None,
        "avocat_responsable": d.avocat_responsable,
        "created_at": str(d.created_at) if d.created_at else None,
    }


# ── Permis & Autorisations ────────────────────────────────────────────────

@router.get("/permis")
async def list_permis(
    projet_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(PermisAutorisation).order_by(PermisAutorisation.date_expiration.asc())
    if projet_id:
        q = q.where(PermisAutorisation.projet_id == projet_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [_serialize_permis(r) for r in rows]


@router.post("/permis", status_code=201)
async def create_permis(
    body: PermisCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permis = PermisAutorisation(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        type_permis=body.type_permis,
        numero=body.numero,
        date_delivrance=date.fromisoformat(body.date_delivrance) if body.date_delivrance else None,
        date_expiration=date.fromisoformat(body.date_expiration) if body.date_expiration else None,
        autorite_delivrance=body.autorite_delivrance,
    )
    db.add(permis)
    await db.commit()
    await db.refresh(permis)
    return _serialize_permis(permis)


def _serialize_permis(p: PermisAutorisation) -> dict:
    return {
        "id": p.id,
        "type_permis": p.type_permis,
        "numero": p.numero,
        "date_delivrance": str(p.date_delivrance) if p.date_delivrance else None,
        "date_expiration": str(p.date_expiration) if p.date_expiration else None,
        "autorite_delivrance": p.autorite_delivrance,
        "est_valide": p.est_valide,
        "created_at": str(p.created_at) if p.created_at else None,
    }


# ── Commandes d'Achat ─────────────────────────────────────────────────────

@router.get("/commandes")
async def list_commandes(
    statut: Optional[str] = None,
    entreprise_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(CommandeAchat).order_by(CommandeAchat.date_commande.desc())
    if statut:
        q = q.where(CommandeAchat.statut == statut)
    if entreprise_id:
        q = q.where(CommandeAchat.entreprise_id == entreprise_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [_serialize_commande(r) for r in rows]


@router.post("/commandes", status_code=201)
async def create_commande(
    body: CommandeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    montant_ttc = body.montant_ht + body.montant_tva
    cmd = CommandeAchat(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        fournisseur_id=body.fournisseur_id,
        reference=body.reference,
        realite_financiere=body.realite_financiere,
        montant_ht=body.montant_ht,
        montant_tva=body.montant_tva,
        montant_ttc=montant_ttc,
        est_avance_materiel=body.est_avance_materiel,
        statut=StatutCommande(body.statut),
        date_commande=date.fromisoformat(body.date_commande),
        date_livraison_prevue=date.fromisoformat(body.date_livraison_prevue) if body.date_livraison_prevue else None,
        description=body.description,
        created_by=current_user.id,
    )
    db.add(cmd)
    await db.commit()
    await db.refresh(cmd)
    return _serialize_commande(cmd)


def _serialize_commande(c: CommandeAchat) -> dict:
    return {
        "id": c.id,
        "reference": c.reference,
        "entreprise_id": c.entreprise_id,
        "projet_id": c.projet_id,
        "realite_financiere": c.realite_financiere,
        "montant_ht": float(c.montant_ht) if c.montant_ht else 0,
        "montant_tva": float(c.montant_tva) if c.montant_tva else 0,
        "montant_ttc": float(c.montant_ttc) if c.montant_ttc else 0,
        "est_avance_materiel": c.est_avance_materiel,
        "statut": c.statut.value if c.statut else None,
        "date_commande": str(c.date_commande) if c.date_commande else None,
        "date_livraison_prevue": str(c.date_livraison_prevue) if c.date_livraison_prevue else None,
        "description": c.description,
        "created_at": str(c.created_at) if c.created_at else None,
    }


# ── Stock Materiel ─────────────────────────────────────────────────────────

@router.get("/stock")
async def list_stock(
    entreprise_id: Optional[str] = None,
    alerte_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(StockMateriel).where(StockMateriel.est_actif == True)
    if entreprise_id:
        q = q.where(StockMateriel.entreprise_id == entreprise_id)
    if alerte_only:
        q = q.where(StockMateriel.quantite <= StockMateriel.seuil_alerte)
    q = q.order_by(StockMateriel.code_article)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [_serialize_stock(r) for r in rows]


@router.post("/stock", status_code=201)
async def create_stock(
    body: StockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = StockMateriel(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        entreprise_id=body.entreprise_id,
        code_article=body.code_article,
        designation=body.designation,
        unite=body.unite,
        quantite=body.quantite,
        valeur_unitaire=body.valeur_unitaire,
        valeur_totale=body.quantite * body.valeur_unitaire,
        emplacement=body.emplacement,
        seuil_alerte=body.seuil_alerte,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _serialize_stock(item)


def _serialize_stock(s: StockMateriel) -> dict:
    return {
        "id": s.id,
        "code_article": s.code_article,
        "designation": s.designation,
        "unite": s.unite,
        "quantite": float(s.quantite) if s.quantite else 0,
        "valeur_unitaire": float(s.valeur_unitaire) if s.valeur_unitaire else 0,
        "valeur_totale": float(s.valeur_totale) if s.valeur_totale else 0,
        "emplacement": s.emplacement,
        "seuil_alerte": float(s.seuil_alerte) if s.seuil_alerte else 0,
        "est_actif": s.est_actif,
        "en_alerte": float(s.quantite or 0) <= float(s.seuil_alerte or 0) and float(s.seuil_alerte or 0) > 0,
    }
