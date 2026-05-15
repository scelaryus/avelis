# GAP 2 — FINANCE & ASSOCIÉS — finance_associes.py (API router)
"""API endpoints for Finance & Associés domain."""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sa_func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User
from app.models.finance_associes import (
    CompteCourantAssocie, MouvementCompteCourant,
    ClotureMensuelle, AppelDeFonds, CessionParts,
    TypeMouvement, StatutAppelFonds, StatutCession,
)
from app.services.blocking_rules import (
    BlockingError, validate_retrait_associe,
    validate_share_transfer_integrity,
)

router = APIRouter(tags=["Finance & Associés"])


# ── Pydantic Schemas ────────────────────────────────────────────────────────

class CompteCreate(BaseModel):
    associe_id: str

class MouvementCreate(BaseModel):
    compte_courant_id: str
    associe_id: str
    type_mouvement: str
    montant: float = Field(gt=0)
    sens: str  # CREDIT or DEBIT
    date_mouvement: date
    description: str
    projet_id: Optional[str] = None
    entreprise_id: Optional[str] = None
    exercice_id: Optional[str] = None
    reference_interne: Optional[str] = None
    appel_fonds_id: Optional[str] = None
    cession_parts_id: Optional[str] = None
    document_id: Optional[str] = None
    est_test_fictif: bool = False

class AppelFondsCreate(BaseModel):
    entreprise_id: str
    projet_id: Optional[str] = None
    montant_total_requis: float = Field(gt=0)
    motif: str
    date_emission: date
    date_limite: date
    detail_contributions: list

class CessionCreate(BaseModel):
    projet_id: str
    vendeur_id: str
    acheteur_id: Optional[str] = None
    pourcentage_parts_cedees: float = Field(gt=0)
    valorisation_systeme_par_point: float
    prix_demande_par_point: Optional[float] = None
    date_proposition: date
    date_limite_offres: Optional[date] = None
    motif: Optional[str] = None
    est_cession_forcee: bool = False

class ClotureRequest(BaseModel):
    projet_id: str
    mois: int = Field(ge=1, le=12)
    annee: int
    est_test_fictif: bool = False


# ── Comptes Courants ────────────────────────────────────────────────────────

@router.post("/comptes-courants", status_code=201)
async def create_compte_courant(
    body: CompteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cc = CompteCourantAssocie(
        id=str(uuid.uuid4()),
        associe_id=body.associe_id,
    )
    db.add(cc)
    await db.flush()
    return {"id": cc.id, "associe_id": cc.associe_id}


@router.get("/comptes-courants")
async def list_comptes_courants(
    associe_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(CompteCourantAssocie).where(
        CompteCourantAssocie.is_deleted == False
    )
    if associe_id:
        q = q.where(CompteCourantAssocie.associe_id == associe_id)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "associe_id": r.associe_id,
            "solde_global": float(r.solde_global),
            "solde_disponible_retrait": float(r.solde_disponible_retrait),
            "solde_avances_non_remboursees": float(r.solde_avances_non_remboursees),
            "est_gele": r.est_gele,
            "motif_gel": r.motif_gel,
        }
        for r in rows
    ]


@router.post("/comptes-courants/{compte_id}/gel")
async def toggle_gel_compte(
    compte_id: str,
    gele: bool,
    motif: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CompteCourantAssocie).where(CompteCourantAssocie.id == compte_id)
    )
    cc = result.scalar_one_or_none()
    if not cc:
        raise HTTPException(404, "Compte courant not found")
    cc.est_gele = gele
    cc.motif_gel = motif if gele else None
    await db.flush()
    return {"id": cc.id, "est_gele": cc.est_gele}


# ── Mouvements ──────────────────────────────────────────────────────────────

