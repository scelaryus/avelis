"""ADV Sale Workflow — Section 8 of SPECIFICATION_GFI7_V3.1.

Implements the full lot lifecycle:
  DISPONIBLE → VERROUILLÉ → RÉSERVÉ → ENGAGÉ → VENDU
  with RF2 blocking (R-004 / KT-07) and dunning (EX-ADV-005).
"""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User, AuditLog
from app.models.adv import (
    DossierVente, StatutLotADV, ModePaiement, StatutRF2,
)

router = APIRouter(tags=["ADV Ventes"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class DossierCreate(BaseModel):
    entreprise_id: str
    projet_id: str
    lot_code: str
    unit_id: Optional[str] = None
    prix_vente_rf1: float = 0
    prix_vente_rf2: float = 0
    mode_paiement: Optional[str] = None
    notes: Optional[str] = None


class PaiementSpot(BaseModel):
    montant: float = Field(gt=0)
    realite_financiere: str = "RF1"  # RF1 (cheque) or RF2 (especes)
    reference: Optional[str] = None


class EngagementRequest(BaseModel):
    client_id: str
    contract_id: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _dossier_to_dict(d: DossierVente) -> dict:
    return {
        "id": d.id,
        "entreprise_id": d.entreprise_id,
        "projet_id": d.projet_id,
        "client_id": d.client_id,
        "lot_code": d.lot_code,
        "unit_id": d.unit_id,
        "statut_lot": d.statut_lot.value if d.statut_lot else None,
        "mode_paiement": d.mode_paiement.value if d.mode_paiement else None,
        "prix_vente_rf1": float(d.prix_vente_rf1 or 0),
        "prix_vente_rf2": float(d.prix_vente_rf2 or 0),
        "prix_total": float(d.prix_total or 0),
        "statut_rf2": d.statut_rf2.value if d.statut_rf2 else None,
        "montant_rf2_recu": float(d.montant_rf2_recu or 0),
        "montant_total_paye": float(d.montant_total_paye or 0),
        "montant_restant": float(d.montant_restant or 0),
        "date_reservation": str(d.date_reservation) if d.date_reservation else None,
        "date_engagement": str(d.date_engagement) if d.date_engagement else None,
        "date_livraison": str(d.date_livraison) if d.date_livraison else None,
        "jours_retard_max": d.jours_retard_max,
        "niveau_relance": d.niveau_relance,
        "notes": d.notes,
        "created_at": str(d.created_at) if d.created_at else None,
    }


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("/dossiers")
async def list_dossiers(
    projet_id: Optional[str] = None,
    statut: Optional[str] = None,
    x_entreprise_id: Optional[str] = Header(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List sale dossiers — scoped to active entreprise."""
    from fastapi import Header as _H
    q = select(DossierVente).where(DossierVente.tenant_id == user.tenant_id)
    ent_id = x_entreprise_id or getattr(user, "_active_entreprise_id", None)
    if ent_id:
        q = q.where(DossierVente.entreprise_id == ent_id)
    if projet_id:
        q = q.where(DossierVente.projet_id == projet_id)
    if statut:
        q = q.where(DossierVente.statut_lot == statut)
    q = q.order_by(DossierVente.created_at.desc())
    result = await db.execute(q)
    return [_dossier_to_dict(d) for d in result.scalars().all()]


@router.post("/dossiers", status_code=201)
async def create_dossier(
    body: DossierCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new sale dossier for a lot — starts as DISPONIBLE."""
    # EX-ADV-001: Check lot is not already taken
    existing = await db.execute(
        select(DossierVente).where(
            DossierVente.tenant_id == user.tenant_id,
            DossierVente.lot_code == body.lot_code,
            DossierVente.projet_id == body.projet_id,
            DossierVente.statut_lot.notin_(["VENDU", "INDISPONIBLE"]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Le lot {body.lot_code} a déjà un dossier actif")

    prix_rf2 = Decimal(str(body.prix_vente_rf2))
    dossier = DossierVente(
        tenant_id=user.tenant_id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        lot_code=body.lot_code,
        unit_id=body.unit_id,
        prix_vente_rf1=body.prix_vente_rf1,
        prix_vente_rf2=body.prix_vente_rf2,
        prix_total=body.prix_vente_rf1 + body.prix_vente_rf2,
        montant_restant=body.prix_vente_rf1 + body.prix_vente_rf2,
        mode_paiement=body.mode_paiement,
        statut_rf2=StatutRF2.EN_ATTENTE if prix_rf2 > 0 else StatutRF2.NON_APPLICABLE,
        notes=body.notes,
        created_by=user.id,
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return _dossier_to_dict(dossier)


@router.get("/dossiers/{dossier_id}")
async def get_dossier(
    dossier_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DossierVente).where(
            DossierVente.id == dossier_id,
            DossierVente.tenant_id == user.tenant_id,
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    return _dossier_to_dict(d)


# ── WORKFLOW TRANSITIONS ─────────────────────────────────────────────────────

@router.post("/dossiers/{dossier_id}/verrouiller")
async def verrouiller_lot(
    dossier_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lock a lot for 15 min (commercial option). EX-ADV-001."""
    d = await _get_dossier(dossier_id, user.tenant_id, db)
    if d.statut_lot != StatutLotADV.DISPONIBLE:
        raise HTTPException(400, f"Lot non disponible (statut: {d.statut_lot.value})")

    d.statut_lot = StatutLotADV.VERROUILLE
    d.verrouille_par = user.id
    d.verrouille_at = datetime.utcnow()
    _audit(db, user, "lot_verrouille", dossier_id)
    await db.commit()
    return {"statut": "VERROUILLE", "expire_dans": "15 minutes"}


@router.post("/dossiers/{dossier_id}/liberer")
async def liberer_lot(
    dossier_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Release a locked lot back to DISPONIBLE."""
    d = await _get_dossier(dossier_id, user.tenant_id, db)
    if d.statut_lot != StatutLotADV.VERROUILLE:
        raise HTTPException(400, "Lot non verrouillé")

    d.statut_lot = StatutLotADV.DISPONIBLE
    d.verrouille_par = None
    d.verrouille_at = None
    _audit(db, user, "lot_libere", dossier_id)
    await db.commit()
    return {"statut": "DISPONIBLE"}


@router.post("/dossiers/{dossier_id}/reserver")
async def reserver_lot(
    dossier_id: str,
    file: UploadFile = File(..., description="Preuve de paiement SPOT (reçu, chèque, quittance)"),
    montant: float = Form(..., gt=0),
    realite_financiere: str = Form("RF1"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reserve a lot after SPOT payment. Requires proof document."""
    from app.services.proof_verifier import verify_proof

    d = await _get_dossier(dossier_id, user.tenant_id, db)
    if d.statut_lot not in (StatutLotADV.DISPONIBLE, StatutLotADV.VERROUILLE):
        raise HTTPException(400, f"BLOCAGE EX-ADV-001 : lot en statut {d.statut_lot.value}")

    # AI proof verification
    proof = await verify_proof(file, "reserver_lot", {"montant": montant, "lot_code": d.lot_code}, user.tenant_id, user.id, db)
    if not proof["verified"]:
        _audit(db, user, "lot_reserve_bloque_preuve", dossier_id)
        await db.commit()
        raise HTTPException(400, f"BLOCAGE : Preuve non conforme — {proof['rejection_reason']}")

    montant_d = Decimal(str(montant))
    d.statut_lot = StatutLotADV.RESERVE
    d.date_reservation = date.today()
    d.montant_total_paye = Decimal(str(d.montant_total_paye or 0)) + montant_d
    d.montant_restant = Decimal(str(d.prix_total or 0)) - d.montant_total_paye

    if realite_financiere == "RF2":
        d.montant_rf2_recu = Decimal(str(d.montant_rf2_recu or 0)) + montant_d
        if d.montant_rf2_recu >= Decimal(str(d.prix_vente_rf2 or 0)):
            d.statut_rf2 = StatutRF2.SECURISE

    _audit(db, user, f"lot_reserve_spot_{realite_financiere}", dossier_id)
    await db.commit()
    return {
        "statut": "RESERVE",
        "montant_paye": float(d.montant_total_paye),
        "statut_rf2": d.statut_rf2.value,
        "proof": proof,
    }


@router.post("/dossiers/{dossier_id}/engager")
async def engager_lot(
    dossier_id: str,
    file: UploadFile = File(..., description="Contrat signé, promesse de vente ou décision d'affectation"),
    client_id: str = Form(...),
    contract_id: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Engage (sign contract). Requires signed contract proof. BLOCKED if RF2 not secured."""
    from app.services.proof_verifier import verify_proof

    d = await _get_dossier(dossier_id, user.tenant_id, db)
    if d.statut_lot != StatutLotADV.RESERVE:
        raise HTTPException(400, f"Le lot doit être RÉSERVÉ avant engagement (actuel: {d.statut_lot.value})")

    # R-004 / KT-07
    if d.statut_rf2 == StatutRF2.EN_ATTENTE:
        rf2_manquant = Decimal(str(d.prix_vente_rf2 or 0)) - Decimal(str(d.montant_rf2_recu or 0))
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"BLOCAGE R-004 (KT-07) : RF2 non sécurisé. "
            f"Attendu: {d.prix_vente_rf2:,.2f} DA, reçu: {d.montant_rf2_recu:,.2f} DA, manquant: {rf2_manquant:,.2f} DA."
        )

    # AI proof verification
    proof = await verify_proof(file, "engager_lot", {"lot_code": d.lot_code, "montant": float(d.prix_total or 0)}, user.tenant_id, user.id, db)
    if not proof["verified"]:
        _audit(db, user, "lot_engage_bloque_preuve", dossier_id)
        await db.commit()
        raise HTTPException(400, f"BLOCAGE : Preuve non conforme — {proof['rejection_reason']}")

    d.statut_lot = StatutLotADV.ENGAGE
    d.client_id = client_id
    d.contract_id = contract_id
    d.date_engagement = date.today()
    _audit(db, user, "lot_engage", dossier_id)
    await db.commit()
    return {"statut": "ENGAGE", "client_id": client_id, "proof": proof}


@router.post("/dossiers/{dossier_id}/paiement")
async def enregistrer_paiement(
    dossier_id: str,
    file: UploadFile = File(..., description="Preuve de paiement (reçu, chèque, virement)"),
    montant: float = Form(..., gt=0),
    realite_financiere: str = Form("RF1"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a payment on a dossier. Requires proof document."""
    from app.services.proof_verifier import verify_proof

    d = await _get_dossier(dossier_id, user.tenant_id, db)
    if d.statut_lot not in (StatutLotADV.RESERVE, StatutLotADV.ENGAGE):
        raise HTTPException(400, f"Paiement impossible sur un lot {d.statut_lot.value}")

    # AI proof verification
    proof = await verify_proof(file, "paiement_lot", {"montant": montant, "lot_code": d.lot_code}, user.tenant_id, user.id, db)
    if not proof["verified"]:
        _audit(db, user, "paiement_bloque_preuve", dossier_id)
        await db.commit()
        raise HTTPException(400, f"BLOCAGE : Preuve non conforme — {proof['rejection_reason']}")

    montant_d = Decimal(str(montant))
    d.montant_total_paye = Decimal(str(d.montant_total_paye or 0)) + montant_d
    d.montant_restant = Decimal(str(d.prix_total or 0)) - d.montant_total_paye

    if realite_financiere == "RF2":
        d.montant_rf2_recu = Decimal(str(d.montant_rf2_recu or 0)) + montant_d
        if d.montant_rf2_recu >= Decimal(str(d.prix_vente_rf2 or 0)):
            d.statut_rf2 = StatutRF2.SECURISE

    if d.montant_restant <= 0 and d.statut_lot == StatutLotADV.ENGAGE:
        d.statut_lot = StatutLotADV.VENDU
        d.date_livraison = date.today()
        _audit(db, user, "lot_vendu_100pct", dossier_id)
    else:
        _audit(db, user, f"paiement_{realite_financiere}", dossier_id)

    await db.commit()
    return {
        "statut": d.statut_lot.value,
        "montant_paye": float(d.montant_total_paye),
        "montant_restant": float(d.montant_restant),
        "statut_rf2": d.statut_rf2.value,
        "proof": proof,
    }


@router.post("/dossiers/{dossier_id}/livrer")
async def livrer_lot(
    dossier_id: str,
    file: UploadFile = File(..., description="PV de remise des clés ou attestation de livraison"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark as VENDU (keys delivered). Requires PV de remise des clés."""
    from app.services.proof_verifier import verify_proof

    d = await _get_dossier(dossier_id, user.tenant_id, db)
    if d.statut_lot != StatutLotADV.ENGAGE:
        raise HTTPException(400, f"Le lot doit être ENGAGÉ (actuel: {d.statut_lot.value})")
    if Decimal(str(d.montant_restant or 0)) > 0:
        raise HTTPException(400, f"Paiement incomplet : {d.montant_restant:,.2f} DA restant")

    proof = await verify_proof(file, "livrer_lot", {"lot_code": d.lot_code}, user.tenant_id, user.id, db)
    if not proof["verified"]:
        _audit(db, user, "livraison_bloque_preuve", dossier_id)
        await db.commit()
        raise HTTPException(400, f"BLOCAGE : Preuve non conforme — {proof['rejection_reason']}")

    d.statut_lot = StatutLotADV.VENDU
    d.date_livraison = date.today()
    _audit(db, user, "lot_vendu_livre", dossier_id)
    await db.commit()
    return {"statut": "VENDU", "proof": proof}


@router.post("/dossiers/{dossier_id}/indisponible")
async def marquer_indisponible(
    dossier_id: str,
    motif: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark lot as INDISPONIBLE (technical/legal hold)."""
    d = await _get_dossier(dossier_id, user.tenant_id, db)
    if d.statut_lot in (StatutLotADV.VENDU,):
        raise HTTPException(400, "Lot déjà vendu, impossible de le rendre indisponible")
    d.statut_lot = StatutLotADV.INDISPONIBLE
    d.notes = (d.notes or "") + f"\n[INDISPONIBLE] {motif}"
    _audit(db, user, "lot_indisponible", dossier_id)
    await db.commit()
    return {"statut": "INDISPONIBLE", "motif": motif}


# ── DUNNING / RELANCE (EX-ADV-005) ──────────────────────────────────────────

@router.post("/dossiers/relance")
async def run_dunning(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the dunning workflow on all ENGAGÉ dossiers with overdue payments.

    EX-ADV-005:
    - J+1: notification
    - J+7: first formal reminder
    - J+14: second reminder with mise en demeure
    - J+30: statut → DÉFAUT_PAIEMENT, escalade juridique
    """
    result = await db.execute(
        select(DossierVente).where(
            DossierVente.tenant_id == user.tenant_id,
            DossierVente.statut_lot.in_(["ENGAGE", "RESERVE"]),
            DossierVente.montant_restant > 0,
        )
    )
    dossiers = result.scalars().all()

    relances = {"j1": 0, "j7": 0, "j14": 0, "j30": 0}
    today = date.today()

    for d in dossiers:
        # Calculate overdue from engagement date or last payment due
        ref_date = d.date_engagement or d.date_reservation
        if not ref_date:
            continue

        jours = (today - ref_date).days
        d.jours_retard_max = max(d.jours_retard_max or 0, jours)

        if jours >= 30 and d.niveau_relance < 4:
            d.statut_lot = StatutLotADV.DEFAUT_PAIEMENT
            d.niveau_relance = 4
            d.derniere_relance = today
            relances["j30"] += 1
            _audit(db, user, "relance_j30_defaut", d.id)
        elif jours >= 14 and d.niveau_relance < 3:
            d.niveau_relance = 3
            d.derniere_relance = today
            relances["j14"] += 1
            _audit(db, user, "relance_j14_miseendemeure", d.id)
        elif jours >= 7 and d.niveau_relance < 2:
            d.niveau_relance = 2
            d.derniere_relance = today
            relances["j7"] += 1
            _audit(db, user, "relance_j7_formelle", d.id)
        elif jours >= 1 and d.niveau_relance < 1:
            d.niveau_relance = 1
            d.derniere_relance = today
            relances["j1"] += 1
            _audit(db, user, "relance_j1_notification", d.id)

    await db.commit()
    return {
        "dossiers_analyses": len(dossiers),
        "relances": relances,
        "total_relances": sum(relances.values()),
    }


# ── DASHBOARD ────────────────────────────────────────────────────────────────

@router.get("/dossiers/stats")
async def dossier_stats(
    projet_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sale dossier statistics by status."""
    q = select(
        DossierVente.statut_lot,
        sa_func.count(DossierVente.id),
        sa_func.coalesce(sa_func.sum(DossierVente.prix_total), 0),
    ).where(DossierVente.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(DossierVente.projet_id == projet_id)
    q = q.group_by(DossierVente.statut_lot)

    result = await db.execute(q)
    stats = {
        row[0].value if hasattr(row[0], "value") else str(row[0]): {
            "count": row[1],
            "montant_total": float(row[2]),
        }
        for row in result.fetchall()
    }
    return stats


# ── Internal helpers ─────────────────────────────────────────────────────────

async def _get_dossier(dossier_id: str, tenant_id: str, db: AsyncSession) -> DossierVente:
    result = await db.execute(
        select(DossierVente).where(
            DossierVente.id == dossier_id,
            DossierVente.tenant_id == tenant_id,
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Dossier de vente introuvable")
    return d


def _audit(db, user, action, entity_id):
    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action=action, entity_type="dossier_vente", entity_id=entity_id,
    ))
