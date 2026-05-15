"""GFI v7.0 — CFF Engine (Charges Fiscales & Financières).

CFF = % entreprise (NEVER % projet) + Yamina=0 in DBPI/OC/EP/SEN/BIM

Kill tests:
  KT-01: Yamina CFF = 0 DA in {SARL-DBPI, SARL-OC, SARL-EP, SARL-SEN, EURL-BIM}
  KT-02: Ahmed SARL-DP = 25% enterprise, NOT 60% project
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cff import CFFFacture, CFFImputationAssocie
from app.models.financial import EntrepriseAssocie, Entreprise
from app.services.blocking_rules import BlockingError

QUANTIZE_2 = Decimal("0.01")

# Enterprises where Yamina (associé D) must have 0% CFF
YAMINA_ZERO_ENTERPRISES = {"SARL-DBPI", "SARL-OC", "SARL-EP", "SARL-SEN", "EURL-BIM"}


@dataclass
class CFFImputationResult:
    associe_id: str
    pourcentage_entreprise: float
    montant_impute: float


@dataclass
class CFFCalculResult:
    montant_ht: float
    cff_tva: float
    cff_ibs: float
    cff_tap: float
    cff_cnas: float
    cff_timbre: float
    cff_total: float
    imputations: list[CFFImputationResult] = field(default_factory=list)


class CFFEngine:
    """Compute CFF (Charges Fiscales & Financières) for an enterprise.

    CFF is distributed by ENTERPRISE ownership % — never by project %.
    """

    def __init__(
        self,
        taux_tva: float = 0.19,
        taux_ibs: float = 0.19,
        taux_tap: float = 0.02,
        taux_cnas_patronal: float = 0.26,
        appliquer_cnas: bool = False,
        appliquer_timbre: bool = True,
        montant_timbre_fixe: float = 15000.0,
    ):
        self.taux_tva = Decimal(str(taux_tva))
        self.taux_ibs = Decimal(str(taux_ibs))
        self.taux_tap = Decimal(str(taux_tap))
        self.taux_cnas_patronal = Decimal(str(taux_cnas_patronal))
        self.appliquer_cnas = appliquer_cnas
        self.appliquer_timbre = appliquer_timbre
        self.montant_timbre_fixe = Decimal(str(montant_timbre_fixe))

    def calculer(
        self,
        montant_ht: Decimal,
        participations_entreprise: list[dict],
        entreprise_code: str = "",
    ) -> CFFCalculResult:
        """Calculate CFF and distribute to associates by enterprise %.

        Args:
            montant_ht: Invoice amount HT
            participations_entreprise: list of {associe_id, pourcentage, nom?}
            entreprise_code: enterprise code for KT-01 validation

        Returns:
            CFFCalculResult with breakdown and imputations
        """
        montant = Decimal(str(montant_ht))

        cff_tva = (montant * self.taux_tva).quantize(QUANTIZE_2, ROUND_HALF_UP)
        cff_ibs = (montant * self.taux_ibs).quantize(QUANTIZE_2, ROUND_HALF_UP)
        cff_tap = (montant * self.taux_tap).quantize(QUANTIZE_2, ROUND_HALF_UP)
        cff_cnas = (
            (montant * self.taux_cnas_patronal).quantize(QUANTIZE_2, ROUND_HALF_UP)
            if self.appliquer_cnas
            else Decimal("0")
        )
        cff_timbre = self.montant_timbre_fixe if self.appliquer_timbre else Decimal("0")

        cff_total = cff_tva + cff_ibs + cff_tap + cff_cnas + cff_timbre

        # Distribute by enterprise %
        imputations = []
        for p in participations_entreprise:
            pct = Decimal(str(p["pourcentage"]))
            imputed = (cff_total * pct / 100).quantize(QUANTIZE_2, ROUND_HALF_UP)
            imputations.append(CFFImputationResult(
                associe_id=p["associe_id"],
                pourcentage_entreprise=float(pct),
                montant_impute=float(imputed),
            ))

        return CFFCalculResult(
            montant_ht=float(montant),
            cff_tva=float(cff_tva),
            cff_ibs=float(cff_ibs),
            cff_tap=float(cff_tap),
            cff_cnas=float(cff_cnas),
            cff_timbre=float(cff_timbre),
            cff_total=float(cff_total),
            imputations=imputations,
        )

    def verifier_kt01(
        self,
        imputations: list[CFFImputationResult],
        associe_yamina_id: str,
        entreprise_code: str,
    ) -> bool:
        """KT-01: Yamina in {DBPI, OC, EP, SEN, BIM} → 0 DA.

        Returns True if KT-01 passes (Yamina has 0 DA imputed).
        """
        code_upper = entreprise_code.upper().replace(" ", "")
        is_restricted = any(k in code_upper for k in ("DBPI", "OC", "EP", "SEN", "BIM"))

        if not is_restricted:
            return True  # KT-01 only applies to these enterprises

        for imp in imputations:
            if imp.associe_id == associe_yamina_id:
                return imp.montant_impute == 0.0

        return True  # Yamina not in imputations = OK (absent from enterprise)

    def verifier_kt02(
        self,
        imputations: list[CFFImputationResult],
        associe_ahmed_id: str,
        entreprise_code: str,
        pourcentage_attendu: float = 25.0,
    ) -> bool:
        """KT-02: Ahmed SARL-DP = 25% enterprise, NOT 60% project.

        Returns True if Ahmed's imputation uses the correct enterprise %.
        """
        code_upper = entreprise_code.upper().replace(" ", "")
        if "DP" not in code_upper and "DENDANI" not in code_upper:
            return True  # KT-02 only applies to SARL-DP

        for imp in imputations:
            if imp.associe_id == associe_ahmed_id:
                return abs(imp.pourcentage_entreprise - pourcentage_attendu) < 0.01

        return True  # Ahmed not found = OK


async def calculer_et_sauvegarder_cff(
    db: AsyncSession,
    entreprise_id: str,
    montant_ht: float,
    projet_id: Optional[str] = None,
    periode_mois: Optional[str] = None,
    reference_facture: Optional[str] = None,
    created_by: Optional[str] = None,
) -> CFFFacture:
    """Calculate CFF for an enterprise and save to database."""
    # Get enterprise
    ent_result = await db.execute(
        select(Entreprise).where(Entreprise.id == entreprise_id)
    )
    entreprise = ent_result.scalar_one_or_none()
    if not entreprise:
        raise BlockingError(f"Entreprise {entreprise_id} introuvable")

    # Get enterprise participations
    parts_result = await db.execute(
        select(EntrepriseAssocie).where(
            EntrepriseAssocie.entreprise_id == entreprise_id,
            EntrepriseAssocie.est_actif == True,
        )
    )
    parts = parts_result.scalars().all()

    participations = [
        {"associe_id": p.associe_id, "pourcentage": float(p.pourcentage)}
        for p in parts
    ]

    engine = CFFEngine(
        taux_tva=float(entreprise.taux_tva or 0.19),
        taux_ibs=float(entreprise.taux_ibs or 0.19),
        taux_tap=float(entreprise.taux_tap or 0.02),
    )

    result = engine.calculer(
        Decimal(str(montant_ht)),
        participations,
        entreprise.raison_sociale,
    )

    # Hash
    hash_input = json.dumps({
        "entreprise_id": entreprise_id,
        "montant_ht": result.montant_ht,
        "cff_total": result.cff_total,
        "imputations": [
            {"associe_id": i.associe_id, "montant": i.montant_impute}
            for i in result.imputations
        ],
    }, sort_keys=True)
    hash_val = hashlib.sha256(hash_input.encode()).hexdigest()

    facture = CFFFacture(
        id=str(uuid.uuid4()),
        entreprise_id=entreprise_id,
        projet_id=projet_id,
        periode_mois=periode_mois,
        montant_ht=result.montant_ht,
        cff_tva=result.cff_tva,
        cff_ibs=result.cff_ibs,
        cff_tap=result.cff_tap,
        cff_cnas=result.cff_cnas,
        cff_timbre=result.cff_timbre,
        cff_total=result.cff_total,
        reference_facture=reference_facture,
        hash_sha256=hash_val,
        created_by=created_by,
    )
    db.add(facture)
    await db.flush()

    # Save imputations
    for imp in result.imputations:
        db.add(CFFImputationAssocie(
            id=str(uuid.uuid4()),
            facture_id=facture.id,
            associe_id=imp.associe_id,
            pourcentage_entreprise=imp.pourcentage_entreprise,
            montant_impute=imp.montant_impute,
        ))

    await db.flush()
    return facture
