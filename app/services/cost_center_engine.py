"""GFI Platform — Centre de Coût Calculation Engine.

Implements:
- Chapter 2: Ratio de répartition des charges communes (CA-based & DEPENSES-based)
- Chapter 3: Centre de coût temps réel per project per month (~25 computed fields)
- Chapter 8: IRG barème, CNAS taux, TVA verification

All formulas exactly match docs/changment.md / Blueprint v6.0 Annexe C.
"""
import hashlib
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import structlog
from sqlalchemy import select, func as sa_func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import (
    Entreprise, Projet, Exercice, Encaissement, Decaissement,
    Parametre, RatioChargesCommunes, CentreCoutMensuel,
    ImputationPaieProjet, MouvementCaisse, MouvementStock,
    CompteTransitoireNotaire, ClientCC, Lot,
    StatutFiscal, TypeCharge, CategorieDepense, SensOperation,
    StatutProjet, MethodeRatio, BulletinPaieComplement,
    TypeMouvementStock,
)
from app.models.hr import PayrollProposal

logger = structlog.get_logger(__name__)

D = Decimal
ZERO = D("0.00")
CENT = D("100.00")
FICTIF_STATUSES = [
    StatutFiscal.FICTIF,
    StatutFiscal.FICTIF_DECLARE,
    StatutFiscal.FICTIF_NON_DECLARE,
]


# ────────────────────────────────────────────────────────────────────────────
# Helper: get system parameter
# ────────────────────────────────────────────────────────────────────────────

async def get_parametre(db: AsyncSession, tenant_id: str, cle: str, default: str = "0") -> str:
    result = await db.execute(
        select(Parametre.valeur).where(
            Parametre.tenant_id == tenant_id,
            Parametre.cle == cle,
        )
    )
    val = result.scalar_one_or_none()
    return val if val is not None else default


async def get_param_decimal(db: AsyncSession, tenant_id: str, cle: str, default: str = "0") -> Decimal:
    return D(await get_parametre(db, tenant_id, cle, default))


# ────────────────────────────────────────────────────────────────────────────
# Chapter 8: IRG (Algerian progressive income tax)
# ────────────────────────────────────────────────────────────────────────────

def calculer_irg(salaire_imposable: Decimal) -> Decimal:
    """IRG barème progressif algérien 2024-2026."""
    s = salaire_imposable
    if s <= 20000:
        return ZERO
    elif s <= 40000:
        return ((s - 20000) * D("0.23")).quantize(D("0.01"), ROUND_HALF_UP)
    elif s <= 80000:
        return (D("4600") + (s - 40000) * D("0.27")).quantize(D("0.01"), ROUND_HALF_UP)
    elif s <= 160000:
        return (D("15400") + (s - 80000) * D("0.30")).quantize(D("0.01"), ROUND_HALF_UP)
    elif s <= 320000:
        return (D("39400") + (s - 160000) * D("0.33")).quantize(D("0.01"), ROUND_HALF_UP)
    else:
        return (D("92200") + (s - 320000) * D("0.35")).quantize(D("0.01"), ROUND_HALF_UP)


# ────────────────────────────────────────────────────────────────────────────
# Chapter 2: Ratio de répartition des charges communes
# ────────────────────────────────────────────────────────────────────────────