@router.post("/mouvements", status_code=201)
async def create_mouvement(
    body: MouvementCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.sens not in ("CREDIT", "DEBIT"):
        raise HTTPException(400, "sens must be CREDIT or DEBIT")

    mvt = MouvementCompteCourant(
        id=str(uuid.uuid4()),
        compte_courant_id=body.compte_courant_id,
        associe_id=body.associe_id,
        projet_id=body.projet_id,
        entreprise_id=body.entreprise_id,
        exercice_id=body.exercice_id,
        type_mouvement=TypeMouvement(body.type_mouvement),
        montant=body.montant,
        sens=body.sens,
        date_mouvement=body.date_mouvement,
        description=body.description,
        reference_interne=body.reference_interne,
        appel_fonds_id=body.appel_fonds_id,
        cession_parts_id=body.cession_parts_id,
        document_id=body.document_id,
        est_test_fictif=body.est_test_fictif,
        created_by=user.id,
    )
    db.add(mvt)
    await db.flush()

    # Recalculate solde_global on the associated current account
    await _recalculate_solde(body.compte_courant_id, db)

    # If linked to an appel de fonds, update its montant_collecte
    if body.appel_fonds_id and body.sens == "CREDIT":
        await _update_appel_fonds_collecte(body.appel_fonds_id, db)

    return {"id": mvt.id}


@router.get("/mouvements")
async def list_mouvements(
    compte_courant_id: Optional[str] = None,
    associe_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(MouvementCompteCourant)
    if compte_courant_id:
        q = q.where(MouvementCompteCourant.compte_courant_id == compte_courant_id)
    if associe_id:
        q = q.where(MouvementCompteCourant.associe_id == associe_id)
    if projet_id:
        q = q.where(MouvementCompteCourant.projet_id == projet_id)
    q = q.order_by(MouvementCompteCourant.date_mouvement.desc()).limit(limit)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "compte_courant_id": r.compte_courant_id,
            "associe_id": r.associe_id,
            "type_mouvement": r.type_mouvement.value,
            "montant": float(r.montant),
            "sens": r.sens,
            "date_mouvement": str(r.date_mouvement),
            "description": r.description,
        }
        for r in rows
    ]


# ── Appels de Fonds ─────────────────────────────────────────────────────────

