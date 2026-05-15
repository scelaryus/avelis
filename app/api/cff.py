"""GFI v7.0 — CFF API endpoints.

POST /cff/calculer         — Calculate CFF for an enterprise
GET  /cff/verifier-kt01/{code} — Verify KT-01 (Yamina=0 in restricted enterprises)
GET  /cff/factures         — List CFF invoices
GET  /cff/factures/{id}    — Get CFF invoice with imputations
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.cff_engine import calculer_et_sauvegarder_cff, CFFEngine
from app.models.cff import CFFFacture, CFFImputationAssocie
from app.models.financial import EntrepriseAssocie, Entreprise

router = APIRouter(tags=["CFF"])


class CFFCalculRequest(BaseModel):
    entreprise_id: str
    montant_ht: float = Field(gt=0)
    projet_id: Optional[str] = None
    periode_mois: Optional[str] = None
    reference_facture: Optional[str] = None


class CFFCalculResponse(BaseModel):
    facture_id: str
    montant_ht: float
    cff_tva: float
    cff_ibs: float
    cff_tap: float
    cff_cnas: float
    cff_timbre: float
    cff_total: float
    hash_sha256: str


@router.post("/calculer", response_model=CFFCalculResponse)
async def calculer_cff(body: CFFCalculRequest, db: AsyncSession = Depends(get_db)):
    """Calculate CFF for an enterprise and distribute to associates by enterprise %."""
    facture = await calculer_et_sauvegarder_cff(
        db=db,
        entreprise_id=body.entreprise_id,
        montant_ht=body.montant_ht,
        projet_id=body.projet_id,
        periode_mois=body.periode_mois,
        reference_facture=body.reference_facture,
    )
    await db.commit()

    return CFFCalculResponse(
        facture_id=facture.id,
        montant_ht=float(facture.montant_ht),
        cff_tva=float(facture.cff_tva),
        cff_ibs=float(facture.cff_ibs),
        cff_tap=float(facture.cff_tap),
        cff_cnas=float(facture.cff_cnas),
        cff_timbre=float(facture.cff_timbre),
        cff_total=float(facture.cff_total),
        hash_sha256=facture.hash_sha256,
    )


@router.get("/verifier-kt01/{entreprise_code}")
async def verifier_kt01(
    entreprise_code: str,
    associe_yamina_id: str = Query(..., description="UUID of Yamina associate"),
    db: AsyncSession = Depends(get_db),
):
    """KT-01: Verify Yamina has 0% CFF in restricted enterprises."""
    # Find enterprise
    result = await db.execute(
        select(Entreprise).where(Entreprise.raison_sociale.ilike(f"%{entreprise_code}%"))
    )
    entreprise = result.scalar_one_or_none()
    if not entreprise:
        raise HTTPException(404, f"Entreprise '{entreprise_code}' introuvable")

    # Check if Yamina has participation in this enterprise
    part_result = await db.execute(
        select(EntrepriseAssocie).where(
            EntrepriseAssocie.entreprise_id == entreprise.id,
            EntrepriseAssocie.associe_id == associe_yamina_id,
            EntrepriseAssocie.est_actif == True,
        )
    )
    yamina_part = part_result.scalar_one_or_none()

    code_upper = entreprise_code.upper()
    is_restricted = any(k in code_upper for k in ("DBPI", "OC", "EP", "SEN", "BIM"))

    if is_restricted and yamina_part:
        return {
            "kt01_pass": False,
            "message": f"Yamina has {float(yamina_part.pourcentage)}% in {entreprise_code} — should be 0%",
            "entreprise_code": entreprise_code,
        }

    return {
        "kt01_pass": True,
        "message": f"Yamina correctly absent from {entreprise_code}" if is_restricted else "Enterprise not restricted",
        "entreprise_code": entreprise_code,
    }


@router.get("/factures")
async def list_factures(
    entreprise_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List CFF invoices."""
    q = select(CFFFacture).order_by(CFFFacture.created_at.desc())
    if entreprise_id:
        q = q.where(CFFFacture.entreprise_id == entreprise_id)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    factures = result.scalars().all()
    return [
        {
            "id": f.id,
            "entreprise_id": f.entreprise_id,
            "montant_ht": float(f.montant_ht),
            "cff_total": float(f.cff_total),
            "periode_mois": f.periode_mois,
            "created_at": str(f.created_at) if f.created_at else None,
        }
        for f in factures
    ]


@router.get("/factures/{facture_id}")
async def get_facture(facture_id: str, db: AsyncSession = Depends(get_db)):
    """Get CFF invoice with imputations."""
    result = await db.execute(
        select(CFFFacture).where(CFFFacture.id == facture_id)
    )
    facture = result.scalar_one_or_none()
    if not facture:
        raise HTTPException(404, "CFF facture introuvable")

    imp_result = await db.execute(
        select(CFFImputationAssocie).where(
            CFFImputationAssocie.facture_id == facture_id
        )
    )
    imputations = imp_result.scalars().all()

    return {
        "id": facture.id,
        "entreprise_id": facture.entreprise_id,
        "montant_ht": float(facture.montant_ht),
        "cff_tva": float(facture.cff_tva),
        "cff_ibs": float(facture.cff_ibs),
        "cff_tap": float(facture.cff_tap),
        "cff_cnas": float(facture.cff_cnas),
        "cff_timbre": float(facture.cff_timbre),
        "cff_total": float(facture.cff_total),
        "hash_sha256": facture.hash_sha256,
        "imputations": [
            {
                "associe_id": i.associe_id,
                "pourcentage_entreprise": float(i.pourcentage_entreprise),
                "montant_impute": float(i.montant_impute),
            }
            for i in imputations
        ],
    }