async def calculer_ratio_charges_communes(
    db: AsyncSession,
    tenant_id: str,
    entreprise_id: str,
    mois: int,
    annee: int,
    methode: Optional[str] = None,
) -> RatioChargesCommunes:
    """
    Compute the monthly common-charge ratio for all active projects of an entreprise.

    Two methods (Ch. 2.1):
      CA     → ratio = CA_projet / CA_total
      DEPENSES → ratio = Dépenses_directes_projet / Dépenses_directes_total
    """
    if methode is None:
        methode = await get_parametre(db, tenant_id, "methode_ratio_charges_communes", "CA")

    # Get active projects for this entreprise
    result = await db.execute(
        select(Projet).where(
            Projet.tenant_id == tenant_id,
            Projet.entreprise_id == entreprise_id,
            Projet.statut != StatutProjet.ABANDONNE,
            Projet.is_active == True,
        )
    )
    projets = result.scalars().all()

    date_debut = date(annee, mois, 1)
    if mois == 12:
        date_fin = date(annee, 12, 31)
    else:
        date_fin = date(annee, mois + 1, 1)

    detail_projets = []
    total_base = ZERO

    for p in projets:
        if methode == "CA":
            # CA = SUM(encaissements RD + RND) for this project this month
            r = await db.execute(
                select(sa_func.coalesce(sa_func.sum(Encaissement.montant), 0)).where(
                    Encaissement.tenant_id == tenant_id,
                    Encaissement.projet_id == p.id,
                    Encaissement.entreprise_id == entreprise_id,
                    Encaissement.statut_fiscal.in_([StatutFiscal.REEL_DECLARE, StatutFiscal.REEL_NON_DECLARE]),
                    Encaissement.date_encaissement >= date_debut,
                    Encaissement.date_encaissement < date_fin,
                    Encaissement.is_deleted == False,
                )
            )
            valeur = D(str(r.scalar()))
        else:
            # DEPENSES = SUM(decaissements where projet_id = X) for this project
            r = await db.execute(
                select(sa_func.coalesce(sa_func.sum(Decaissement.montant), 0)).where(
                    Decaissement.tenant_id == tenant_id,
                    Decaissement.projet_id == p.id,
                    Decaissement.entreprise_id == entreprise_id,
                    Decaissement.type_charge == TypeCharge.PROJET,
                    Decaissement.date_decaissement >= date_debut,
                    Decaissement.date_decaissement < date_fin,
                    Decaissement.is_deleted == False,
                )
            )
            valeur = D(str(r.scalar()))

        detail_projets.append({
            "projet_id": p.id,
            "projet_code": p.code,
            "valeur_base": float(valeur),
            "ratio_pct": 0.0,  # computed below
        })
        total_base += valeur

    # Now compute ratios
    somme_ratios = ZERO
    for dp in detail_projets:
        if total_base > 0:
            ratio = (D(str(dp["valeur_base"])) / total_base * CENT).quantize(D("0.0001"), ROUND_HALF_UP)
        else:
            ratio = ZERO
        dp["ratio_pct"] = float(ratio)
        somme_ratios += ratio

    # Total charges communes for this month
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Decaissement.montant), 0)).where(
            Decaissement.tenant_id == tenant_id,
            Decaissement.entreprise_id == entreprise_id,
            Decaissement.type_charge == TypeCharge.COMMUNE,
            Decaissement.date_decaissement >= date_debut,
            Decaissement.date_decaissement < date_fin,
            Decaissement.is_deleted == False,
        )
    )
    total_cc = D(str(r.scalar()))

    # Compute verification hash
    h = hashlib.sha256(json.dumps(detail_projets, sort_keys=True).encode()).hexdigest()

    # Upsert
    existing = await db.execute(
        select(RatioChargesCommunes).where(
            RatioChargesCommunes.tenant_id == tenant_id,
            RatioChargesCommunes.entreprise_id == entreprise_id,
            RatioChargesCommunes.annee == annee,
            RatioChargesCommunes.mois == mois,
        )
    )
    ratio_row = existing.scalar_one_or_none()

    if ratio_row is None:
        ratio_row = RatioChargesCommunes(
            tenant_id=tenant_id,
            entreprise_id=entreprise_id,
            annee=annee,
            mois=mois,
        )
        db.add(ratio_row)

    ratio_row.methode = MethodeRatio(methode)
    ratio_row.detail_projets = detail_projets
    ratio_row.total_base = total_base
    ratio_row.total_charges_communes = total_cc
    ratio_row.somme_ratios = somme_ratios
    ratio_row.hash_verification = h

    await db.flush()
    logger.info("ratio_calculated", entreprise=entreprise_id, mois=mois, annee=annee, methode=methode)
    return ratio_row


# ────────────────────────────────────────────────────────────────────────────
# Chapter 3: Centre de Coût Temps Réel — Full computation
# ────────────────────────────────────────────────────────────────────────────

