"""
GFI v7.0 — Centre de Couts Engine: the financial truth engine.

Consolidates ALL flows (RF1+RF2+RF3+RF4) per project, per company,
per associate. Real profitability, not declared fiction.

Core API:
  initialize_tree(session) -> builds full 6-level hierarchy
  impute(node_code, rf_type, montant, ...) -> records + ascending propagation
  verify_v1(node_code) -> checks SUM(children) = parent
  get_tree(company_id) -> returns full CC tree for an entity
  get_project_profitability(project_id) -> revenue - costs per RF
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class V1IntegrityError(Exception):
    """V1: SUM(children) != parent — BLOQUANT."""
    def __init__(self, message: str, node_code: str, expected: Decimal, actual: Decimal):
        super().__init__(message)
        self.node_code = node_code
        self.expected = expected
        self.actual = actual


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── 16 Standard Cost Categories (Level 3) ────────────────────────────────────
CATEGORIES = [
    ("TERRAIN", "Cout du terrain"),
    ("CONSTR", "Construction et realisation"),
    ("VRD", "Voiries et reseaux divers"),
    ("ETUDES", "Etudes et honoraires"),
    ("NATURE_ST", "Prestations en nature / sous-traitance"),
    ("CFF", "Dossier fiscal fictif (CFF)"),
    ("FRAIS_FIN", "Frais financiers"),
    ("COMPENSATION", "Compensations en nature"),
    ("ASSOC", "Prelevements associes"),
    ("COMMISSION", "Commissions et dettes personnelles"),
    ("CHARGES_GEN", "Charges generales ventilees"),
    ("VENTES_RF1", "Ventes declarees (RF1)"),
    ("VENTES_RF2", "Ventes non declarees (RF2)"),
    ("IMPOTS", "Impots et taxes"),
    ("DIVERS", "Divers"),
    ("INTER_PROJ", "Flux inter-projets"),
]


def _get_or_create_node(
    session: Session,
    *,
    code: str,
    level: int,
    libelle: str,
    node_type: str,
    company_id: UUID,
    parent_id: UUID | None = None,
    parent_code: str | None = None,
    project_id: UUID | None = None,
    categorie: str | None = None,
    impact_tresorerie: bool = True,
) -> object:
    """Get existing node or create it."""
    from app.models.cost_center import CostCenterNode

    existing = (
        session.query(CostCenterNode)
        .filter(CostCenterNode.code == code, CostCenterNode.is_deleted.is_(False))
        .first()
    )
    if existing:
        return existing

    node = CostCenterNode(
        company_id=company_id,
        code=code,
        level=level,
        parent_id=parent_id,
        parent_code=parent_code,
        libelle=libelle,
        node_type=node_type,
        project_id=project_id,
        categorie=categorie,
        impact_tresorerie=impact_tresorerie,
    )
    session.add(node)
    session.flush()
    return node


def initialize_tree(session: Session) -> dict:
    """
    Auto-generate the full CC tree for all 12 entities and their
    active projects. Creates 16 category nodes under each project.
    """
    from app.models.company import Company
    from app.models.project import Project

    stats = {"nodes_created": 0, "entities": 0, "projects": 0}

    companies = (
        session.query(Company)
        .filter(Company.is_deleted.is_(False))
        .all()
    )

    # Level 0: Groupe root
    # Use first company's ID for the root (system-level node)
    root_cid = companies[0].id if companies else None
    if not root_cid:
        return stats

    root = _get_or_create_node(
        session, code="CC-GROUPE", level=0,
        libelle="Groupe GFI", node_type="GROUPE",
        company_id=root_cid,
    )
    stats["nodes_created"] += 1

    # Entity code mapping for CC codes
    entity_codes = {}
    for i, c in enumerate(companies, 1):
        entity_codes[c.id] = f"ENT{i}"

    for company in companies:
        ent_code = entity_codes[company.id]
        cc_ent = f"CC-{ent_code}"

        # Level 1: Enterprise
        ent_node = _get_or_create_node(
            session, code=cc_ent, level=1,
            libelle=company.legal_name, node_type="ENTREPRISE",
            company_id=company.id,
            parent_id=root.id, parent_code=root.code,
        )
        stats["nodes_created"] += 1
        stats["entities"] += 1

        # Get projects for this entity
        active_statuses = ("ACTIF", "TERRAIN", "DONATION")
        projects = (
            session.query(Project)
            .filter(
                Project.company_id == company.id,
                Project.status.in_(active_statuses),
                Project.is_deleted.is_(False),
            )
            .all()
        )

        # Dissolved entities get minimal structure
        if company.status == "DISSOUTE":
            _get_or_create_node(
                session, code=f"{cc_ent}-CFF", level=3,
                libelle=f"CFF historique {company.code}",
                node_type="CATEGORIE",
                company_id=company.id, categorie="CFF",
                parent_id=ent_node.id, parent_code=ent_node.code,
            )
            stats["nodes_created"] += 1
            continue

        for project in projects:
            cc_proj = f"{cc_ent}-{project.code}"

            # Level 2: Project
            proj_node = _get_or_create_node(
                session, code=cc_proj, level=2,
                libelle=f"Projet {project.name}",
                node_type="PROJET",
                company_id=company.id, project_id=project.id,
                parent_id=ent_node.id, parent_code=ent_node.code,
            )
            stats["nodes_created"] += 1
            stats["projects"] += 1

            # Level 3: 16 categories under each project
            for cat_code, cat_label in CATEGORIES:
                is_compensation = cat_code == "COMPENSATION"
                _get_or_create_node(
                    session, code=f"{cc_proj}-{cat_code}", level=3,
                    libelle=cat_label, node_type="CATEGORIE",
                    company_id=company.id, project_id=project.id,
                    categorie=cat_code,
                    parent_id=proj_node.id, parent_code=proj_node.code,
                    impact_tresorerie=not is_compensation,
                )
                stats["nodes_created"] += 1

        # Level 2: Function nodes (siege, BBZ)
        for func_code, func_label in [("SIEGE", "Siege"), ("BBZ", "Bureau Bab Ezzouar")]:
            _get_or_create_node(
                session, code=f"{cc_ent}-{func_code}", level=2,
                libelle=func_label, node_type="FONCTION",
                company_id=company.id,
                parent_id=ent_node.id, parent_code=ent_node.code,
            )
            stats["nodes_created"] += 1

        # Level 2: Inter-projects node
        _get_or_create_node(
            session, code=f"{cc_ent}-INTER-PROJETS", level=2,
            libelle="Flux inter-projets", node_type="FONCTION",
            company_id=company.id,
            parent_id=ent_node.id, parent_code=ent_node.code,
        )
        stats["nodes_created"] += 1

    session.flush()
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# IMPUTATION WITH ASCENDING CONSOLIDATION
# ═════════════════════════════════════════════════════════════════════════════

def impute(
    session: Session,
    *,
    node_code: str,
    rf_type: str,
    montant: Decimal,
    entry_date: date,
    libelle: str,
    company_id: UUID,
    project_id: UUID | None = None,
    source_type: str | None = None,
    source_id: UUID | None = None,
    impact_tresorerie: bool = True,
    created_by: UUID | None = None,
) -> object:
    """
    Record an imputation at a CC node and propagate upward.
    This is the CORE function — every financial event calls this.

    Real-time ascending consolidation: the amount is added to the node
    AND all its ancestors up to CC-GROUPE in the SAME transaction.
    """
    from app.models.cost_center import CostCenterNode, CostCenterEntry

    montant = Decimal(str(montant))

    # Find the target node
    node = (
        session.query(CostCenterNode)
        .filter(
            CostCenterNode.code == node_code,
            CostCenterNode.is_deleted.is_(False),
        )
        .first()
    )

    if node is None:
        # Auto-create leaf node if parent exists
        parts = node_code.rsplit("-", 1)
        if len(parts) == 2:
            parent_code = parts[0]
            parent = (
                session.query(CostCenterNode)
                .filter(CostCenterNode.code == parent_code,
                        CostCenterNode.is_deleted.is_(False))
                .first()
            )
            if parent:
                node = CostCenterNode(
                    company_id=company_id,
                    code=node_code,
                    level=parent.level + 1,
                    parent_id=parent.id,
                    parent_code=parent.code,
                    libelle=libelle,
                    node_type="SOUS_CATEGORIE" if parent.level == 3 else "DETAIL",
                    project_id=project_id or parent.project_id,
                    impact_tresorerie=impact_tresorerie,
                )
                session.add(node)
                session.flush()

    if node is None:
        raise ValueError(f"CC node '{node_code}' not found and cannot be auto-created.")

    # Create the entry
    entry = CostCenterEntry(
        company_id=company_id,
        node_id=node.id,
        node_code=node_code,
        entry_date=entry_date,
        rf_type=rf_type,
        montant=montant,
        libelle=libelle,
        source_type=source_type,
        source_id=source_id,
        project_id=project_id,
        impact_tresorerie=impact_tresorerie,
        created_by=created_by,
    )
    session.add(entry)

    # ── Ascending consolidation ──────────────────────────────────────────
    # Update the node and ALL ancestors up to root
    rf_col = f"montant_{rf_type.lower()}"
    current = node
    while current is not None:
        setattr(current, rf_col,
                _r2(Decimal(str(getattr(current, rf_col))) + montant))
        current.montant_total = _r2(
            Decimal(str(current.montant_rf1))
            + Decimal(str(current.montant_rf2))
            + Decimal(str(current.montant_rf3))
            + Decimal(str(current.montant_rf4))
        )
        # Move to parent
        if current.parent_id:
            current = session.get(CostCenterNode, current.parent_id)
        else:
            current = None

    session.flush()
    return entry


# ═════════════════════════════════════════════════════════════════════════════
# VERIFICATION V1: SUM(children) = parent
# ═════════════════════════════════════════════════════════════════════════════

def verify_v1(
    session: Session,
    node_code: str,
) -> dict:
    """
    V1: Verify ascending integrity at a node.
    Checks SUM(all direct children montant_total) == node montant_total.
    Returns {status: 'PASS'/'FAIL', ...}
    """
    from app.models.cost_center import CostCenterNode

    node = (
        session.query(CostCenterNode)
        .filter(CostCenterNode.code == node_code, CostCenterNode.is_deleted.is_(False))
        .first()
    )
    if node is None:
        return {"status": "ERROR", "message": f"Node {node_code} not found."}

    # Get children sum
    children_sum = (
        session.query(sqfunc.coalesce(sqfunc.sum(CostCenterNode.montant_total), 0))
        .filter(
            CostCenterNode.parent_id == node.id,
            CostCenterNode.is_deleted.is_(False),
        )
        .scalar()
    )
    children_sum = Decimal(str(children_sum))

    # For leaf nodes (no children), check entries sum
    child_count = (
        session.query(sqfunc.count(CostCenterNode.id))
        .filter(CostCenterNode.parent_id == node.id,
                CostCenterNode.is_deleted.is_(False))
        .scalar()
    )

    if child_count == 0:
        # Leaf node — check entries
        from app.models.cost_center import CostCenterEntry
        entries_sum = (
            session.query(sqfunc.coalesce(sqfunc.sum(CostCenterEntry.montant), 0))
            .filter(
                CostCenterEntry.node_id == node.id,
                CostCenterEntry.is_deleted.is_(False),
            )
            .scalar()
        )
        entries_sum = Decimal(str(entries_sum))
        node_total = Decimal(str(node.montant_total))

        if _r2(entries_sum) != _r2(node_total):
            return {
                "status": "FAIL",
                "node_code": node_code,
                "expected": str(entries_sum),
                "actual": str(node_total),
                "message": (
                    f"Incoherence CC : somme entries {entries_sum} DA "
                    f"!= noeud {node_total} DA au noeud {node_code}."
                ),
            }
        return {"status": "PASS", "node_code": node_code}

    # Non-leaf: check children sum vs node total
    node_total = Decimal(str(node.montant_total))

    if _r2(children_sum) != _r2(node_total):
        return {
            "status": "FAIL",
            "node_code": node_code,
            "expected": str(children_sum),
            "actual": str(node_total),
            "message": (
                f"Incoherence CC : somme enfants {children_sum} DA "
                f"!= parent {node_total} DA au noeud {node_code}."
            ),
        }

    return {"status": "PASS", "node_code": node_code}


def verify_v1_recursive(
    session: Session,
    node_code: str = "CC-GROUPE",
) -> list[dict]:
    """Run V1 recursively on a subtree. Returns all failures."""
    from app.models.cost_center import CostCenterNode

    failures = []

    result = verify_v1(session, node_code)
    if result["status"] == "FAIL":
        failures.append(result)

    # Check children
    node = (
        session.query(CostCenterNode)
        .filter(CostCenterNode.code == node_code, CostCenterNode.is_deleted.is_(False))
        .first()
    )
    if node:
        children = (
            session.query(CostCenterNode)
            .filter(CostCenterNode.parent_id == node.id,
                    CostCenterNode.is_deleted.is_(False))
            .all()
        )
        for child in children:
            failures.extend(verify_v1_recursive(session, child.code))

    return failures


def get_tree(
    session: Session,
    company_id: UUID | None = None,
    root_code: str = "CC-GROUPE",
    max_depth: int = 6,
) -> list[dict]:
    """Get the CC tree as a flat list with indentation level."""
    from app.models.cost_center import CostCenterNode

    query = session.query(CostCenterNode).filter(
        CostCenterNode.is_deleted.is_(False),
    )
    if company_id:
        query = query.filter(CostCenterNode.company_id == company_id)

    nodes = query.order_by(CostCenterNode.code).all()

    return [
        {
            "code": n.code,
            "level": n.level,
            "libelle": n.libelle,
            "montant_rf1": str(n.montant_rf1),
            "montant_rf2": str(n.montant_rf2),
            "montant_rf3": str(n.montant_rf3),
            "montant_rf4": str(n.montant_rf4),
            "montant_total": str(n.montant_total),
            "parent_code": n.parent_code,
        }
        for n in nodes if n.level <= max_depth
    ]


def get_project_profitability(
    session: Session,
    project_id: UUID,
) -> dict:
    """Get revenue - costs per RF for a project."""
    from app.models.cost_center import CostCenterNode

    nodes = (
        session.query(CostCenterNode)
        .filter(
            CostCenterNode.project_id == project_id,
            CostCenterNode.level == 3,
            CostCenterNode.is_deleted.is_(False),
        )
        .all()
    )

    revenue_rf1 = Decimal("0")
    revenue_rf2 = Decimal("0")
    costs = Decimal("0")

    for n in nodes:
        if n.categorie in ("VENTES_RF1",):
            revenue_rf1 += Decimal(str(n.montant_rf1))
        elif n.categorie in ("VENTES_RF2",):
            revenue_rf2 += Decimal(str(n.montant_rf2))
        else:
            costs += Decimal(str(n.montant_total))

    return {
        "revenue_rf1": str(revenue_rf1),
        "revenue_rf2": str(revenue_rf2),
        "revenue_total": str(revenue_rf1 + revenue_rf2),
        "costs_total": str(costs),
        "profit_officiel": str(revenue_rf1 - costs),
        "profit_reel": str(revenue_rf1 + revenue_rf2 - costs),
    }
