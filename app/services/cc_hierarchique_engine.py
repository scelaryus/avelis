"""GFI v7.0 — Hierarchical Cost Center Engine.

Auto-builds the CC tree from enterprises/projects, computes aggregates
dynamically from existing financial data (encaissements, décaissements, CFF),
and provides consolidation views.
"""
from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import structlog
from sqlalchemy import select, func as sa_func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import (
    Entreprise, Projet, Associe, Encaissement, Decaissement,
    EntrepriseAssocie, StatutFiscal, FluxInterProjet,
    MouvementCaisse,
)
from app.models.registry import PartProjet
from app.models.cff import CFFFacture, CFFImputationAssocie
from app.models.cc_hierarchique import (
    CCNode, CCDistribution, CCImputation,
    TypeImputation, SensImputation, CategorieCC,
)

logger = structlog.get_logger(__name__)

QUANTIZE_2 = Decimal("0.01")


# ────────────────────────────────────────────────────────────────────────────
# 1. Auto-build CC tree from existing enterprises/projects
# ────────────────────────────────────────────────────────────────────────────

# Standard level-3 categories for each project
PROJECT_CATEGORIES = [
    (CategorieCC.TERRAIN, "Terrain"),
    (CategorieCC.CONSTR, "Construction"),
    (CategorieCC.COMMERCIAL, "Commercial"),
    (CategorieCC.VENTES, "Ventes"),
    (CategorieCC.ASSOC, "Prélèvements associés"),
    (CategorieCC.CFF, "CFF"),
    (CategorieCC.FISCAL, "Charges fiscales"),
    (CategorieCC.MASSE_SAL, "Masse salariale"),
    (CategorieCC.VEHICULES, "Véhicules"),
    (CategorieCC.ACHATS, "Achats & Stock"),
    (CategorieCC.DIVERS, "Divers"),
]


