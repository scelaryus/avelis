# GAP 5 — ALGORITHME DE CLÔTURE MENSUELLE — cloture_service.py
"""Monthly closing service with 7-step algorithm.

Steps:
  1. Extract TNM from centre_cout_mensuel
  2. Double computation verification
  3. Compute montant_a_liberer (50% of TNM if positive)
  4. Distribute to associates pro-rata their shares
  5. Update solde_disponible_retrait = 50% of positive solde_global
  6. SHA-256 hash verification
  7. Record ClotureMensuelle
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import CentreCoutMensuel, Projet, Exercice, EntrepriseAssocie
from app.models.finance_associes import (
    ClotureMensuelle, StatutCloture,
    MouvementCompteCourant, TypeMouvement,
    CompteCourantAssocie,
)
from app.services.blocking_rules import BlockingError

logger = structlog.get_logger(__name__)

QUANTIZE_2 = Decimal(1) / Decimal(100)  # 2-decimal quantizer


async def executer_cloture_mensuelle(
    projet_id: str,
    mois: int,
    annee: int,
    created_by: str,
    db: AsyncSession,
    est_test_fictif: bool = False,
) -> ClotureMensuelle:
    """Execute the full 7-step monthly closing algorithm."""
    t0 = time.monotonic()

    # ── ÉTAPE 1: Extract TNM from centre_cout_mensuel ───────────────────
    ccm_result = await db.execute(
        select(CentreCoutMensuel).where(
            CentreCoutMensuel.projet_id == projet_id,
            CentreCoutMensuel.mois == mois,
            CentreCoutMensuel.annee == annee,
        )
    )
    ccm = ccm_result.scalar_one_or_none()
    if not ccm:
        raise BlockingError(
            f"Données centre de coût manquantes pour projet={projet_id}, "
            f"mois={mois}, année={annee}"
        )

    TNM = Decimal(str(ccm.resultat_ultra_reel))

    # ── ÉTAPE 2: Double computation indépendante ────────────────────────
    enc_rd = Decimal(str(ccm.encaissements_rd or 0))
    enc_rnd = Decimal(str(ccm.encaissements_rnd or 0))
    gains_cnt = Decimal(str(ccm.gains_contentieux or 0))
    lib_transit = Decimal(str(ccm.liberations_transit or 0))

    dec_rd = Decimal(str(ccm.decaissements_rd or 0))
    dec_rnd = Decimal(str(ccm.decaissements_rnd or 0))
    cout_fd = Decimal(str(ccm.cout_fictif_fd or 0))
    pertes_cnt = Decimal(str(ccm.pertes_contentieux or 0))
    stock_cump = Decimal(str(ccm.stock_consomme_cump or 0))
    masse_sal = Decimal(str(ccm.masse_salariale_directe or 0))
    cc_montant = Decimal(str(ccm.charges_communes_montant or 0))

    TNM_verif = (
        enc_rd + enc_rnd + gains_cnt + lib_transit
        - dec_rd - dec_rnd - cout_fd - pertes_cnt
        - stock_cump - masse_sal - cc_montant
    )

    ecart = abs(TNM - TNM_verif)
    double_ok = ecart <= Decimal("0.00")  # GFI v7.0: STRICT 0.00 DA tolerance
    if not double_ok:
        raise BlockingError(
            f"Divergence double computation : TNM={TNM}, TNM_verif={TNM_verif}, "
            f"écart={ecart} (tolérance=0.00 DA)"
        )

    # ── ÉTAPE 3: Calcul montant à libérer ──────────────────────────────
    pct_liberation = Decimal("50.00")
    if TNM > 0:
        montant_a_liberer = (TNM * pct_liberation / 100).quantize(QUANTIZE_2, ROUND_HALF_UP)
    else:
        montant_a_liberer = Decimal("0")

    # ── ÉTAPE 4: Distribution aux associés (% ENTREPRISE, pas % projet) ─
    # GFI v7.0: distribution uses EntrepriseAssocie.pourcentage (enterprise %)
    projet_result_pre = await db.execute(
        select(Projet).where(Projet.id == projet_id)
    )
    projet_pre = projet_result_pre.scalar_one_or_none()
    if not projet_pre:
        raise BlockingError(f"Projet {projet_id} introuvable")

    parts_result = await db.execute(
        select(EntrepriseAssocie).where(
            EntrepriseAssocie.entreprise_id == projet_pre.entreprise_id,
            EntrepriseAssocie.est_actif == True,
        )
    )
    parts = parts_result.scalars().all()
    if not parts and montant_a_liberer > 0:
        raise BlockingError(
            "Aucune participation entreprise trouvée — impossible de distribuer. "
            "Utilisez entreprise_associes (% entreprise), pas parts_projets (% projet)."
        )

    detail_distribution: list[dict] = []
    total_distribue = Decimal("0")

    for part in parts:
        pct = Decimal(str(part.pourcentage))
        quote = (montant_a_liberer * pct / 100).quantize(QUANTIZE_2, ROUND_HALF_UP)
        total_distribue += quote
        detail_distribution.append({
            "associe_id": str(part.associe_id),
            "parts_pct": float(pct),
            "montant": float(quote),
            "source": "entreprise_associes",  # GFI v7.0: % entreprise
        })

    # Correction écart arrondi sur dernier associé
    ecart = montant_a_liberer - total_distribue
    if abs(ecart) > Decimal("0.00"):
        raise BlockingError(f"Écart arrondi non récupérable : {ecart}")
    if ecart != 0 and detail_distribution:
        detail_distribution[-1]["montant"] = float(
            Decimal(str(detail_distribution[-1]["montant"])) + ecart
        )

    # Resolve exercice
    exercice_result = await db.execute(
        select(Exercice).where(
            Exercice.annee == annee,
        ).limit(1)
    )
    exercice = exercice_result.scalar_one_or_none()
    exercice_id = exercice.id if exercice else ccm.exercice_id

    # Resolve entreprise
    projet_result = await db.execute(
        select(Projet).where(Projet.id == projet_id)
    )
    projet = projet_result.scalar_one_or_none()
    entreprise_id = projet.entreprise_id if projet else ccm.entreprise_id

    # INSERT mouvements LIBERATION_BENEFICE for each associate
    if montant_a_liberer > 0:
        for entry in detail_distribution:
            dest_montant = Decimal(str(entry["montant"]))
            if dest_montant <= 0:
                continue

            # Find or create compte courant
            cc_result = await db.execute(
                select(CompteCourantAssocie).where(
                    CompteCourantAssocie.associe_id == entry["associe_id"],
                    CompteCourantAssocie.is_deleted == False,
                )
            )
            cc = cc_result.scalar_one_or_none()
            if not cc:
                cc = CompteCourantAssocie(
                    id=str(uuid.uuid4()),
                    associe_id=entry["associe_id"],
                )
                db.add(cc)
                await db.flush()

            mvt = MouvementCompteCourant(
                id=str(uuid.uuid4()),
                compte_courant_id=cc.id,
                associe_id=entry["associe_id"],
                projet_id=projet_id,
                entreprise_id=entreprise_id,
                exercice_id=exercice_id,
                type_mouvement=TypeMouvement.LIBERATION_BENEFICE,
                montant=dest_montant,
                sens="CREDIT",
                date_mouvement=date(annee, mois, 1),
                description=f"Libération bénéfice clôture {mois:02d}/{annee}",
                est_test_fictif=est_test_fictif,
                created_by=created_by,
            )
            db.add(mvt)

    await db.flush()

    # ── ÉTAPE 5: Update solde_disponible_retrait ────────────────────────
    # = 50% of positive solde_global
    if montant_a_liberer > 0:
        for entry in detail_distribution:
            cc_result = await db.execute(
                select(CompteCourantAssocie).where(
                    CompteCourantAssocie.associe_id == entry["associe_id"],
                    CompteCourantAssocie.is_deleted == False,
                )
            )
            cc = cc_result.scalar_one_or_none()
            if cc:
                # Recalculate solde_global from movements
                from sqlalchemy import case, func as sa_func
                solde_result = await db.execute(
                    select(
                        sa_func.coalesce(
                            sa_func.sum(
                                case(
                                    (MouvementCompteCourant.sens == "CREDIT",
                                     MouvementCompteCourant.montant),
                                    else_=-MouvementCompteCourant.montant,
                                )
                            ),
                            0,
                        )
                    ).where(
                        MouvementCompteCourant.compte_courant_id == cc.id,
                    )
                )
                solde = Decimal(str(solde_result.scalar()))
                cc.solde_global = solde
                if solde > 0:
                    cc.solde_disponible_retrait = (solde * Decimal("50") / 100).quantize(
                        QUANTIZE_2, ROUND_HALF_UP
                    )
                else:
                    cc.solde_disponible_retrait = Decimal("0")
                cc.derniere_cloture_maj = date(annee, mois, 1)

    # ── ÉTAPE 6: Hash SHA-256 ──────────────────────────────────────────
    hash_input = (
        f"{projet_id}{mois}{annee}{TNM}{montant_a_liberer}"
        f"{json.dumps(detail_distribution, sort_keys=True)}"
    )
    hash_val = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    # ── ÉTAPE 7: Record clôture ────────────────────────────────────────
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    cloture = ClotureMensuelle(
        id=str(uuid.uuid4()),
        projet_id=projet_id,
        entreprise_id=entreprise_id,
        exercice_id=exercice_id or str(uuid.uuid4()),
        mois=mois,
        annee=annee,
        tresorerie_nette_mois=TNM,
        montant_a_liberer=montant_a_liberer,
        pourcentage_liberation=pct_liberation,
        detail_distribution=detail_distribution,
        hash_verification=hash_val,
        double_computation_ok=double_ok,
        # GFI v7.0: store both computations + ecart
        tnm_calcul_1=TNM,
        tnm_calcul_2=TNM_verif,
        ecart_computation=ecart,
        etape_courante=7,
        statut=StatutCloture.SUCCES,
        date_execution=datetime.utcnow(),
        duree_execution_ms=elapsed_ms,
        est_test_fictif=est_test_fictif,
        created_by=created_by,
    )
    db.add(cloture)
    await db.flush()

    logger.info(
        "cloture_mensuelle_ok",
        projet_id=projet_id,
        mois=mois,
        annee=annee,
        tnm=float(TNM),
        montant_libere=float(montant_a_liberer),
        hash=hash_val,
    )

    return cloture


async def run_monthly_clotures_all(db: AsyncSession) -> list[ClotureMensuelle]:
    """Run monthly clôture for all active projects (called by scheduler)."""
    from datetime import date as date_type

    today = date_type.today()
    # Clôture for the previous month
    if today.month == 1:
        target_mois = 12
        target_annee = today.year - 1
    else:
        target_mois = today.month - 1
        target_annee = today.year

    result = await db.execute(
        select(Projet).where(Projet.is_active == True)
    )
    projets = result.scalars().all()

    clotures = []
    for projet in projets:
        try:
            cloture = await executer_cloture_mensuelle(
                projet_id=projet.id,
                mois=target_mois,
                annee=target_annee,
                created_by="system_scheduler",
                db=db,
            )
            clotures.append(cloture)
        except BlockingError as exc:
            logger.warning(
                "cloture_skipped",
                projet_id=projet.id,
                reason=str(exc),
            )
        except Exception as exc:
            logger.error(
                "cloture_error",
                projet_id=projet.id,
                error=str(exc),
            )

    return clotures