@router.post("/appels-de-fonds", status_code=201)
async def create_appel_fonds(
    body: AppelFondsCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    af = AppelDeFonds(
        id=str(uuid.uuid4()),
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        montant_total_requis=body.montant_total_requis,
        motif=body.motif,
        date_emission=body.date_emission,
        date_limite=body.date_limite,
        detail_contributions=body.detail_contributions,
        statut=StatutAppelFonds.EMIS,
        emis_par=user.id,
    )
    db.add(af)
    await db.flush()
    return {"id": af.id}


@router.get("/appels-de-fonds")
async def list_appels_fonds(
    entreprise_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(AppelDeFonds)
    if entreprise_id:
        q = q.where(AppelDeFonds.entreprise_id == entreprise_id)
    q = q.order_by(AppelDeFonds.date_emission.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "entreprise_id": r.entreprise_id,
            "projet_id": r.projet_id,
            "montant_total_requis": float(r.montant_total_requis),
            "montant_collecte": float(r.montant_collecte),
            "motif": r.motif,
            "statut": r.statut.value,
            "date_emission": str(r.date_emission),
            "date_limite": str(r.date_limite),
        }
        for r in rows
    ]


# ── Cessions de Parts ──────────────────────────────────────────────────────

@router.post("/cessions", status_code=201)
async def create_cession(
    body: CessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Blocking validation
    await validate_share_transfer_integrity(
        body.projet_id, body.vendeur_id,
        Decimal(str(body.pourcentage_parts_cedees)), db
    )

    cs = CessionParts(
        id=str(uuid.uuid4()),
        projet_id=body.projet_id,
        vendeur_id=body.vendeur_id,
        acheteur_id=body.acheteur_id,
        pourcentage_parts_cedees=body.pourcentage_parts_cedees,
        valorisation_systeme_par_point=body.valorisation_systeme_par_point,
        prix_demande_par_point=body.prix_demande_par_point,
        date_proposition=body.date_proposition,
        date_limite_offres=body.date_limite_offres,
        motif=body.motif,
        est_cession_forcee=body.est_cession_forcee,
        created_by=user.id,
    )
    db.add(cs)
    await db.flush()
    return {"id": cs.id}


@router.get("/cessions")
async def list_cessions(
    projet_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(CessionParts)
    if projet_id:
        q = q.where(CessionParts.projet_id == projet_id)
    q = q.order_by(CessionParts.date_proposition.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "projet_id": r.projet_id,
            "vendeur_id": r.vendeur_id,
            "acheteur_id": r.acheteur_id,
            "pourcentage_parts_cedees": float(r.pourcentage_parts_cedees),
            "statut": r.statut.value,
            "date_proposition": str(r.date_proposition),
        }
        for r in rows
    ]


# ── Clôture trigger ────────────────────────────────────────────────────────

@router.post("/clotures/trigger")
async def trigger_cloture(
    body: ClotureRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger monthly closing for a project. Requires DAF or SUPER_ADMIN."""
    from app.services.rbac import check_permission
    if not check_permission(user.role, "cloture:trigger"):
        raise HTTPException(403, "Permission denied: cloture:trigger required")

    from app.services.cloture_service import executer_cloture_mensuelle
    cloture = await executer_cloture_mensuelle(
        projet_id=body.projet_id,
        mois=body.mois,
        annee=body.annee,
        created_by=user.id,
        db=db,
        est_test_fictif=body.est_test_fictif,
    )
    return {
        "id": cloture.id,
        "statut": cloture.statut.value,
        "tresorerie_nette_mois": float(cloture.tresorerie_nette_mois),
        "montant_a_liberer": float(cloture.montant_a_liberer),
        "detail_distribution": cloture.detail_distribution,
        "hash_verification": cloture.hash_verification,
        "double_computation_ok": cloture.double_computation_ok,
    }


@router.get("/clotures")
async def list_clotures(
    projet_id: Optional[str] = None,
    annee: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(ClotureMensuelle)
    if projet_id:
        q = q.where(ClotureMensuelle.projet_id == projet_id)
    if annee:
        q = q.where(ClotureMensuelle.annee == annee)
    q = q.order_by(ClotureMensuelle.annee.desc(), ClotureMensuelle.mois.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "projet_id": r.projet_id,
            "mois": r.mois,
            "annee": r.annee,
            "tresorerie_nette_mois": float(r.tresorerie_nette_mois),
            "montant_a_liberer": float(r.montant_a_liberer),
            "statut": r.statut.value,
            "hash_verification": r.hash_verification,
        }
        for r in rows
    ]


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _recalculate_solde(compte_courant_id: str, db: AsyncSession):
    """Recalculate solde_global from all movements."""
    from sqlalchemy import case, literal_column
    result = await db.execute(
        select(
            sa_func.coalesce(
                sa_func.sum(
                    case(
                        (MouvementCompteCourant.sens == "CREDIT", MouvementCompteCourant.montant),
                        else_=-MouvementCompteCourant.montant,
                    )
                ),
                0,
            )
        ).where(MouvementCompteCourant.compte_courant_id == compte_courant_id)
    )
    solde = result.scalar()
    await db.execute(
        update(CompteCourantAssocie)
        .where(CompteCourantAssocie.id == compte_courant_id)
        .values(solde_global=solde)
    )


async def _update_appel_fonds_collecte(appel_fonds_id: str, db: AsyncSession):
    """Recalculate montant_collecte and update status."""
    result = await db.execute(
        select(
            sa_func.coalesce(
                sa_func.sum(MouvementCompteCourant.montant), 0
            )
        ).where(
            MouvementCompteCourant.appel_fonds_id == appel_fonds_id,
            MouvementCompteCourant.sens == "CREDIT",
        )
    )
    collecte = result.scalar()

    af_result = await db.execute(
        select(AppelDeFonds).where(AppelDeFonds.id == appel_fonds_id)
    )
    af = af_result.scalar_one_or_none()
    if af:
        af.montant_collecte = collecte
        if collecte >= af.montant_total_requis:
            af.statut = StatutAppelFonds.INTEGRALEMENT_COUVERT
        elif collecte > 0:
            af.statut = StatutAppelFonds.PARTIELLEMENT_COUVERT


# ── GFI v7.0: EntrepriseAssocie (% entreprise) ─────────────────────────────

@router.get("/entreprise-associes")
async def list_entreprise_associes(
    entreprise_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List enterprise participation percentages (EntrepriseAssocie).

    These are the % used by CFF and monthly closing — never project shares.
    """
    from app.models.financial import EntrepriseAssocie, Entreprise, Associe

    q = select(EntrepriseAssocie).where(EntrepriseAssocie.est_actif == True)
    if entreprise_id:
        q = q.where(EntrepriseAssocie.entreprise_id == entreprise_id)

    result = await db.execute(q)
    rows = result.scalars().all()

    # Resolve names
    items = []
    for row in rows:
        ent_result = await db.execute(
            select(Entreprise.raison_sociale).where(Entreprise.id == row.entreprise_id)
        )
        assoc_result = await db.execute(
            select(Associe).where(Associe.id == row.associe_id)
        )
        assoc = assoc_result.scalar_one_or_none()
        assoc_nom = f"{assoc.nom} {assoc.prenom or ''}".strip() if assoc else None
        # pourcentage stored as fraction (0.25 = 25%), display as percentage
        pct = float(row.pourcentage or 0) * 100
        items.append({
            "id": row.id,
            "entreprise_id": row.entreprise_id,
            "associe_id": row.associe_id,
            "pourcentage": round(pct, 2),
            "est_actif": row.est_actif,
            "entreprise_nom": ent_result.scalar() or None,
            "associe_nom": assoc_nom,
        })

    return items