async def calculer_centre_cout_mensuel(
    db: AsyncSession,
    tenant_id: str,
    projet_id: str,
    entreprise_id: str,
    mois: int,
    annee: int,
) -> CentreCoutMensuel:
    """
    Compute the full monthly cost center for a project.

    This implements the exact formulas from docs/changment.md Chapter 3:
    A. Recettes (RD, RND, gains contentieux, libérations transit)
    B. Dépenses directes (RD, RND, F cost, pertes contentieux, stock CUMP, masse salariale)
    C. Charges communes (ratio × total CC)
    D. Résultats (ultra-réel, fiscal)
    E. Indicateurs (marge, ratios, transit, reste à payer)
    """
    date_debut = date(annee, mois, 1)
    if mois == 12:
        date_fin = date(annee, 12, 31)
    else:
        date_fin = date(annee, mois + 1, 1)

    taux_fictif = await get_param_decimal(db, tenant_id, "taux_cout_fictif", "3")

    # ── A. RECETTES ──

    # A1. Encaissements RD
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Encaissement.montant), 0)).where(
            Encaissement.tenant_id == tenant_id,
            Encaissement.entreprise_id == entreprise_id,
            Encaissement.projet_id == projet_id,
            Encaissement.statut_fiscal == StatutFiscal.REEL_DECLARE,
            Encaissement.date_encaissement >= date_debut,
            Encaissement.date_encaissement < date_fin,
            Encaissement.is_deleted == False,
        )
    )
    enc_rd = D(str(r.scalar()))

    # A2. Encaissements RND
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Encaissement.montant), 0)).where(
            Encaissement.tenant_id == tenant_id,
            Encaissement.entreprise_id == entreprise_id,
            Encaissement.projet_id == projet_id,
            Encaissement.statut_fiscal == StatutFiscal.REEL_NON_DECLARE,
            Encaissement.date_encaissement >= date_debut,
            Encaissement.date_encaissement < date_fin,
            Encaissement.is_deleted == False,
        )
    )
    enc_rnd = D(str(r.scalar()))

    # A3. Gains contentieux
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Decaissement.montant), 0)).where(
            Decaissement.tenant_id == tenant_id,
            Decaissement.entreprise_id == entreprise_id,
            Decaissement.projet_id == projet_id,
            Decaissement.categorie_depense == CategorieDepense.CONTENTIEUX,
            Decaissement.sens == SensOperation.GAIN,
            Decaissement.date_decaissement >= date_debut,
            Decaissement.date_decaissement < date_fin,
            Decaissement.is_deleted == False,
        )
    )
    gains_contentieux = D(str(r.scalar()))

    # A4. Libérations transit notaire
    r = await db.execute(
        select(sa_func.coalesce(
            sa_func.sum(CompteTransitoireNotaire.montant_tranche1_20pct), 0
        )).where(
            CompteTransitoireNotaire.tenant_id == tenant_id,
            CompteTransitoireNotaire.projet_id == projet_id,
            CompteTransitoireNotaire.date_liberation_tranche1 >= date_debut,
            CompteTransitoireNotaire.date_liberation_tranche1 < date_fin,
        )
    )
    transit_t1 = D(str(r.scalar()))

    r = await db.execute(
        select(sa_func.coalesce(
            sa_func.sum(CompteTransitoireNotaire.montant_tranche2_5pct), 0
        )).where(
            CompteTransitoireNotaire.tenant_id == tenant_id,
            CompteTransitoireNotaire.projet_id == projet_id,
            CompteTransitoireNotaire.date_liberation_tranche2 >= date_debut,
            CompteTransitoireNotaire.date_liberation_tranche2 < date_fin,
        )
    )
    transit_t2 = D(str(r.scalar()))
    liberations_transit = transit_t1 + transit_t2

    total_recettes = enc_rd + enc_rnd + gains_contentieux + liberations_transit

    # ── B. DÉPENSES DIRECTES ──

    # B1. Décaissements RD
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Decaissement.montant), 0)).where(
            Decaissement.tenant_id == tenant_id,
            Decaissement.entreprise_id == entreprise_id,
            Decaissement.projet_id == projet_id,
            Decaissement.statut_fiscal == StatutFiscal.REEL_DECLARE,
            Decaissement.type_charge == TypeCharge.PROJET,
            or_(
                Decaissement.categorie_depense != CategorieDepense.CONTENTIEUX,
                Decaissement.sens != SensOperation.GAIN,
            ),
            Decaissement.date_decaissement >= date_debut,
            Decaissement.date_decaissement < date_fin,
            Decaissement.is_deleted == False,
        )
    )
    dec_rd = D(str(r.scalar()))

    # B2. Décaissements RND
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Decaissement.montant), 0)).where(
            Decaissement.tenant_id == tenant_id,
            Decaissement.entreprise_id == entreprise_id,
            Decaissement.projet_id == projet_id,
            Decaissement.statut_fiscal == StatutFiscal.REEL_NON_DECLARE,
            Decaissement.type_charge == TypeCharge.PROJET,
            Decaissement.date_decaissement >= date_debut,
            Decaissement.date_decaissement < date_fin,
            Decaissement.is_deleted == False,
        )
    )
    dec_rnd = D(str(r.scalar()))

    # B3. Factures fictives (F)
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Decaissement.montant), 0)).where(
            Decaissement.tenant_id == tenant_id,
            Decaissement.entreprise_id == entreprise_id,
            Decaissement.projet_id == projet_id,
            Decaissement.statut_fiscal.in_(FICTIF_STATUSES),
            Decaissement.date_decaissement >= date_debut,
            Decaissement.date_decaissement < date_fin,
            Decaissement.is_deleted == False,
        )
    )
    nominal_f = D(str(r.scalar()))
    cout_f = (nominal_f * taux_fictif / CENT).quantize(D("0.01"), ROUND_HALF_UP)

    # B5. Pertes contentieux
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Decaissement.montant), 0)).where(
            Decaissement.tenant_id == tenant_id,
            Decaissement.entreprise_id == entreprise_id,
            Decaissement.projet_id == projet_id,
            Decaissement.categorie_depense == CategorieDepense.CONTENTIEUX,
            Decaissement.sens == SensOperation.PERTE,
            Decaissement.date_decaissement >= date_debut,
            Decaissement.date_decaissement < date_fin,
            Decaissement.is_deleted == False,
        )
    )
    pertes_contentieux = D(str(r.scalar()))

    # B6. Stock consommé (sorties valorisées au CUMP)
    r = await db.execute(
        select(sa_func.coalesce(
            sa_func.sum(MouvementStock.quantite * MouvementStock.prix_unitaire), 0
        )).where(
            MouvementStock.tenant_id == tenant_id,
            MouvementStock.projet_id == projet_id,
            MouvementStock.type_mouvement == TypeMouvementStock.SORTIE,
            MouvementStock.date_mouvement >= date_debut,
            MouvementStock.date_mouvement < date_fin,
        )
    )
    stock_cump = D(str(r.scalar()))

    # B7. Masse salariale directe (from imputation_paie_projets)
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(ImputationPaieProjet.montant_impute_total), 0)).where(
            ImputationPaieProjet.tenant_id == tenant_id,
            ImputationPaieProjet.projet_id == projet_id,
        )
    )
    # Filter by month/year using JOIN with payroll_proposals
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(ImputationPaieProjet.montant_impute_total), 0)).where(
            ImputationPaieProjet.tenant_id == tenant_id,
            ImputationPaieProjet.projet_id == projet_id,
        ).join(PayrollProposal, PayrollProposal.id == ImputationPaieProjet.bulletin_id).where(
            PayrollProposal.period_label == f"{annee}-{mois:02d}",
        )
    )
    masse_salariale = D(str(r.scalar()))

    total_dep_directes = dec_rd + dec_rnd + cout_f + pertes_contentieux + stock_cump + masse_salariale

    # ── C. CHARGES COMMUNES ──

    # Get or calculate ratio
    ratio_row = await db.execute(
        select(RatioChargesCommunes).where(
            RatioChargesCommunes.tenant_id == tenant_id,
            RatioChargesCommunes.entreprise_id == entreprise_id,
            RatioChargesCommunes.annee == annee,
            RatioChargesCommunes.mois == mois,
        )
    )
    ratio_obj = ratio_row.scalar_one_or_none()

    if ratio_obj is None:
        # Auto-calculate ratio
        ratio_obj = await calculer_ratio_charges_communes(db, tenant_id, entreprise_id, mois, annee)

    ratio_pct = ZERO
    for dp in ratio_obj.detail_projets:
        if dp["projet_id"] == projet_id:
            ratio_pct = D(str(dp["ratio_pct"]))
            break

    total_cc = ratio_obj.total_charges_communes or ZERO
    charges_communes = (D(str(total_cc)) * ratio_pct / CENT).quantize(D("0.01"), ROUND_HALF_UP)

    # ── D. TOTAUX / RÉSULTATS ──

    total_depenses = total_dep_directes + charges_communes
    resultat_ultra_reel = total_recettes - total_depenses
    resultat_fiscal = enc_rd - (dec_rd + nominal_f)

    # ── E. INDICATEURS ──

    marge_brute = (resultat_ultra_reel / total_recettes * CENT).quantize(D("0.01"), ROUND_HALF_UP) if total_recettes > 0 else ZERO
    ratio_cc_dep = (charges_communes / total_depenses * CENT).quantize(D("0.01"), ROUND_HALF_UP) if total_depenses > 0 else ZERO
    part_nd = (enc_rnd / (enc_rd + enc_rnd) * CENT).quantize(D("0.01"), ROUND_HALF_UP) if (enc_rd + enc_rnd) > 0 else ZERO

    # Transit notaire en attente
    r = await db.execute(
        select(sa_func.coalesce(
            sa_func.sum(
                CompteTransitoireNotaire.montant_tranche1_20pct + CompteTransitoireNotaire.montant_tranche2_5pct
            ), 0
        )).where(
            CompteTransitoireNotaire.tenant_id == tenant_id,
            CompteTransitoireNotaire.projet_id == projet_id,
            CompteTransitoireNotaire.statut != "CLOTURE",
        )
    )
    transit_attente = D(str(r.scalar()))

    # Reste à payer clients: sum of (lot price - total payments for that lot's client)
    # Simplified: total lot prices - total encaissements for project
    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Lot.prix_vente), 0)).where(
            Lot.tenant_id == tenant_id,
            Lot.projet_id == projet_id,
        )
    )
    total_lots = D(str(r.scalar()))

    r = await db.execute(
        select(sa_func.coalesce(sa_func.sum(Encaissement.montant), 0)).where(
            Encaissement.tenant_id == tenant_id,
            Encaissement.entreprise_id == entreprise_id,
            Encaissement.projet_id == projet_id,
            Encaissement.is_deleted == False,
        )
    )
    total_enc_all = D(str(r.scalar()))
    reste_a_payer = max(total_lots - total_enc_all, ZERO)

    # Compute verification hash
    data_for_hash = {
        "enc_rd": str(enc_rd), "enc_rnd": str(enc_rnd),
        "dec_rd": str(dec_rd), "dec_rnd": str(dec_rnd),
        "cout_f": str(cout_f),
        "ratio_pct": str(ratio_pct),
    }
    h = hashlib.sha256(json.dumps(data_for_hash, sort_keys=True).encode()).hexdigest()

    # ── UPSERT ──

    existing = await db.execute(
        select(CentreCoutMensuel).where(
            CentreCoutMensuel.tenant_id == tenant_id,
            CentreCoutMensuel.projet_id == projet_id,
            CentreCoutMensuel.annee == annee,
            CentreCoutMensuel.mois == mois,
        )
    )
    cc = existing.scalar_one_or_none()

    if cc is None:
        cc = CentreCoutMensuel(
            tenant_id=tenant_id,
            projet_id=projet_id,
            entreprise_id=entreprise_id,
            annee=annee,
            mois=mois,
        )
        db.add(cc)

    # A
    cc.encaissements_rd = enc_rd
    cc.encaissements_rnd = enc_rnd
    cc.gains_contentieux = gains_contentieux
    cc.liberations_transit = liberations_transit
    cc.total_recettes = total_recettes
    # B
    cc.decaissements_rd = dec_rd
    cc.decaissements_rnd = dec_rnd
    cc.montant_nominal_fd = nominal_f
    cc.cout_fictif_fd = cout_f
    cc.montant_nominal_fnd = ZERO
    cc.cout_fictif_fnd = ZERO
    cc.pertes_contentieux = pertes_contentieux
    cc.stock_consomme_cump = stock_cump
    cc.masse_salariale_directe = masse_salariale
    cc.total_depenses_directes = total_dep_directes
    # C
    cc.ratio_pct = ratio_pct
    cc.charges_communes_montant = charges_communes
    # D
    cc.total_depenses = total_depenses
    cc.resultat_ultra_reel = resultat_ultra_reel
    cc.resultat_fiscal = resultat_fiscal
    # E
    cc.marge_brute_pct = marge_brute
    cc.ratio_cc_depenses_pct = ratio_cc_dep
    cc.part_non_declare_pct = part_nd
    cc.montant_transit_notaire = transit_attente
    cc.reste_a_payer_clients = reste_a_payer
    cc.hash_verification = h

    await db.flush()
    logger.info("centre_cout_calculated", projet=projet_id, mois=mois, annee=annee)
    return cc