async def build_cc_tree(db: AsyncSession, tenant_id: str) -> dict:
    """Build the full CC tree from enterprises and projects.

    Creates nodes if they don't exist (idempotent).
    Returns summary of created nodes.
    """
    created = 0

    # Level 0: GROUPE
    root = await _get_or_create_node(
        db, tenant_id, "CC-GROUPE", "GROUPE DENDANI", 0, None, "CC-GROUPE"
    )
    if root["created"]:
        created += 1

    # Get all enterprises
    ent_result = await db.execute(
        select(Entreprise).where(Entreprise.tenant_id == tenant_id)
    )
    entreprises = ent_result.scalars().all()

    ent_map = {}  # short code → enterprise
    for idx, ent in enumerate(entreprises, 1):
        ent_code = f"ENT{idx}"
        ent_map[ent.id] = ent_code

        # Level 1: ENTREPRISE
        ent_node_code = f"CC-{ent_code}"
        ent_node = await _get_or_create_node(
            db, tenant_id, ent_node_code, ent.raison_sociale,
            1, root["id"], f"CC-GROUPE/{ent_node_code}",
            entreprise_id=ent.id,
        )
        if ent_node["created"]:
            created += 1

        # Get projects for this enterprise
        proj_result = await db.execute(
            select(Projet).where(
                Projet.entreprise_id == ent.id,
                Projet.tenant_id == tenant_id,
            )
        )
        projets = proj_result.scalars().all()

        for proj in projets:
            proj_short = _project_short_code(proj.nom or proj.code)

            # Level 2: PROJET
            proj_node_code = f"CC-{ent_code}-{proj_short}"
            proj_node = await _get_or_create_node(
                db, tenant_id, proj_node_code, proj.nom or proj.code,
                2, ent_node["id"],
                f"CC-GROUPE/{ent_node_code}/{proj_node_code}",
                entreprise_id=ent.id, projet_id=proj.id,
            )
            if proj_node["created"]:
                created += 1

            # Level 3: CATEGORIES
            for cat_enum, cat_label in PROJECT_CATEGORIES:
                cat_code = f"{proj_node_code}-{cat_enum.value}"
                cat_node = await _get_or_create_node(
                    db, tenant_id, cat_code, f"{cat_label} — {proj.nom or proj.code}",
                    3, proj_node["id"],
                    f"CC-GROUPE/{ent_node_code}/{proj_node_code}/{cat_code}",
                    entreprise_id=ent.id, projet_id=proj.id,
                    categorie=cat_enum,
                )
                if cat_node["created"]:
                    created += 1

        # Level 2: SIEGE (function node)
        siege_code = f"CC-{ent_code}-SIEGE"
        siege_node = await _get_or_create_node(
            db, tenant_id, siege_code, f"Siège — {ent.raison_sociale}",
            2, ent_node["id"],
            f"CC-GROUPE/{ent_node_code}/{siege_code}",
            entreprise_id=ent.id, categorie=CategorieCC.SIEGE,
        )
        if siege_node["created"]:
            created += 1

        # Level 2: FISCAL SOCIÉTÉ
        fisc_code = f"CC-{ent_code}-FISCAL-SOCIETE"
        fisc_node = await _get_or_create_node(
            db, tenant_id, fisc_code, f"Charges fiscales société — {ent.raison_sociale}",
            2, ent_node["id"],
            f"CC-GROUPE/{ent_node_code}/{fisc_code}",
            entreprise_id=ent.id, categorie=CategorieCC.FISCAL,
        )
        if fisc_node["created"]:
            created += 1

    # Level 1: Bureau BBZ (transversal)
    bbz_code = "CC-BBZ"
    bbz_node = await _get_or_create_node(
        db, tenant_id, bbz_code, "Bureau Bab Ezzouar",
        1, root["id"], f"CC-GROUPE/{bbz_code}",
    )
    if bbz_node["created"]:
        created += 1

    # Level 1: Per-associate transversal nodes
    assoc_result = await db.execute(
        select(Associe).where(
            Associe.tenant_id == tenant_id,
            Associe.is_active == True,
        )
    )
    # Deduplicate by name (associes can exist in multiple enterprises)
    seen_names: set[str] = set()
    for assoc in assoc_result.scalars().all():
        name_key = assoc.nom.upper().strip()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        short = _assoc_short(assoc.nom)
        assoc_code = f"CC-ASS-{short}"
        assoc_node = await _get_or_create_node(
            db, tenant_id, assoc_code, f"Consolidation {assoc.nom}",
            1, root["id"], f"CC-GROUPE/{assoc_code}",
            associe_id=assoc.id,
        )
        if assoc_node["created"]:
            created += 1

    await db.flush()
    # Now build distributions
    dist_created = await _build_distributions(db, tenant_id)

    return {"nodes_created": created, "distributions_created": dist_created}