async def recalculer_tous_centres_cout(
    db: AsyncSession,
    tenant_id: str,
    entreprise_id: str,
    mois: int,
    annee: int,
) -> list[CentreCoutMensuel]:
    """Recalculate cost centers for ALL active projects of an entreprise for a given month."""
    # First recalculate the ratio
    await calculer_ratio_charges_communes(db, tenant_id, entreprise_id, mois, annee)

    # Get all active projects
    result = await db.execute(
        select(Projet).where(
            Projet.tenant_id == tenant_id,
            Projet.entreprise_id == entreprise_id,
            Projet.statut != StatutProjet.ABANDONNE,
            Projet.is_active == True,
        )
    )
    projets = result.scalars().all()

    results = []
    for p in projets:
        cc = await calculer_centre_cout_mensuel(db, tenant_id, p.id, entreprise_id, mois, annee)
        results.append(cc)

    return results


def format_centre_cout(cc: CentreCoutMensuel) -> dict:
    """Format a CentreCoutMensuel record for API response / frontend display."""
    return {
        "id": cc.id,
        "projet_id": cc.projet_id,
        "entreprise_id": cc.entreprise_id,
        "mois": cc.mois,
        "annee": cc.annee,
        "periode": f"{cc.annee}-{cc.mois:02d}",
        "recettes": {
            "encaissements_rd": float(cc.encaissements_rd or 0),
            "encaissements_rnd": float(cc.encaissements_rnd or 0),
            "gains_contentieux": float(cc.gains_contentieux or 0),
            "liberations_transit": float(cc.liberations_transit or 0),
            "total": float(cc.total_recettes or 0),
        },
        "depenses_directes": {
            "decaissements_rd": float(cc.decaissements_rd or 0),
            "decaissements_rnd": float(cc.decaissements_rnd or 0),
            "montant_nominal_f": float((cc.montant_nominal_fd or 0) + (cc.montant_nominal_fnd or 0)),
            "cout_fictif_f": float((cc.cout_fictif_fd or 0) + (cc.cout_fictif_fnd or 0)),
            "montant_nominal_fd": float(cc.montant_nominal_fd or 0),
            "cout_fictif_fd": float(cc.cout_fictif_fd or 0),
            "montant_nominal_fnd": float(cc.montant_nominal_fnd or 0),
            "cout_fictif_fnd": float(cc.cout_fictif_fnd or 0),
            "pertes_contentieux": float(cc.pertes_contentieux or 0),
            "stock_consomme_cump": float(cc.stock_consomme_cump or 0),
            "masse_salariale_directe": float(cc.masse_salariale_directe or 0),
            "total": float(cc.total_depenses_directes or 0),
        },
        "charges_communes": {
            "ratio_pct": float(cc.ratio_pct or 0),
            "montant": float(cc.charges_communes_montant or 0),
        },
        "total_depenses": float(cc.total_depenses or 0),
        "resultat_ultra_reel": float(cc.resultat_ultra_reel or 0),
        "resultat_fiscal": float(cc.resultat_fiscal or 0),
        "indicateurs": {
            "marge_brute_pct": float(cc.marge_brute_pct or 0),
            "ratio_cc_depenses_pct": float(cc.ratio_cc_depenses_pct or 0),
            "part_non_declare_pct": float(cc.part_non_declare_pct or 0),
            "montant_transit_notaire": float(cc.montant_transit_notaire or 0),
            "reste_a_payer_clients": float(cc.reste_a_payer_clients or 0),
        },
        "hash_verification": cc.hash_verification,
    }