async def _get_or_create_node(
    db: AsyncSession, tenant_id: str,
    code: str, libelle: str, niveau: int,
    parent_id: Optional[str], chemin: str,
    entreprise_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    associe_id: Optional[str] = None,
    categorie: Optional[CategorieCC] = None,
) -> dict:
    """Get existing node or create new one. Returns {id, created}."""
    result = await db.execute(
        select(CCNode).where(
            CCNode.tenant_id == tenant_id,
            CCNode.code == code,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {"id": existing.id, "created": False}

    node = CCNode(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        code=code,
        libelle=libelle,
        niveau=niveau,
        parent_id=parent_id,
        chemin_complet=chemin,
        entreprise_id=entreprise_id,
        projet_id=projet_id,
        associe_id=associe_id,
        categorie=categorie,
    )
    db.add(node)
    await db.flush()
    return {"id": node.id, "created": True}


def _project_short_code(name: str) -> str:
    """Generate short code from project name."""
    replacements = {
        "LES JASMINS": "JASMINS", "JARDIN DE L'OPÉRA": "OPERA",
        "JARDIN DE LOPERA": "OPERA", "05 HECTARE BOUMERDES": "5H",
        "05 HECTARE": "5H", "AVELIS DRIVE": "EDRIVE",
        "ALLO MAISON": "ALLOMAISON", "LES LYS": "LYS",
        "LES MAGNOLIA": "MAGNOLIA", "EL ACHOUR": "ACHOUR",
        "EDEN ST": "EDEN-ST",
    }
    upper = name.upper().strip()
    for full, short in replacements.items():
        if full in upper:
            return short
    # Default: first 8 chars uppercase, no spaces
    return upper.replace(" ", "")[:10]


def _assoc_short(name: str) -> str:
    """Short code for associate."""
    upper = name.upper().strip()
    if "AHMED" in upper:
        return "AHMED"
    if "MOHAMED" in upper:
        return "MOHAMED"
    if "LYAZID" in upper or "BOUABDELLAH" in upper:
        return "LYAZID"
    if "YAMINA" in upper:
        return "YAMINA"
    return upper.replace(" ", "")[:10]


# ────────────────────────────────────────────────────────────────────────────
# 2. Build distributions (% per associate per node)
# ────────────────────────────────────────────────────────────────────────────

async def _build_distributions(db: AsyncSession, tenant_id: str) -> int:
    """Build CCDistribution for all nodes based on EntrepriseAssocie + PartProjet."""
    created = 0

    # Get all CC nodes
    nodes_result = await db.execute(
        select(CCNode).where(CCNode.tenant_id == tenant_id)
    )
    nodes = nodes_result.scalars().all()

    for node in nodes:
        if node.niveau < 1:
            continue  # Skip root (groupe)

        if node.entreprise_id and node.projet_id:
            # Project-level node: use PartProjet % for charges/benefice
            parts_result = await db.execute(
                select(PartProjet).where(
                    PartProjet.projet_id == node.projet_id,
                    PartProjet.tenant_id == tenant_id,
                )
            )
            parts = parts_result.scalars().all()

            # Also get enterprise % for CFF
            ent_parts_result = await db.execute(
                select(EntrepriseAssocie).where(
                    EntrepriseAssocie.entreprise_id == node.entreprise_id,
                    EntrepriseAssocie.est_actif == True,
                )
            )
            ent_parts = {ep.associe_id: float(ep.pourcentage) for ep in ent_parts_result.scalars().all()}

            for part in parts:
                pct_proj = float(part.pourcentage)
                pct_ent = ent_parts.get(part.associe_id, 0.0)

                existing = await db.execute(
                    select(CCDistribution).where(
                        CCDistribution.cc_node_id == node.id,
                        CCDistribution.associe_id == part.associe_id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                db.add(CCDistribution(
                    id=str(uuid.uuid4()),
                    cc_node_id=node.id,
                    associe_id=part.associe_id,
                    pct_entreprise=pct_ent,
                    pct_projet=pct_proj,
                    pct_applicable_charges=pct_proj,  # Charges directes = % projet
                    pct_applicable_cff=pct_ent,  # CFF = % entreprise ÉMETTRICE
                    pct_applicable_benefice=pct_proj,  # Bénéfices = % projet
                ))
                created += 1

        elif node.entreprise_id:
            # Enterprise-level or siege: use EntrepriseAssocie %
            ent_parts_result = await db.execute(
                select(EntrepriseAssocie).where(
                    EntrepriseAssocie.entreprise_id == node.entreprise_id,
                    EntrepriseAssocie.est_actif == True,
                )
            )
            for ep in ent_parts_result.scalars().all():
                pct = float(ep.pourcentage)
                existing = await db.execute(
                    select(CCDistribution).where(
                        CCDistribution.cc_node_id == node.id,
                        CCDistribution.associe_id == ep.associe_id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                db.add(CCDistribution(
                    id=str(uuid.uuid4()),
                    cc_node_id=node.id,
                    associe_id=ep.associe_id,
                    pct_entreprise=pct,
                    pct_projet=pct,
                    pct_applicable_charges=pct,  # Société charges = % entreprise
                    pct_applicable_cff=pct,
                    pct_applicable_benefice=pct,
                ))
                created += 1

    await db.flush()
    return created


# ────────────────────────────────────────────────────────────────────────────
# 3. Compute dynamic aggregates (no materialized view — computed on the fly)
# ────────────────────────────────────────────────────────────────────────────

async def compute_node_aggregates(
    db: AsyncSession, tenant_id: str, node_id: str,
    periode: Optional[str] = None,
) -> dict:
    """Compute aggregates for a single CC node from existing financial data.

    Instead of relying on cc_imputation records, we compute directly from
    encaissements/décaissements tables for project-level nodes.
    """
    node_result = await db.execute(
        select(CCNode).where(CCNode.id == node_id)
    )
    node = node_result.scalar_one_or_none()
    if not node:
        return {}

    if node.projet_id:
        return await _compute_project_aggregates(db, tenant_id, node, periode)
    elif node.entreprise_id:
        return await _compute_enterprise_aggregates(db, tenant_id, node, periode)
    elif node.niveau == 0:
        return await _compute_group_aggregates(db, tenant_id, node, periode)
    return _empty_aggregates(node)


async def _compute_project_aggregates(
    db: AsyncSession, tenant_id: str, node: CCNode,
    periode: Optional[str] = None,
) -> dict:
    """Compute aggregates for a project-level node directly from transaction tables."""
    projet_id = node.projet_id
    entreprise_id = node.entreprise_id

    # Build period filter
    def _period_filter_enc(q):
        if periode:
            year, month = int(periode[:4]), int(periode[5:7])
            from sqlalchemy import extract
            q = q.where(
                extract("year", Encaissement.date_encaissement) == year,
                extract("month", Encaissement.date_encaissement) == month,
            )
        return q

    def _period_filter_dec(q):
        if periode:
            year, month = int(periode[:4]), int(periode[5:7])
            from sqlalchemy import extract
            q = q.where(
                extract("year", Decaissement.date_decaissement) == year,
                extract("month", Decaissement.date_decaissement) == month,
            )
        return q

    # Encaissements by RF
    enc_base = select(
        sa_func.coalesce(sa_func.sum(Encaissement.montant), 0)
    ).where(
        Encaissement.projet_id == projet_id,
        Encaissement.tenant_id == tenant_id,
    )

    enc_total = (await db.execute(_period_filter_enc(enc_base))).scalar() or 0

    enc_rf1 = (await db.execute(_period_filter_enc(
        enc_base.where(Encaissement.statut_fiscal.in_([
            StatutFiscal.REEL_DECLARE, StatutFiscal.FICTIF,
        ]))
    ))).scalar() or 0

    enc_rf2 = (await db.execute(_period_filter_enc(
        enc_base.where(Encaissement.statut_fiscal == StatutFiscal.REEL_NON_DECLARE)
    ))).scalar() or 0

    # Décaissements by RF
    dec_base = select(
        sa_func.coalesce(sa_func.sum(Decaissement.montant), 0)
    ).where(
        Decaissement.projet_id == projet_id,
        Decaissement.tenant_id == tenant_id,
    )

    dec_total = (await db.execute(_period_filter_dec(dec_base))).scalar() or 0

    dec_rf1 = (await db.execute(_period_filter_dec(
        dec_base.where(Decaissement.statut_fiscal.in_([
            StatutFiscal.REEL_DECLARE, StatutFiscal.FICTIF,
        ]))
    ))).scalar() or 0

    dec_rf2 = (await db.execute(_period_filter_dec(
        dec_base.where(Decaissement.statut_fiscal == StatutFiscal.REEL_NON_DECLARE)
    ))).scalar() or 0

    # CFF for this project's enterprise
    cff_total = 0
    cff_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(CFFFacture.cff_total), 0)).where(
            CFFFacture.projet_id == projet_id,
        )
    )
    cff_total = float(cff_result.scalar() or 0)

    # ── Masse salariale from employees assigned to this project ──
    masse_salariale = 0
    try:
        from app.models.hr import Employee, EmploymentStatus
        from app.models.planification import SPIMensuel
        import json as _json

        emp_result = await db.execute(
            select(Employee).where(
                Employee.tenant_id == tenant_id,
                Employee.status == EmploymentStatus.ACTIVE,
            )
        )
        all_emps = emp_result.scalars().all()

        for emp in all_emps:
            # Check if employee is assigned to this project
            pct_temps = 0
            if emp.entite_juridique_id == entreprise_id:
                affectations = emp.projets_affectes
                if isinstance(affectations, str):
                    try:
                        affectations = _json.loads(affectations)
                    except Exception:
                        affectations = []
                if isinstance(affectations, list):
                    for aff in affectations:
                        if isinstance(aff, dict) and aff.get("projet_id") == projet_id:
                            pct_temps = float(aff.get("pourcentage_temps", 0))
                            break
                if pct_temps == 0 and not affectations:
                    pct_temps = 100  # default: 100% if no affectation specified

            if pct_temps > 0:
                base = float(emp.base_salary or 0)
                prime = float(emp.prime_spi_plafond or 0) * 0.8  # avg prime estimate
                total_emp = base + prime
                masse_salariale += total_emp * pct_temps / 100
    except Exception:
        pass  # Graceful fallback — don't break CC if planification models unavailable

    enc_total_f = float(enc_total)
    dec_total_f = float(dec_total) + round(masse_salariale, 2)
    solde_net = enc_total_f - dec_total_f
    solde_officiel = float(enc_rf1) - float(dec_rf1)

    # Get distributions for quote-parts
    dist_result = await db.execute(
        select(CCDistribution).where(CCDistribution.cc_node_id == node.id)
    )
    distributions = dist_result.scalars().all()

    # Get associate names
    assoc_ids = [d.associe_id for d in distributions]
    assoc_names = {}
    if assoc_ids:
        names_result = await db.execute(
            select(Associe.id, Associe.nom).where(Associe.id.in_(assoc_ids))
        )
        assoc_names = {r[0]: r[1] for r in names_result.all()}

    # Quote-parts by associate
    quote_parts = []
    for dist in distributions:
        pct_charge = float(dist.pct_applicable_charges)
        pct_cff = float(dist.pct_applicable_cff)
        pct_benef = float(dist.pct_applicable_benefice)

        qp_enc = round(enc_total_f * pct_benef / 100, 2)
        qp_dec = round(dec_total_f * pct_charge / 100, 2)
        qp_cff = round(cff_total * pct_cff / 100, 2)
        qp_solde = round(qp_enc - qp_dec, 2)
        qp_net = round(qp_solde - qp_cff, 2)

        quote_parts.append({
            "associe_id": dist.associe_id,
            "nom": assoc_names.get(dist.associe_id, "?"),
            "pct_projet": float(dist.pct_projet),
            "pct_entreprise": float(dist.pct_entreprise),
            "qp_encaissements": qp_enc,
            "qp_decaissements": qp_dec,
            "qp_cff": qp_cff,
            "qp_solde_net": qp_solde,
            "qp_net_apres_cff": qp_net,
        })

    return {
        "node_id": node.id,
        "code": node.code,
        "libelle": node.libelle,
        "niveau": node.niveau,
        "entreprise_id": node.entreprise_id,
        "projet_id": node.projet_id,
        # Vue interne (RF1+RF2+RF3+RF4)
        "encaissements": enc_total_f,
        "decaissements": dec_total_f,
        "cff_total": cff_total,
        "solde_net": solde_net,
        # Vue officielle (RF1+RF3 only)
        "encaissements_officiel": float(enc_rf1),
        "decaissements_officiel": float(dec_rf1),
        "solde_officiel": solde_officiel,
        # RF breakdown
        "encaissements_rf1": float(enc_rf1),
        "encaissements_rf2": float(enc_rf2),
        "decaissements_rf1": float(dec_rf1),
        "decaissements_rf2": float(dec_rf2),
        # Masse salariale
        "masse_salariale": round(masse_salariale, 2),
        # Ratios
        "marge_brute_pct": round((solde_net / enc_total_f * 100) if enc_total_f > 0 else 0, 2),
        "impact_cff_pct": round((cff_total / enc_total_f * 100) if enc_total_f > 0 else 0, 2),
        "poids_rf2_pct": round(
            (float(enc_rf2) / (float(enc_rf1) + float(enc_rf2)) * 100)
            if (float(enc_rf1) + float(enc_rf2)) > 0 else 0, 2
        ),
        # Quote-parts
        "quote_parts": quote_parts,
    }


async def _compute_enterprise_aggregates(
    db: AsyncSession, tenant_id: str, node: CCNode,
    periode: Optional[str] = None,
) -> dict:
    """Aggregate all projects under an enterprise."""
    children = await db.execute(
        select(CCNode).where(
            CCNode.parent_id == node.id,
            CCNode.projet_id.isnot(None),
            CCNode.niveau == 2,
        )
    )
    child_nodes = children.scalars().all()

    totals = {
        "encaissements": 0, "decaissements": 0, "cff_total": 0,
        "solde_net": 0, "encaissements_officiel": 0, "decaissements_officiel": 0,
        "solde_officiel": 0, "encaissements_rf1": 0, "encaissements_rf2": 0,
        "decaissements_rf1": 0, "decaissements_rf2": 0,
    }
    projets_data = []

    for child in child_nodes:
        agg = await _compute_project_aggregates(db, tenant_id, child, periode)
        for key in totals:
            totals[key] += agg.get(key, 0)
        projets_data.append(agg)

    return {
        "node_id": node.id,
        "code": node.code,
        "libelle": node.libelle,
        "niveau": node.niveau,
        "entreprise_id": node.entreprise_id,
        **totals,
        "marge_brute_pct": round(
            (totals["solde_net"] / totals["encaissements"] * 100)
            if totals["encaissements"] > 0 else 0, 2
        ),
        "projets": projets_data,
    }


async def _compute_group_aggregates(
    db: AsyncSession, tenant_id: str, node: CCNode,
    periode: Optional[str] = None,
) -> dict:
    """Aggregate all enterprises under the group."""
    children = await db.execute(
        select(CCNode).where(
            CCNode.parent_id == node.id,
            CCNode.entreprise_id.isnot(None),
            CCNode.niveau == 1,
        )
    )
    child_nodes = children.scalars().all()

    totals = {
        "encaissements": 0, "decaissements": 0, "cff_total": 0,
        "solde_net": 0, "encaissements_officiel": 0, "decaissements_officiel": 0,
        "solde_officiel": 0,
    }
    entreprises_data = []

    for child in child_nodes:
        agg = await _compute_enterprise_aggregates(db, tenant_id, child, periode)
        for key in totals:
            totals[key] += agg.get(key, 0)
        entreprises_data.append(agg)

    return {
        "node_id": node.id,
        "code": node.code,
        "libelle": node.libelle,
        "niveau": 0,
        **totals,
        "marge_brute_pct": round(
            (totals["solde_net"] / totals["encaissements"] * 100)
            if totals["encaissements"] > 0 else 0, 2
        ),
        "entreprises": entreprises_data,
    }


def _empty_aggregates(node: CCNode) -> dict:
    return {
        "node_id": node.id, "code": node.code, "libelle": node.libelle,
        "niveau": node.niveau,
        "encaissements": 0, "decaissements": 0, "cff_total": 0,
        "solde_net": 0, "solde_officiel": 0,
    }


# ────────────────────────────────────────────────────────────────────────────
# 4. Get the CC tree structure (for frontend rendering)
# ────────────────────────────────────────────────────────────────────────────

async def get_cc_tree(
    db: AsyncSession, tenant_id: str,
    entreprise_id: Optional[str] = None,
    projet_id: Optional[str] = None,
    max_niveau: int = 5,
) -> list[dict]:
    """Get CC tree as nested structure for frontend."""
    q = select(CCNode).where(
        CCNode.tenant_id == tenant_id,
        CCNode.est_actif == True,
        CCNode.niveau <= max_niveau,
    ).order_by(CCNode.chemin_complet)

    if entreprise_id:
        q = q.where(
            (CCNode.entreprise_id == entreprise_id) | (CCNode.niveau == 0)
        )
    if projet_id:
        q = q.where(
            (CCNode.projet_id == projet_id) |
            (CCNode.niveau <= 1) |
            (CCNode.projet_id.is_(None))
        )

    result = await db.execute(q)
    nodes = result.scalars().all()

    # Build flat list
    node_list = []
    for n in nodes:
        node_list.append({
            "id": n.id,
            "code": n.code,
            "libelle": n.libelle,
            "niveau": n.niveau,
            "parent_id": n.parent_id,
            "entreprise_id": n.entreprise_id,
            "projet_id": n.projet_id,
            "associe_id": n.associe_id,
            "categorie": n.categorie.value if n.categorie else None,
            "est_actif": n.est_actif,
            "chemin": n.chemin_complet,
        })

    return node_list


# ────────────────────────────────────────────────────────────────────────────
# 5. Dashboard data
# ────────────────────────────────────────────────────────────────────────────

async def get_dashboard_data(
    db: AsyncSession, tenant_id: str,
    periode: Optional[str] = None,
) -> dict:
    """Get full dashboard data for the DAF view."""
    # Ensure tree exists
    await build_cc_tree(db, tenant_id)

    # Get group root
    root_result = await db.execute(
        select(CCNode).where(
            CCNode.tenant_id == tenant_id,
            CCNode.code == "CC-GROUPE",
        )
    )
    root = root_result.scalar_one_or_none()
    if not root:
        return {"error": "No CC tree found"}

    # Group aggregates
    group_agg = await compute_node_aggregates(db, tenant_id, root.id, periode)

    # Per-associate consolidation
    assoc_consolidation = await _get_associate_consolidation(db, tenant_id, periode)

    # Top projects by margin
    top_projects = await _get_top_projects(db, tenant_id, periode)

    # Enterprise breakdown
    entreprises = group_agg.get("entreprises", [])

    return {
        "groupe": {
            "encaissements": group_agg.get("encaissements", 0),
            "decaissements": group_agg.get("decaissements", 0),
            "cff_total": group_agg.get("cff_total", 0),
            "solde_net": group_agg.get("solde_net", 0),
            "solde_officiel": group_agg.get("solde_officiel", 0),
            "marge_brute_pct": group_agg.get("marge_brute_pct", 0),
        },
        "associes": assoc_consolidation,
        "top_projets": top_projects,
        "entreprises": [
            {
                "code": e.get("code", ""),
                "libelle": e.get("libelle", ""),
                "encaissements": e.get("encaissements", 0),
                "decaissements": e.get("decaissements", 0),
                "solde_net": e.get("solde_net", 0),
                "cff_total": e.get("cff_total", 0),
                "marge_brute_pct": e.get("marge_brute_pct", 0),
                "nb_projets": len(e.get("projets", [])),
            }
            for e in entreprises
        ],
        "periode": periode or "cumul",
    }


async def _get_associate_consolidation(
    db: AsyncSession, tenant_id: str,
    periode: Optional[str] = None,
) -> list[dict]:
    """Consolidate all project data per associate."""
    # Get all project-level nodes with distributions
    proj_nodes = await db.execute(
        select(CCNode).where(
            CCNode.tenant_id == tenant_id,
            CCNode.projet_id.isnot(None),
            CCNode.niveau == 2,
            CCNode.est_actif == True,
        )
    )

    # Accumulate per associate
    assoc_totals: dict[str, dict] = {}

    for node in proj_nodes.scalars().all():
        agg = await _compute_project_aggregates(db, tenant_id, node, periode)
        for qp in agg.get("quote_parts", []):
            aid = qp["associe_id"]
            if aid not in assoc_totals:
                assoc_totals[aid] = {
                    "associe_id": aid,
                    "nom": qp["nom"],
                    "qp_encaissements": 0,
                    "qp_decaissements": 0,
                    "qp_cff": 0,
                    "qp_net": 0,
                    "nb_projets": 0,
                }
            assoc_totals[aid]["qp_encaissements"] += qp["qp_encaissements"]
            assoc_totals[aid]["qp_decaissements"] += qp["qp_decaissements"]
            assoc_totals[aid]["qp_cff"] += qp["qp_cff"]
            assoc_totals[aid]["qp_net"] += qp["qp_net_apres_cff"]
            assoc_totals[aid]["nb_projets"] += 1

    return sorted(assoc_totals.values(), key=lambda x: x["qp_net"], reverse=True)


async def _get_top_projects(
    db: AsyncSession, tenant_id: str,
    periode: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Get top projects by margin."""
    proj_nodes = await db.execute(
        select(CCNode).where(
            CCNode.tenant_id == tenant_id,
            CCNode.projet_id.isnot(None),
            CCNode.niveau == 2,
            CCNode.est_actif == True,
        )
    )

    projects = []
    for node in proj_nodes.scalars().all():
        agg = await _compute_project_aggregates(db, tenant_id, node, periode)
        projects.append({
            "code": node.code,
            "libelle": node.libelle,
            "encaissements": agg.get("encaissements", 0),
            "decaissements": agg.get("decaissements", 0),
            "solde_net": agg.get("solde_net", 0),
            "marge_brute_pct": agg.get("marge_brute_pct", 0),
            "cff_total": agg.get("cff_total", 0),
            "poids_rf2_pct": agg.get("poids_rf2_pct", 0),
        })

    projects.sort(key=lambda x: x["marge_brute_pct"], reverse=True)
    return projects[:limit]


# ────────────────────────────────────────────────────────────────────────────
# 6. Double-vue (officielle vs interne)
# ────────────────────────────────────────────────────────────────────────────

async def get_double_vue(
    db: AsyncSession, tenant_id: str, node_id: str,
    periode: Optional[str] = None,
) -> dict:
    """Get the dual view: official (RF1+RF3) vs internal (RF1+RF2+RF3+RF4)."""
    agg = await compute_node_aggregates(db, tenant_id, node_id, periode)

    return {
        "node": {"id": agg.get("node_id"), "code": agg.get("code"), "libelle": agg.get("libelle")},
        "vue_officielle": {
            "encaissements": agg.get("encaissements_officiel", 0),
            "decaissements": agg.get("decaissements_officiel", 0),
            "solde_net": agg.get("solde_officiel", 0),
        },
        "vue_interne": {
            "encaissements": agg.get("encaissements", 0),
            "decaissements": agg.get("decaissements", 0),
            "solde_net": agg.get("solde_net", 0),
            "cff_total": agg.get("cff_total", 0),
        },
        "rf_breakdown": {
            "encaissements_rf1": agg.get("encaissements_rf1", 0),
            "encaissements_rf2": agg.get("encaissements_rf2", 0),
            "decaissements_rf1": agg.get("decaissements_rf1", 0),
            "decaissements_rf2": agg.get("decaissements_rf2", 0),
        },
        "quote_parts": agg.get("quote_parts", []),
        "ratios": {
            "marge_brute_pct": agg.get("marge_brute_pct", 0),
            "impact_cff_pct": agg.get("impact_cff_pct", 0),
            "poids_rf2_pct": agg.get("poids_rf2_pct", 0),
        },
    }
